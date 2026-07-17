from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, field_validator

from photo_mecha_battle.api.database import Database, UserRow
from photo_mecha_battle.api.db_path import resolve_db_path
from photo_mecha_battle.api.game_store import FeatureMismatchError, GameStore, QuotaExceededError
from photo_mecha_battle.api.store import build_demo_cpu_team
from photo_mecha_battle.features import FEATURES_ALGO_VERSION, FeatureVector
from photo_mecha_battle.models import MechForm, Position
from photo_mecha_battle.tactics import (
    PRESET_LABELS,
    ActionType,
    ConditionKind,
    TacticPreset,
    TacticSet,
    TacticSlot,
    build_preset,
    Condition,
)

DATA_DIR = Path(os.environ.get("PMB_DATA_DIR", "data"))
# docs/12: 既定はファイル SQLite（{PMB_DATA_DIR}/pmb.sqlite3）。PMB_DB_PATH で上書き可。
# テストは conftest.fresh_game_store が :memory: に差し替える。
_DB_PATH = resolve_db_path(ensure_parent=True)
store = GameStore(db=Database(str(_DB_PATH)), data_dir=DATA_DIR)
app = FastAPI(title="Photo Mecha Battle API", version="0.3.0")
app.mount("/media", StaticFiles(directory=str(store.image_storage.root)), name="media")

# 簡易Webクライアント（撮影→メカ生成→編成→バトルを一気通貫で試せるデモUI）。
# バックエンドAPIの薄いフロントに過ぎず、バトル結果自体はサーバー側の既存エンドポイントで
# 決定される（docs/09 信頼モデル）。モバイルクライアント本体（P25-007）はスコープ外のまま。
_WEB_CLIENT_DIR = Path(os.environ.get("PMB_WEB_DIR", str(Path(__file__).resolve().parents[3] / "web")))
if _WEB_CLIENT_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=str(_WEB_CLIENT_DIR), html=True), name="web_client")


def get_store() -> GameStore:
    return store


def require_user(
    x_user_token: Annotated[str | None, Header()] = None,
    game_store: GameStore = Depends(get_store),
) -> UserRow:
    # docs/07 API 共通規約: X-User-Token の「欠落・無効」はいずれも 401 とする。
    if x_user_token is None:
        raise HTTPException(status_code=401, detail="missing token")
    user = game_store.authenticate(x_user_token)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid token")
    return user


# docs/06 デモ用 Entitlement 付与 API の扱い / PLAN D-004: 本番公開前に管理者権限チェックまたは
# エンドポイント無効化を必須とする。PMB_ADMIN_TOKEN が未設定の環境（=本番デフォルト）では
# 常に拒否し、事実上エンドポイントを無効化する。設定されたデモ環境でのみ、一致する
# X-Admin-Token を持つ呼び出しを許可する。
_ADMIN_TOKEN_ENV_VAR = "PMB_ADMIN_TOKEN"


def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
    configured = os.environ.get(_ADMIN_TOKEN_ENV_VAR)
    if not configured or x_admin_token != configured:
        raise HTTPException(status_code=403, detail="admin token required")


# PLAN D-005 / docs/06 Webhook: RevenueCat は Webhook に HMAC 署名を付与しないため、ダッシュボードで
# 設定した共有シークレットを Authorization ヘッダーで検証する方式が公式サポートの認証手段。
# 環境変数が未設定の場合（本番デフォルト）は常に拒否し、エンドポイントを事実上無効化する。
# 実シークレットの発行・設定は外部作業（config/revenuecat_pending_setup.json 参照）。
_REVENUECAT_WEBHOOK_SECRET_ENV_VAR = "PMB_REVENUECAT_WEBHOOK_SECRET"


def require_revenuecat_webhook_auth(authorization: Annotated[str | None, Header()] = None) -> None:
    configured = os.environ.get(_REVENUECAT_WEBHOOK_SECRET_ENV_VAR)
    if not configured or authorization != configured:
        raise HTTPException(status_code=401, detail="invalid webhook credentials")


class RegisterRequest(BaseModel):
    name: str


class CaptureCreateRequest(BaseModel):
    label: str = "umbrella"


class SegmentRequest(BaseModel):
    label: str = "umbrella"
    bbox: list[float] | None = None


class MechCreateRequest(BaseModel):
    object_id: str
    name: str
    # PLAN D-013: 型はサーバー推定で確定する（docs/03 form_inference/1.0）。
    # 後方互換のため form を受理はするが、値は無視して常にサーバー推定で上書きする。
    form: MechForm | None = None


