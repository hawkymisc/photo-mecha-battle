from __future__ import annotations

import uuid
from pathlib import Path

from photo_mecha_battle.api.capture_pipeline import (
    create_capture_from_bytes,
    detect_for_capture,
    segment_for_capture,
)
from photo_mecha_battle.api.database import Database, TeamRow, UserRow
from photo_mecha_battle.api.image_storage import ImageStorage
from photo_mecha_battle.api.limits import limits_for_user
from photo_mecha_battle.api.store import InMemoryStore, CaptureRecord, ObjectRecord, build_demo_cpu_team
from photo_mecha_battle.battle import BattleEngine, BattleResult
from photo_mecha_battle.models import Mech, MechForm, MechStats, Position, Team, TeamSlot
from photo_mecha_battle.tactics import TacticSet
from photo_mecha_battle.tactics_serde import tactic_set_from_payload, tactic_set_to_payload
from photo_mecha_battle.vision.mech_art import render_mech_art


class QuotaExceededError(Exception):
    def __init__(self, resource: str) -> None:
        self.resource = resource
        super().__init__(f"quota exceeded: {resource}")


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

    def create_mech(self, object_id: str, form: MechForm, name: str):
        return self._session.create_mech(object_id, form, name)

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

    def create_mech_for_user(self, user_id: str, object_id: str, form: MechForm, name: str) -> dict[str, object]:
        self._ensure_mech_quota(user_id)
        record = self.create_mech(object_id, form, name)
        art_url = self._render_and_store_art(record.id, object_id, form)
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

    def run_ranked_battle(
        self,
        player_a: UserRow,
        team_a: TeamRow,
        opponent_team: Team | None,
        opponent_tactics: dict[Position, TacticSet] | None,
        opponent_user: UserRow | None,
        opponent_team_row: TeamRow | None,
        seed: int,
    ):
        player_team, player_tactics = self.load_team_for_battle(team_a)
        if opponent_team is None or opponent_tactics is None:
            opponent_team, opponent_tactics = build_demo_cpu_team()
            opponent_team = Team(id="cpu", name="CPU", slots=opponent_team.slots)

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

    # docs/06 Product/Package案: Monthly/Annual Premium = 自然言語戦術生成 + 保存枠拡張 +
    # ログ要約 + 生成クォータ拡大。いずれも利便性・表現機能であり、戦闘性能や戦術スロット数・
    # 使用可能条件/行動には影響しない（generation_boost は「試行回数」のみを増やす。docs/06 公平性の整理）。
    # 商品↔Entitlement の個別対応が RevenueCat ダッシュボードで確定するまでは一括付与の簡易実装とする
    # （PLAN D-005）。
    _PREMIUM_BUNDLE_ENTITLEMENTS = (
        "premium_tactics",
        "extra_tactic_slots",
        "battle_log_summary",
        "generation_boost",
    )

    # docs/06 Entitlement案の全量。docs/07 の POST /billing/sync はこの集合に限定して
    # クライアント CustomerInfo を反映する（未知キーは無視し、戦闘系の権限拡張を防ぐ）。
    KNOWN_ENTITLEMENT_KEYS = (
        "premium_tactics",
        "extra_tactic_slots",
        "battle_log_summary",
        "cosmetic_pack_access",
        "generation_boost",
    )

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

    def apply_revenuecat_event(self, app_user_id: str, event_type: str) -> dict[str, object]:
        user = self.db.get_user(app_user_id)
        if user is None:
            return {"applied": False, "reason": "user_not_found"}
        if event_type in {"INITIAL_PURCHASE", "RENEWAL", "NON_RENEWING_PURCHASE", "PRODUCT_CHANGE"}:
            for key in self._PREMIUM_BUNDLE_ENTITLEMENTS:
                self.db.set_entitlement(app_user_id, key, True)
            return {"applied": True, "entitlements": self.db.get_entitlements(app_user_id)}
        if event_type in {"CANCELLATION", "EXPIRATION"}:
            for key in self._PREMIUM_BUNDLE_ENTITLEMENTS:
                self.db.set_entitlement(app_user_id, key, False)
            return {"applied": True, "entitlements": self.db.get_entitlements(app_user_id)}
        return {"applied": False, "reason": "ignored_event"}

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
