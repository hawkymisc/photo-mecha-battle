from __future__ import annotations

import secrets
import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image

from photo_mecha_battle.api.capture_pipeline import (
    DUPLICATE_HASH_DISTANCE,
    PENALIZED_INFO_SCORE_CAP,
    SCORE_PENALIZED_SAFETY_REASONS,
    create_capture_from_bytes,
    detect_for_capture,
    segment_for_capture,
)
from photo_mecha_battle.api.database import Database, TeamRow, UserRow
from photo_mecha_battle.api.image_storage import ImageStorage
from photo_mecha_battle.api.limits import limits_for_user
from photo_mecha_battle.api.store import InMemoryStore, CaptureRecord, ObjectRecord, build_demo_cpu_team
from photo_mecha_battle.battle import BattleEngine, BattleResult
from photo_mecha_battle.battle_log_serde import battle_log_to_payload
from photo_mecha_battle.features import FEATURES_ALGO_VERSION, FeatureVector
from photo_mecha_battle.mech_stats import FORM_INFERENCE_VERSION, compute_info_score
from photo_mecha_battle.models import Mech, MechForm, MechStats, Position, Team, TeamSlot
from photo_mecha_battle.tactics import TacticSet
from photo_mecha_battle.tactics_serde import tactic_set_from_payload, tactic_set_to_payload
from photo_mecha_battle.vision.analysis import (
    MASK_FOREGROUND_THRESHOLD,
    analyze_rgba_crop,
    assess_capture_safety,
    hamming_distance,
    perceptual_hash,
)
from photo_mecha_battle.vision.mech_art import render_mech_art
from photo_mecha_battle.vision.segmentation import image_to_png_bytes


class QuotaExceededError(Exception):
    def __init__(self, resource: str) -> None:
        self.resource = resource
        super().__init__(f"quota exceeded: {resource}")


class FeatureMismatchError(Exception):
    """docs/09 信頼モデル: クライアント申告特徴量とサーバー再計算値の差分が閾値を超えた。"""

    def __init__(self, dimension: str, client_value: float, server_value: float, tolerance: float) -> None:
        self.dimension = dimension
        self.client_value = client_value
        self.server_value = server_value
        self.tolerance = tolerance
        super().__init__(
            f"feature mismatch: {dimension} client={client_value:.4f} server={server_value:.4f} tolerance={tolerance}"
        )