class MechDirectCreateRequest(BaseModel):
    """docs/09 主経路: クライアント厚め構成の 1 リクエストメカ登録の JSON パート。

    `form` は受け付けない（送られてもモデル定義に無いため無視され、サーバー推定が正）。
    """

    name: str
    algo_version: str
    bbox: list[float] | None = None
    features: dict[str, float]

    @field_validator("bbox")
    @classmethod
    def _validate_bbox(cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return value
        if (
            len(value) != 4
            or not all(0.0 <= coord <= 1.0 for coord in value)
            or value[0] >= value[2]
            or value[1] >= value[3]
        ):
            raise ValueError("bbox must be [x1, y1, x2, y2] normalized to 0.0-1.0 with x1 < x2, y1 < y2")
        return value


class TacticSlotRequest(BaseModel):
    condition_kind: ConditionKind
    condition_threshold: str | int | float | None = None
    action: ActionType


class TacticCreateRequest(BaseModel):
    name: str
    slots: list[TacticSlotRequest] = Field(max_length=4)
    fallback_action: ActionType


class TeamSlotConfig(BaseModel):
    mech_id: str
    tactic_id: str
    position: Position


class TeamCreateRequest(BaseModel):
    name: str
    slots: list[TeamSlotConfig]


class MatchRequest(BaseModel):
    team_id: str


class RankedBattleRequest(BaseModel):
    team_id: str
    # docs/09 信頼モデル / PLAN D-007: ランク戦の seed は常にサーバーが生成する。
    # クライアントがこのフィールドを送っても後方互換のため 400 にはせず、単に無視する。
    seed: int | None = None


class BattleSlotRequest(BaseModel):
    mech_id: str
    position: Position
    preset: TacticPreset


class BattleCreateRequest(BaseModel):
    team_name: str = "Player"
    slots: list[BattleSlotRequest]
    seed: int = 42


class EntitlementUpdateRequest(BaseModel):
    entitlement_key: str
    is_active: bool


class RevenueCatWebhookRequest(BaseModel):
    api_version: str | None = None
    event: dict[str, object]


class BillingSyncRequest(BaseModel):
    active_entitlements: list[str] = Field(default_factory=list)


def _build_tactic_set(body: TacticCreateRequest) -> TacticSet:
    slots = [
        TacticSlot(
            condition=Condition(
                kind=slot.condition_kind,
                threshold=MechForm(slot.condition_threshold)
                if slot.condition_kind == ConditionKind.TARGET_FORM and isinstance(slot.condition_threshold, str)
                else slot.condition_threshold,
            ),
            action=slot.action,
        )
        for slot in body.slots
    ]
    return TacticSet.from_slots(body.name, slots, body.fallback_action)


def _team_slots_to_row(user_id: str, name: str, slots: list[TeamSlotConfig]):
    by_position = {slot.position: slot for slot in slots}
    if set(by_position) != {Position.FRONT, Position.MIDDLE, Position.BACK}:
        raise HTTPException(status_code=400, detail="team must include front, middle, and back")
    return store.create_team(
        user_id=user_id,
        name=name,
        front_mech_id=by_position[Position.FRONT].mech_id,
        front_tactic_id=by_position[Position.FRONT].tactic_id,
        middle_mech_id=by_position[Position.MIDDLE].mech_id,
        middle_tactic_id=by_position[Position.MIDDLE].tactic_id,
        back_mech_id=by_position[Position.BACK].mech_id,
        back_tactic_id=by_position[Position.BACK].tactic_id,
    )


@app.post("/auth/register")
def register_user(body: RegisterRequest, game_store: GameStore = Depends(get_store)):
    user = game_store.register_user(body.name)
    return {"user_id": user.id, "name": user.name, "token": user.token, "rating": user.rating}


@app.get("/auth/me")
def get_current_user(user: UserRow = Depends(require_user)):
    return {"user_id": user.id, "name": user.name, "rating": user.rating}


@app.post("/captures")
def create_capture(body: CaptureCreateRequest, game_store: GameStore = Depends(get_store)):
    record = game_store.create_capture(body.label)
    return {"id": record.id, "label": record.label, "mode": "stub"}


@app.post("/captures/upload")
def upload_capture(
    user: UserRow = Depends(require_user),
    file: UploadFile = File(...),
    game_store: GameStore = Depends(get_store),
):
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty file")
    try:
        return game_store.create_capture_upload(user.id, content, file.filename or "capture.jpg")
    except ValueError as exc:
        message = str(exc)
        if message == "duplicate_capture":
            raise HTTPException(status_code=409, detail="duplicate capture") from exc
        if message.startswith("unsafe_capture:"):
            reason = message.split(":", 1)[1]
            raise HTTPException(
                status_code=422,
                detail={"error": "unsafe_capture", "reason": reason, "action": "recapture"},
            ) from exc
        raise HTTPException(status_code=400, detail=message) from exc
    except QuotaExceededError as exc:
        raise HTTPException(status_code=429, detail=f"{exc.resource} quota exceeded") from exc


@app.post("/captures/{capture_id}/detect")
def detect_objects(capture_id: str, game_store: GameStore = Depends(get_store)):
    if capture_id not in game_store.captures and game_store.db.get_capture(capture_id) is None:
        raise HTTPException(status_code=404, detail="capture not found")
    return {"candidates": game_store.detect_objects(capture_id)}


@app.post("/captures/{capture_id}/segment")
def segment_object(capture_id: str, body: SegmentRequest, game_store: GameStore = Depends(get_store)):
    if capture_id not in game_store.captures and game_store.db.get_capture(capture_id) is None:
        raise HTTPException(status_code=404, detail="capture not found")
    record = game_store.segment_object(capture_id, body.label, body.bbox)
    return {
        "id": record.id,
        "capture_id": record.capture_id,
        "info_score": record.info_score,
        "features": record.features.__dict__,
    }


@app.post("/objects/{object_id}/analyze")
def analyze_object(object_id: str, game_store: GameStore = Depends(get_store)):
    analysis = game_store.get_object_analysis(object_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="object not found")
    return analysis


async def _create_mech_direct(request: Request, user: UserRow, game_store: GameStore):
    """docs/09 主経路: multipart（`payload` JSON + `crop` 画像）でのメカ直登録。"""
    form = await request.form()
    payload_raw = form.get("payload")
    crop_part = form.get("crop")
    if payload_raw is None or crop_part is None or isinstance(crop_part, str):
        raise HTTPException(
            status_code=400,
            detail="multipart request must include 'payload' (JSON string) and 'crop' (image file)",
        )
    try:
        payload_text = payload_raw if isinstance(payload_raw, str) else (await payload_raw.read()).decode("utf-8")
        payload = MechDirectCreateRequest.model_validate(json.loads(payload_text))
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid payload: {exc}") from exc
    try:
        client_features = FeatureVector(**payload.features)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid features: {exc}") from exc

    crop_bytes = await crop_part.read()
    if not crop_bytes:
        raise HTTPException(status_code=400, detail="empty crop file")

    try:
        return game_store.create_mech_direct(
            user.id,
            payload.name,
            payload.algo_version,
            payload.bbox,
            client_features,
            crop_bytes,
        )
    except FeatureMismatchError as exc:
        # docs/09 信頼モデル: 差分が閾値超なら reject（クライアント実装ずれの検出を優先し、
        # 黙ってサーバー値で上書きしない）。
        raise HTTPException(
            status_code=422,
            detail={
                "error": "feature_mismatch",
                "dimension": exc.dimension,
                "client": exc.client_value,
                "server": exc.server_value,
                "tolerance": exc.tolerance,
            },
        ) from exc
    except QuotaExceededError as exc:
        raise HTTPException(status_code=429, detail=f"{exc.resource} quota exceeded") from exc
    except ValueError as exc:
        message = str(exc)
        if message == "duplicate_capture":
            raise HTTPException(status_code=409, detail="duplicate capture") from exc
        if message.startswith("unsafe_capture:"):
            reason = message.split(":", 1)[1]
            raise HTTPException(
                status_code=422,
                detail={"error": "unsafe_capture", "reason": reason, "action": "recapture"},
            ) from exc
        if message.startswith("unsupported_algo_version:"):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "unsupported_algo_version",
                    "sent": message.split(":", 1)[1],
                    "supported": [FEATURES_ALGO_VERSION],
                },
            ) from exc
        if message.startswith("invalid_image:"):
            raise HTTPException(status_code=400, detail="crop is not a decodable image") from exc
        raise HTTPException(status_code=400, detail=message) from exc


