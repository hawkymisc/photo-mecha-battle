from __future__ import annotations

import uuid

from photo_mecha_battle.api.database import Database, TeamRow, UserRow
from photo_mecha_battle.api.store import InMemoryStore, build_demo_cpu_team
from photo_mecha_battle.models import Mech, MechForm, MechStats, Position, Team, TeamSlot
from photo_mecha_battle.tactics import TacticSet
from photo_mecha_battle.tactics_serde import tactic_set_from_payload, tactic_set_to_payload


class GameStore:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._session = InMemoryStore()

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

    def detect_objects(self, capture_id: str):
        return self._session.detect_objects(capture_id)

    def segment_object(self, capture_id: str, label: str):
        return self._session.segment_object(capture_id, label)

    def create_mech(self, object_id: str, form: MechForm, name: str):
        return self._session.create_mech(object_id, form, name)

    def run_battle(self, team_a, tactics_a, team_b, tactics_b, seed: int):
        return self._session.run_battle(team_a, tactics_a, team_b, tactics_b, seed)

    def register_user(self, name: str) -> UserRow:
        return self.db.create_user(name)

    def authenticate(self, token: str) -> UserRow | None:
        return self.db.get_user_by_token(token)

    def create_mech_for_user(self, user_id: str, object_id: str, form: MechForm, name: str) -> dict[str, object]:
        record = self.create_mech(object_id, form, name)
        self.db.save_mech(
            user_id,
            record.id,
            record.object_id,
            record.mech.form.value,
            record.mech.name,
            record.mech.stats.__dict__,
        )
        return self._mech_response(record.id, record.object_id, record.mech)

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
            "seed": result.seed,
            "winner_team_id": result.winner_team_id,
            "turns": result.turns,
            "log": result.format_log(),
        }