class GameStore:
    def __init__(self, db: Database, data_dir: Path | None = None) -> None:
        self.db = db
        self._session = InMemoryStore()
        root = data_dir or Path("data")
        self.image_storage = ImageStorage(root)

    @property
    def captures(self):
        return self._session.captures

    @property
    def objects(self):
        return self._session.objects

    @property
    def mechs(self):
        return self._session.mechs

    @property
    def battles(self):
        return self._session.battles

    def create_capture(self, label: str = "umbrella"):
        return self._session.create_capture(label)

    def create_capture_upload(self, user_id: str, content: bytes, filename: str) -> dict[str, object]:
        self._ensure_capture_quota(user_id)
        suffix = Path(filename).suffix or ".jpg"
        result = create_capture_from_bytes(self.db, self.image_storage, user_id, content, suffix)
        record = CaptureRecord(id=str(result["id"]), label="upload", has_image=True)
        self._session.captures[record.id] = record
        return result

    def detect_objects(self, capture_id: str):
        if self.db.get_capture(capture_id) is not None:
            return detect_for_capture(self.db, capture_id)
        return self._session.detect_objects(capture_id)

    def segment_object(self, capture_id: str, label: str = "umbrella", bbox: list[float] | None = None):
        if self.db.get_capture(capture_id) is not None:
            if bbox is None:
                candidates = detect_for_capture(self.db, capture_id)
                bbox = candidates[0]["bbox"]
            pipeline_object = segment_for_capture(
                self.db,
                self.image_storage,
                capture_id,
                bbox,
                label=label,
            )
            record = ObjectRecord(
                id=pipeline_object.id,
                capture_id=pipeline_object.capture_id,
                features=pipeline_object.features,
                info_score=pipeline_object.info_score,
            )
            self.objects[record.id] = record
            return record
        return self._session.segment_object(capture_id, label)

    def create_mech(self, object_id: str, name: str):
        self._restore_session_object(object_id)
        return self._session.create_mech(object_id, name)

    def _restore_session_object(self, object_id: str) -> None:
        """DB 保存済みの抽出オブジェクトをセッションへ復元する。

        プロセス再起動後はセッション objects が空になるが、`POST /mechs` の
        存在チェックは DB 側 extracted_objects も許可するため、features_json
        から FeatureVector を復元して型推定・生成を成立させる
        （session に既にあれば何もしない）。
        """
        if object_id in self._session.objects:
            return
        extracted = self.db.get_extracted_object(object_id)
        if extracted is None:
            return  # 呼び出し元の KeyError に委ねる（API 層は事前に 404 を返す）
        features = FeatureVector(**extracted["features"])
        self._session.objects[object_id] = ObjectRecord(
            id=object_id,
            capture_id=str(extracted["capture_id"]),
            features=features,
            info_score=float(extracted["info_score"]),
        )

    def run_battle(self, team_a, tactics_a, team_b, tactics_b, seed: int):
        return self._session.run_battle(team_a, tactics_a, team_b, tactics_b, seed)

    def register_user(self, name: str) -> UserRow:
        return self.db.create_user(name)

    def authenticate(self, token: str) -> UserRow | None:
        return self.db.get_user_by_token(token)

    def get_user_quotas(self, user_id: str) -> dict[str, object]:
        usage = self.db.get_quota_usage(user_id)
        limits = limits_for_user(self.db.get_entitlements(user_id))
        return {
            "captures": {
                "used": usage["captures_used"],
                "limit": limits.captures,
                "remaining": max(0, limits.captures - usage["captures_used"]),
            },
            "mechs": {
                "used": usage["mechs_used"],
                "limit": limits.mechs,
                "remaining": max(0, limits.mechs - usage["mechs_used"]),
            },
        }

    def create_mech_for_user(self, user_id: str, object_id: str, name: str) -> dict[str, object]:
        self._ensure_mech_quota(user_id)
        record = self.create_mech(object_id, name)
        art_url = self._render_and_store_art(record.id, object_id, record.mech.form)
        self.db.save_mech(
            user_id,
            record.id,
            record.object_id,
            record.mech.form.value,
            record.mech.name,
            record.mech.stats.__dict__,
            art_url=art_url,
        )
        self.db.increment_quota(user_id, "mechs_used")
        response = self._mech_response(record.id, record.object_id, record.mech)
        response["art_url"] = art_url
        return response

    # docs/09 信頼モデル: クライアント申告 feature_vector とサーバー再計算値の許容差分 ε。
    DIRECT_FEATURE_TOLERANCE = 0.05
    # docs/09 信頼モデル「最小解像度」: これ未満の crop は特徴量が不安定なため再撮影を促す。
    MIN_CROP_DIMENSION = 64

    @staticmethod
    def _is_solid_color_foreground(canonical: Image.Image) -> bool:
        """docs/09 信頼モデル「極端な単色画像の拒否」: 前景が実質 1 色なら True。

        補間で中間色が混ざらないよう、リサイズせず正規形の画素を直接数える。
        """
        colors = {
            (r, g, b)
            for r, g, b, a in canonical.getdata()
            if a >= MASK_FOREGROUND_THRESHOLD
        }
        return len(colors) <= 1

    def create_mech_direct(
        self,
        user_id: str,
        name: str,
        algo_version: str,
        bbox: list[float] | None,
        client_features: FeatureVector,
        crop_bytes: bytes,
    ) -> dict[str, object]:
        """docs/09 主経路: crop + features を 1 リクエストで受け取りメカを確定する。

        検証順序は `/captures/upload` と揃える:
        クォータ事前確認 → phash 重複 → 安全性ゲート → 特徴量再計算・差分検証 →
        永続化（capture / extracted_object / mech）→ クォータ消費。
        """
        if algo_version != FEATURES_ALGO_VERSION:
            raise ValueError(f"unsupported_algo_version:{algo_version}")
        self._ensure_capture_quota(user_id)
        self._ensure_mech_quota(user_id)

        try:
            crop = Image.open(BytesIO(crop_bytes)).convert("RGBA")
        except Exception as exc:
            raise ValueError(f"invalid_image:{exc}") from exc

        # 透明領域に残った不可視 RGB が phash・安全性判定・特徴量に影響しないよう、
        # 以降はすべて正規形（背景ゼロ化済み crop）に対して行う（docs/09 信頼モデル）。
        analysis = analyze_rgba_crop(crop)
        canonical = analysis.canonical
        mask = analysis.mask
        background_mix = analysis.background_mix
        server_features = analysis.features

        # docs/09 信頼モデル「最小解像度、極端な単色画像の拒否」+ マスク空チェック。
        # いずれも安全性ゲートと同じ「再撮影」導線のエラー種別で返す。
        if min(canonical.width, canonical.height) < self.MIN_CROP_DIMENSION:
            raise ValueError("unsafe_capture:crop_too_small")
        if analysis.foreground_ratio <= 0.0:
            raise ValueError("unsafe_capture:empty_mask")
        if self._is_solid_color_foreground(canonical):
            raise ValueError("unsafe_capture:solid_color_crop")

        phash = perceptual_hash(canonical)
        for existing in self.db.list_capture_hashes(user_id):
            if hamming_distance(phash, existing) <= DUPLICATE_HASH_DISTANCE:
                raise ValueError("duplicate_capture")

        safety_status, safety_reason = assess_capture_safety(canonical, phash)
        if safety_status == "blocked":
            raise ValueError(f"unsafe_capture:{safety_reason}")

        for dimension, server_value in server_features.__dict__.items():
            client_value = getattr(client_features, dimension)
            if abs(client_value - server_value) > self.DIRECT_FEATURE_TOLERANCE:
                raise FeatureMismatchError(dimension, client_value, server_value, self.DIRECT_FEATURE_TOLERANCE)

        info_score = compute_info_score(server_features)
        if safety_reason in SCORE_PENALIZED_SAFETY_REASONS:
            info_score = min(info_score, PENALIZED_INFO_SCORE_CAP)

        capture_id = str(uuid.uuid4())
        saved_capture = self.image_storage.save_capture(user_id, crop_bytes, ".png")
        self.db.save_capture(
            capture_id=capture_id,
            user_id=user_id,
            original_path=str(saved_capture),
            perceptual_hash=phash,
            safety_status=safety_status,
            quality_json={"safety_reason": safety_reason} if safety_reason else {},
        )

        object_id = str(uuid.uuid4())
        # 以降の art 生成・再検証は正規形 crop を正とする（不可視 RGB を持ち込まない）。
        crop_path = self.image_storage.save_crop(object_id, image_to_png_bytes(canonical))
        mask_path = self.image_storage.save_mask(object_id, image_to_png_bytes(mask))
        mask_confidence = min(0.98, 0.5 + analysis.foreground_ratio)
        self.db.save_extracted_object(
            object_id=object_id,
            capture_id=capture_id,
            bbox_json=bbox or [0.0, 0.0, 1.0, 1.0],
            mask_path=str(mask_path),
            crop_path=str(crop_path),
            features_json=server_features.__dict__,
            info_score=info_score,
            detected_label="client_direct",
            confidence=mask_confidence,
            quality_json={"background_mix": background_mix},
            safety_status=safety_status,
        )
        self._session.objects[object_id] = ObjectRecord(
            id=object_id,
            capture_id=capture_id,
            features=server_features,
            info_score=info_score,
        )

        # capture クォータはメカ確定が成功してから消費する。途中失敗時に
        # 「枠だけ消費してメカ未作成」となる不整合を避ける（レビュー指摘 M4）。
        response = self.create_mech_for_user(user_id, object_id, name)
        self.db.increment_quota(user_id, "captures_used")
        # docs/09: サーバー確定値をクライアントに返す（クライアントプレビューと異なる場合がある）。
        response["features"] = server_features.__dict__
        response["info_score"] = info_score
        response["algo_version"] = FEATURES_ALGO_VERSION
        return response

    def _render_and_store_art(self, mech_id: str, object_id: str, form: MechForm) -> str | None:
        extracted = self.db.get_extracted_object(object_id)
        if extracted is None or not extracted.get("crop_path"):
            return None
        crop_path = Path(extracted["crop_path"])
        if not crop_path.exists():
            return None
        from PIL import Image

        crop = Image.open(crop_path).convert("RGBA")
        art_bytes = render_mech_art(crop, form)
        art_path = self.image_storage.save_art(mech_id, art_bytes)
        return self.image_storage.public_url(art_path)

    def get_persisted_mech(self, mech_id: str) -> dict[str, object] | None:
        row = self.db.get_mech(mech_id)
        if row is None:
            return None
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "object_id": row["object_id"],
            "name": row["name"],
            "form": row["form"],
            "stats": row["stats"],
            "art_url": row.get("art_url"),
        }

    def list_user_mechs(self, user_id: str) -> list[dict[str, object]]:
        return self.db.list_mechs(user_id)

    def create_tactic(self, user_id: str, tactic: TacticSet) -> dict[str, object]:
        tactic_id = str(uuid.uuid4())
        payload = tactic_set_to_payload(tactic)
        self.db.save_tactic(user_id, tactic_id, payload)
        return {"id": tactic_id, **payload}

    def get_tactic_set(self, tactic_id: str) -> TacticSet | None:
        row = self.db.get_tactic(tactic_id)
        if row is None:
            return None
        return tactic_set_from_payload(row["payload"])

    def update_tactic(self, tactic_id: str, tactic: TacticSet) -> dict[str, object]:
        payload = tactic_set_to_payload(tactic)
        self.db.update_tactic(tactic_id, payload)
        return {"id": tactic_id, **payload}

    def simulate_tactic(self, tactic_id: str, mech_id: str, seed: int = 0) -> BattleResult:
        """docs/07 POST /tactics/{id}/simulate: テストバトル。

        Runs the tactic against the demo CPU team without touching rating or
        persisted battle history — a scratch sandbox for tactic tuning.
        """
        tactic = self.get_tactic_set(tactic_id)
        if tactic is None:
            raise ValueError(f"tactic not found: {tactic_id}")
        mech = self._load_mech(mech_id)
        player_team = Team(id="sim-player", name="Simulation", slots=[TeamSlot(mech=mech, position=Position.FRONT)])
        player_tactics = {Position.FRONT: tactic}
        cpu_team, cpu_tactics = build_demo_cpu_team()
        return BattleEngine().simulate(player_team, player_tactics, cpu_team, cpu_tactics, seed=seed)

    def create_team(
        self,
        user_id: str,
        name: str,
        front_mech_id: str,
        front_tactic_id: str,
        middle_mech_id: str,
        middle_tactic_id: str,
        back_mech_id: str,
        back_tactic_id: str,
    ) -> TeamRow:
        team = TeamRow(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            front_mech_id=front_mech_id,
            front_tactic_id=front_tactic_id,
            middle_mech_id=middle_mech_id,
            middle_tactic_id=middle_tactic_id,
            back_mech_id=back_mech_id,
            back_tactic_id=back_tactic_id,
        )
        self.db.save_team(team)
        return team

    def update_team(
        self,
        team_id: str,
        user_id: str,
        name: str,
        front_mech_id: str,
        front_tactic_id: str,
        middle_mech_id: str,
        middle_tactic_id: str,
        back_mech_id: str,
        back_tactic_id: str,
    ) -> TeamRow:
        team = TeamRow(
            id=team_id,
            user_id=user_id,
            name=name,
            front_mech_id=front_mech_id,
            front_tactic_id=front_tactic_id,
            middle_mech_id=middle_mech_id,
            middle_tactic_id=middle_tactic_id,
            back_mech_id=back_mech_id,
            back_tactic_id=back_tactic_id,
        )
        self.db.update_team(team)
        return team

    def load_team_for_battle(self, team_row: TeamRow) -> tuple[Team, dict[Position, TacticSet]]:
        slots: list[TeamSlot] = []
        tactics: dict[Position, TacticSet] = {}
        mapping = [
            (Position.FRONT, team_row.front_mech_id, team_row.front_tactic_id),
            (Position.MIDDLE, team_row.middle_mech_id, team_row.middle_tactic_id),
            (Position.BACK, team_row.back_mech_id, team_row.back_tactic_id),
        ]
        for position, mech_id, tactic_id in mapping:
            mech = self._load_mech(mech_id)
            tactic = self.get_tactic_set(tactic_id)
            if tactic is None:
                raise ValueError(f"tactic not found: {tactic_id}")
            slots.append(TeamSlot(mech=mech, position=position))
            tactics[position] = tactic
        return Team(id=team_row.id, name=team_row.name, slots=slots), tactics

    def queue_for_match(self, team_id: str) -> None:
        self.db.queue_team(team_id)

    def find_opponent(self, user_id: str, rating: int) -> TeamRow | None:
        return self.db.find_queued_opponent(user_id, rating)

    # docs/09 信頼モデル / PLAN D-007: ランク戦の公平性のため seed は常にサーバーが生成する。
    # クライアント送信 seed（後方互換のため受け付けはするが無視する）は使わない。
    _SEED_BITS = 31

    def generate_battle_seed(self) -> int:
        return secrets.randbits(self._SEED_BITS)

    def run_ranked_battle(
        self,
        player_a: UserRow,
        team_a: TeamRow,
        opponent_team: Team | None,
        opponent_tactics: dict[Position, TacticSet] | None,
        opponent_user: UserRow | None,
        opponent_team_row: TeamRow | None,
    ):
        player_team, player_tactics = self.load_team_for_battle(team_a)
        if opponent_team is None or opponent_tactics is None:
            opponent_team, opponent_tactics = build_demo_cpu_team()
            opponent_team = Team(id="cpu", name="CPU", slots=opponent_team.slots)

        seed = self.generate_battle_seed()
        battle = self.run_battle(player_team, player_tactics, opponent_team, opponent_tactics, seed)
        self.db.save_battle(
            battle.id,
            player_a.id,
            opponent_user.id if opponent_user else None,
            team_a.id,
            opponent_team_row.id if opponent_team_row else None,
            seed,
            battle.result.winner_team_id,
            battle.result.turns,
            battle.result.format_log(),
            battle_log_to_payload(battle.result.log_entries),
        )

        if battle.result.winner_team_id == player_team.id:
            self.db.update_rating(player_a.id, 25 if opponent_user else 10)
            if opponent_user:
                self.db.update_rating(opponent_user.id, -15)
        elif battle.result.winner_team_id == opponent_team.id and opponent_user:
            self.db.update_rating(opponent_user.id, 25)
            self.db.update_rating(player_a.id, -15)
        elif battle.result.winner_team_id == "cpu":
            self.db.update_rating(player_a.id, -5)

        if opponent_team_row:
            self.db.dequeue_team(team_a.id)
            self.db.dequeue_team(opponent_team_row.id)

        return battle

    # docs/06 Entitlement案の全量。docs/07 の POST /billing/sync、および Webhook 個別付与
    # （PLAN D-005）はこの集合に限定して反映する（未知キーは無視し、戦闘系の権限拡張を防ぐ）。
    KNOWN_ENTITLEMENT_KEYS = (
        "premium_tactics",
        "extra_tactic_slots",
        "battle_log_summary",
        "cosmetic_pack_access",
        "generation_boost",
    )

    # docs/06 Webhook イベント処理（MVP）表に対応。
    _GRANT_EVENT_TYPES = frozenset(
        {"INITIAL_PURCHASE", "RENEWAL", "NON_RENEWING_PURCHASE", "PRODUCT_CHANGE", "UNCANCELLATION"}
    )
    _REVOKE_EVENT_TYPES = frozenset({"CANCELLATION", "EXPIRATION"})

    def sync_client_entitlements(self, user_id: str, active_keys: list[str]) -> dict[str, object]:
        """docs/07 POST /billing/sync: クライアントの CustomerInfo とサーバー状態の同期。

        RevenueCat Webhook が権威ソースであり、これはWebhook未達時のフォールバック
        （docs/08 リスク対策）。既知のEntitlementキーのみを反映し、クライアント申告を
        そのまま鵜呑みにして未知の権限を付与することはない。
        """
        active_set = {key for key in active_keys if key in self.KNOWN_ENTITLEMENT_KEYS}
        for key in self.KNOWN_ENTITLEMENT_KEYS:
            self.db.set_entitlement(user_id, key, key in active_set)
        return {"entitlements": self.db.get_entitlements(user_id)}

    def apply_revenuecat_event(
        self,
        event_id: str,
        app_user_id: str,
        event_type: str,
        entitlement_ids: list[str],
    ) -> dict[str, object]:
        """docs/06 Webhook イベント処理（PLAN D-005）。

        RevenueCat は商品(Product)↔Entitlement の対応をダッシュボード側で解決し、Webhook イベントの
        `entitlement_ids` に「そのイベントで有効/無効になる Entitlement」を含めて送ってくる。
        そのためサーバー側で商品IDごとの対応表をハードコードする必要はなく、`entitlement_ids` を
        そのまま個別に反映すればよい（商品↔Entitlement 対応自体の確定は外部設定。
        `config/revenuecat_pending_setup.json` 参照）。
        `event_id` を用いた冪等性チェックにより、Webhook 再送時の二重付与/二重失効を防ぐ。
        """
        if event_type not in self._GRANT_EVENT_TYPES and event_type not in self._REVOKE_EVENT_TYPES:
            return {"applied": False, "reason": "ignored_event"}

        user = self.db.get_user(app_user_id)
        if user is None:
            return {"applied": False, "reason": "user_not_found"}

        if self.db.is_webhook_event_processed(event_id):
            return {"applied": False, "reason": "duplicate_event"}

        if not entitlement_ids:
            return {"applied": False, "reason": "missing_entitlement_ids"}

        known_keys = [key for key in entitlement_ids if key in self.KNOWN_ENTITLEMENT_KEYS]
        if not known_keys:
            return {"applied": False, "reason": "no_known_entitlements"}

        is_active = event_type in self._GRANT_EVENT_TYPES
        for key in known_keys:
            self.db.set_entitlement(app_user_id, key, is_active)
        self.db.mark_webhook_event_processed(event_id, event_type, app_user_id)
        return {"applied": True, "entitlements": self.db.get_entitlements(app_user_id)}

    def _ensure_capture_quota(self, user_id: str) -> None:
        quotas = self.get_user_quotas(user_id)
        if quotas["captures"]["remaining"] <= 0:
            raise QuotaExceededError("captures")

    def _ensure_mech_quota(self, user_id: str) -> None:
        quotas = self.get_user_quotas(user_id)
        if quotas["mechs"]["remaining"] <= 0:
            raise QuotaExceededError("mechs")

    def _load_mech(self, mech_id: str) -> Mech:
        row = self.db.get_mech(mech_id)
        if row is None:
            record = self.mechs.get(mech_id)
            if record is None:
                raise ValueError(f"mech not found: {mech_id}")
            return record.mech.clone_for_battle()
        stats = row["stats"]
        return Mech(
            id=row["id"],
            name=row["name"],
            form=MechForm(row["form"]),
            stats=MechStats(**stats),
        ).clone_for_battle()

    @staticmethod
    def _mech_response(mech_id: str, object_id: str, mech: Mech) -> dict[str, object]:
        return {
            "id": mech_id,
            "object_id": object_id,
            "name": mech.name,
            "form": mech.form.value,
            "form_inference_version": FORM_INFERENCE_VERSION,
            "stats": mech.stats.__dict__,
        }

    def get_battle_record(self, battle_id: str) -> dict[str, object] | None:
        persisted = self.db.get_battle(battle_id)
        if persisted is not None:
            return persisted
        record = self.battles.get(battle_id)
        if record is None:
            return None
        result = record.result
        return {
            "id": record.id,
            # docs/07 所有権: デモ用 POST /battles（永続チーム不要）はユーザーに紐づかないため
            # player_a_id は常に None。GET /battles/{id} 側で「所有者なし = 認証済みなら誰でも
            # 閲覧可」として扱う（PLAN D-008）。
            "player_a_id": None,
            "player_b_id": None,
            "seed": result.seed,
            "winner_team_id": result.winner_team_id,
            "turns": result.turns,
            "log": result.format_log(),
            # PLAN D-003: 永続 DB 経由と同じ構造化ログ形式をデモ戦でも返す。
            "log_entries": battle_log_to_payload(result.log_entries),
        }

    def get_object_analysis(self, object_id: str) -> dict[str, object] | None:
        record = self.objects.get(object_id)
        if record is not None:
            return {"id": record.id, "info_score": record.info_score, "features": record.features.__dict__}
        extracted = self.db.get_extracted_object(object_id)
        if extracted is None:
            return None
        return {
            "id": extracted["id"],
            "info_score": extracted["info_score"],
            "features": extracted["features"],
            "quality": extracted["quality"],
        }