@app.post("/mechs")
async def create_mech(request: Request, user: UserRow = Depends(require_user), game_store: GameStore = Depends(get_store)):
    # docs/09: multipart は本番モバイルの主経路（crop + features 直登録）、JSON はサーバー側
    # パイプライン（object_id 参照）の互換経路。Content-Type で分岐する。
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        return await _create_mech_direct(request, user, game_store)

    try:
        body = MechCreateRequest.model_validate(await request.json())
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid request body: {exc}") from exc

    extracted = game_store.db.get_extracted_object(body.object_id)
    if body.object_id not in game_store.objects and extracted is None:
        raise HTTPException(status_code=404, detail="object not found")
    # docs/07 所有権（D-008 と同型）: アップロード写真由来の object は所有者のみ使用可。
    # デモ経路（POST /captures、DB に capture が無い）は所有者を持たないため対象外。
    if extracted is not None:
        capture = game_store.db.get_capture(str(extracted["capture_id"]))
        if capture is not None and capture["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="object belongs to another user")
    try:
        return game_store.create_mech_for_user(user.id, body.object_id, body.name)
    except QuotaExceededError as exc:
        raise HTTPException(status_code=429, detail=f"{exc.resource} quota exceeded") from exc


@app.get("/mechs")
def list_mechs(user: UserRow = Depends(require_user), game_store: GameStore = Depends(get_store)):
    return {"mechs": game_store.list_user_mechs(user.id)}


@app.get("/mechs/{mech_id}")
def get_mech(mech_id: str, game_store: GameStore = Depends(get_store)):
    record = game_store.get_persisted_mech(mech_id)
    if record is None:
        legacy = game_store.mechs.get(mech_id)
        if legacy is None:
            raise HTTPException(status_code=404, detail="mech not found")
        mech = legacy.mech
        return {
            "id": legacy.id,
            "object_id": legacy.object_id,
            "name": mech.name,
            "form": mech.form.value,
            "stats": mech.stats.__dict__,
        }
    return record


@app.get("/tactic-presets")
def list_tactic_presets():
    return {
        "presets": [
            {"id": preset.value, "name": preset.name, "label": PRESET_LABELS[preset]}
            for preset in TacticPreset
        ]
    }


@app.get("/tactics/catalog")
def tactic_catalog():
    return {
        "conditions": [kind.value for kind in ConditionKind],
        "actions": [action.value for action in ActionType],
    }


@app.post("/tactics")
def create_tactic(body: TacticCreateRequest, user: UserRow = Depends(require_user), game_store: GameStore = Depends(get_store)):
    tactic = _build_tactic_set(body)
    return game_store.create_tactic(user.id, tactic)


@app.get("/tactics/{tactic_id}")
def get_tactic(tactic_id: str, game_store: GameStore = Depends(get_store)):
    row = game_store.db.get_tactic(tactic_id)
    if row is None:
        raise HTTPException(status_code=404, detail="tactic not found")
    return {"id": row["id"], **row["payload"]}


@app.put("/tactics/{tactic_id}")
def update_tactic(
    tactic_id: str,
    body: TacticCreateRequest,
    user: UserRow = Depends(require_user),
    game_store: GameStore = Depends(get_store),
):
    existing = game_store.db.get_tactic(tactic_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="tactic not found")
    if existing["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    tactic = _build_tactic_set(body)
    return game_store.update_tactic(tactic_id, tactic)


class TacticSimulateRequest(BaseModel):
    mech_id: str
    seed: int = 0


@app.post("/tactics/{tactic_id}/simulate")
def simulate_tactic(
    tactic_id: str,
    body: TacticSimulateRequest,
    game_store: GameStore = Depends(get_store),
):
    if game_store.db.get_tactic(tactic_id) is None:
        raise HTTPException(status_code=404, detail="tactic not found")
    try:
        result = game_store.simulate_tactic(tactic_id, body.mech_id, body.seed)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "seed": result.seed,
        "winner_team_id": result.winner_team_id,
        "turns": result.turns,
        "log": result.format_log(),
    }


@app.post("/teams")
def create_team(body: TeamCreateRequest, user: UserRow = Depends(require_user)):
    if len(body.slots) != 3:
        raise HTTPException(status_code=400, detail="team must have exactly 3 slots")
    team = _team_slots_to_row(user.id, body.name, body.slots)
    return {"id": team.id, "name": team.name}


@app.put("/teams/{team_id}")
def update_team(
    team_id: str,
    body: TeamCreateRequest,
    user: UserRow = Depends(require_user),
    game_store: GameStore = Depends(get_store),
):
    if len(body.slots) != 3:
        raise HTTPException(status_code=400, detail="team must have exactly 3 slots")
    existing = game_store.db.get_team(team_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="team not found")
    if existing.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    by_position = {slot.position: slot for slot in body.slots}
    if set(by_position) != {Position.FRONT, Position.MIDDLE, Position.BACK}:
        raise HTTPException(status_code=400, detail="team must include front, middle, and back")
    team = game_store.update_team(
        team_id=team_id,
        user_id=user.id,
        name=body.name,
        front_mech_id=by_position[Position.FRONT].mech_id,
        front_tactic_id=by_position[Position.FRONT].tactic_id,
        middle_mech_id=by_position[Position.MIDDLE].mech_id,
        middle_tactic_id=by_position[Position.MIDDLE].tactic_id,
        back_mech_id=by_position[Position.BACK].mech_id,
        back_tactic_id=by_position[Position.BACK].tactic_id,
    )
    return {"id": team.id, "name": team.name}


@app.get("/teams/{team_id}")
def get_team(team_id: str, user: UserRow = Depends(require_user), game_store: GameStore = Depends(get_store)):
    team = game_store.db.get_team(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="team not found")
    if team.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    return {
        "id": team.id,
        "name": team.name,
        "front_mech_id": team.front_mech_id,
        "front_tactic_id": team.front_tactic_id,
        "middle_mech_id": team.middle_mech_id,
        "middle_tactic_id": team.middle_tactic_id,
        "back_mech_id": team.back_mech_id,
        "back_tactic_id": team.back_tactic_id,
    }


@app.post("/battles/match")
def match_opponent(body: MatchRequest, user: UserRow = Depends(require_user), game_store: GameStore = Depends(get_store)):
    team = game_store.db.get_team(body.team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="team not found")
    if team.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    game_store.queue_for_match(team.id)
    opponent = game_store.find_opponent(user.id, user.rating)
    if opponent is None:
        return {"matched": False, "opponent_type": "cpu"}
    opponent_user = game_store.db.get_user(opponent.user_id)
    return {
        "matched": True,
        "opponent_type": "player",
        "opponent_team_id": opponent.id,
        "opponent_name": opponent_user.name if opponent_user else "Unknown",
    }


@app.post("/battles/ranked")
def create_ranked_battle(
    body: RankedBattleRequest,
    user: UserRow = Depends(require_user),
    game_store: GameStore = Depends(get_store),
):
    team = game_store.db.get_team(body.team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="team not found")
    if team.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")

    opponent_row = game_store.find_opponent(user.id, user.rating)
    opponent_user = None
    opponent_team = None
    opponent_tactics = None
    if opponent_row is not None:
        opponent_user = game_store.db.get_user(opponent_row.user_id)
        opponent_team, opponent_tactics = game_store.load_team_for_battle(opponent_row)

    battle = game_store.run_ranked_battle(
        user,
        team,
        opponent_team,
        opponent_tactics,
        opponent_user,
        opponent_row,
    )
    result = battle.result
    return {
        "id": battle.id,
        "seed": result.seed,
        "winner_team_id": result.winner_team_id,
        "turns": result.turns,
        "log": result.format_log(),
        "rating": game_store.db.get_user(user.id).rating if game_store.db.get_user(user.id) else user.rating,
    }


@app.post("/battles")
def create_battle(body: BattleCreateRequest, game_store: GameStore = Depends(get_store)):
    if len(body.slots) != 3:
        raise HTTPException(status_code=400, detail="team must have exactly 3 slots")

    from photo_mecha_battle.models import Team, TeamSlot

    player_slots: list[TeamSlot] = []
    player_tactics: dict[Position, TacticSet] = {}
    for slot in body.slots:
        mech_record = game_store.mechs.get(slot.mech_id)
        persisted = game_store.get_persisted_mech(slot.mech_id)
        if mech_record is None and persisted is None:
            raise HTTPException(status_code=404, detail=f"mech not found: {slot.mech_id}")
        mech = mech_record.mech if mech_record else game_store._load_mech(slot.mech_id)
        player_slots.append(TeamSlot(mech=mech, position=slot.position))
        player_tactics[slot.position] = build_preset(slot.preset)

    player_team = Team(id="player", name=body.team_name, slots=player_slots)
    cpu_team, cpu_tactics = build_demo_cpu_team()
    battle = game_store.run_battle(player_team, player_tactics, cpu_team, cpu_tactics, body.seed)
    result = battle.result
    return {
        "id": battle.id,
        "seed": result.seed,
        "winner_team_id": result.winner_team_id,
        "turns": result.turns,
        "log": result.format_log(),
    }


@app.get("/battles/{battle_id}")
def get_battle(
    battle_id: str,
    user: UserRow = Depends(require_user),
    game_store: GameStore = Depends(get_store),
):
    record = game_store.get_battle_record(battle_id)
    if record is None:
        raise HTTPException(status_code=404, detail="battle not found")
    # docs/07 所有権 / PLAN D-008: 対戦当事者 (player_a / player_b) のみ参照可。
    # CPU 戦は player_b_id が無いため player_a のみ。所有者なし（デモ用 POST /battles）は
    # 認証済みユーザーなら誰でも閲覧可とする。
    player_a_id = record.get("player_a_id")
    player_b_id = record.get("player_b_id")
    if player_a_id is not None and user.id not in {player_a_id, player_b_id}:
        raise HTTPException(status_code=403, detail="forbidden")
    return record


@app.get("/ranking")
def get_ranking(game_store: GameStore = Depends(get_store)):
    return {"entries": game_store.db.get_ranking()}


@app.get("/users/quotas")
def get_user_quotas(user: UserRow = Depends(require_user), game_store: GameStore = Depends(get_store)):
    return game_store.get_user_quotas(user.id)


@app.get("/billing/status")
def billing_status(user: UserRow = Depends(require_user), game_store: GameStore = Depends(get_store)):
    return {
        "user_id": user.id,
        "entitlements": game_store.db.get_entitlements(user.id),
        "note": "RevenueCat sync stub — battle capabilities are not gated by entitlements.",
    }


@app.get("/billing/entitlements")
def list_entitlements(user: UserRow = Depends(require_user), game_store: GameStore = Depends(get_store)):
    return {"entitlements": game_store.db.get_entitlements(user.id)}


@app.post("/billing/entitlements")
def update_entitlement(
    body: EntitlementUpdateRequest,
    user: UserRow = Depends(require_user),
    game_store: GameStore = Depends(get_store),
    _admin: None = Depends(require_admin),
):
    # docs/08 ハッカソン対応: デモ用にEntitlementを強制付与できる管理者フラグ。
    # PLAN D-004: 呼び出しには X-Admin-Token（require_admin）が必須。
    # さらに docs/06 で定義された既知のEntitlementキーのみ許可し、任意の権限を
    # 作り出せないようにする（戦闘力・戦術スロット数には影響しない領域に限定）。
    if body.entitlement_key not in GameStore.KNOWN_ENTITLEMENT_KEYS:
        raise HTTPException(status_code=400, detail=f"unknown entitlement_key: {body.entitlement_key}")
    game_store.db.set_entitlement(user.id, body.entitlement_key, body.is_active)
    return {"entitlements": game_store.db.get_entitlements(user.id)}


@app.post("/billing/sync")
def sync_billing(
    body: BillingSyncRequest,
    user: UserRow = Depends(require_user),
    game_store: GameStore = Depends(get_store),
):
    return game_store.sync_client_entitlements(user.id, body.active_entitlements)


@app.post("/billing/revenuecat/webhook")
def revenuecat_webhook(
    body: RevenueCatWebhookRequest,
    game_store: GameStore = Depends(get_store),
    _auth: None = Depends(require_revenuecat_webhook_auth),
):
    event = body.event
    app_user_id = str(event.get("app_user_id", ""))
    event_id = str(event.get("id", ""))
    event_type = str(event.get("type", ""))
    # docs/06: entitlement_id は RevenueCat 公式ドキュメントで非推奨。entitlement_ids を優先し、
    # 無い場合のみ後方互換で単数形から補う。
    entitlement_ids = event.get("entitlement_ids")
    if not entitlement_ids and event.get("entitlement_id"):
        entitlement_ids = [event["entitlement_id"]]
    if not app_user_id:
        raise HTTPException(status_code=400, detail="missing app_user_id")
    if not event_id:
        raise HTTPException(status_code=400, detail="missing event id")
    return game_store.apply_revenuecat_event(event_id, app_user_id, event_type, list(entitlement_ids or []))
