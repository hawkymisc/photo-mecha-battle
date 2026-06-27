from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class UserRow:
    id: str
    name: str
    token: str
    rating: int


@dataclass(frozen=True)
class TeamRow:
    id: str
    user_id: str
    name: str
    front_mech_id: str
    front_tactic_id: str
    middle_mech_id: str
    middle_tactic_id: str
    back_mech_id: str
    back_tactic_id: str


class Database:
    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE,
                rating INTEGER NOT NULL DEFAULT 1000,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS mechs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                object_id TEXT NOT NULL,
                form TEXT NOT NULL,
                name TEXT NOT NULL,
                stats_json TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS tactic_sets (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS teams (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                front_mech_id TEXT NOT NULL,
                front_tactic_id TEXT NOT NULL,
                middle_mech_id TEXT NOT NULL,
                middle_tactic_id TEXT NOT NULL,
                back_mech_id TEXT NOT NULL,
                back_tactic_id TEXT NOT NULL,
                queued INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS battles (
                id TEXT PRIMARY KEY,
                player_a_id TEXT NOT NULL,
                player_b_id TEXT,
                team_a_id TEXT NOT NULL,
                team_b_id TEXT,
                seed INTEGER NOT NULL,
                winner_team_id TEXT,
                turns INTEGER NOT NULL,
                log_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_entitlements (
                user_id TEXT NOT NULL,
                entitlement_key TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, entitlement_key)
            );
            """
        )
        self._conn.commit()

    def create_user(self, name: str) -> UserRow:
        user_id = str(uuid.uuid4())
        token = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        self._conn.execute(
            "INSERT INTO users (id, name, token, rating, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, token, 1000, created_at),
        )
        self._conn.commit()
        return UserRow(id=user_id, name=name, token=token, rating=1000)

    def get_user_by_token(self, token: str) -> UserRow | None:
        row = self._conn.execute("SELECT * FROM users WHERE token = ?", (token,)).fetchone()
        if row is None:
            return None
        return UserRow(id=row["id"], name=row["name"], token=row["token"], rating=row["rating"])

    def get_user(self, user_id: str) -> UserRow | None:
        row = self._conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        return UserRow(id=row["id"], name=row["name"], token=row["token"], rating=row["rating"])

    def update_rating(self, user_id: str, delta: int) -> int:
        self._conn.execute(
            "UPDATE users SET rating = MAX(0, rating + ?) WHERE id = ?",
            (delta, user_id),
        )
        self._conn.commit()
        user = self.get_user(user_id)
        assert user is not None
        return user.rating

    def save_mech(self, user_id: str, mech_id: str, object_id: str, form: str, name: str, stats: dict[str, int]) -> None:
        self._conn.execute(
            "INSERT INTO mechs (id, user_id, object_id, form, name, stats_json) VALUES (?, ?, ?, ?, ?, ?)",
            (mech_id, user_id, object_id, form, name, json.dumps(stats)),
        )
        self._conn.commit()

    def get_mech(self, mech_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM mechs WHERE id = ?", (mech_id,)).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "object_id": row["object_id"],
            "form": row["form"],
            "name": row["name"],
            "stats": json.loads(row["stats_json"]),
        }

    def list_mechs(self, user_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM mechs WHERE user_id = ? ORDER BY rowid", (user_id,)).fetchall()
        return [
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "object_id": row["object_id"],
                "form": row["form"],
                "name": row["name"],
                "stats": json.loads(row["stats_json"]),
            }
            for row in rows
        ]

    def save_tactic(self, user_id: str, tactic_id: str, payload: dict[str, object]) -> None:
        self._conn.execute(
            "INSERT INTO tactic_sets (id, user_id, payload_json) VALUES (?, ?, ?)",
            (tactic_id, user_id, json.dumps(payload)),
        )
        self._conn.commit()

    def get_tactic(self, tactic_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM tactic_sets WHERE id = ?", (tactic_id,)).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "payload": json.loads(row["payload_json"]),
        }

    def update_tactic(self, tactic_id: str, payload: dict[str, object]) -> None:
        self._conn.execute(
            "UPDATE tactic_sets SET payload_json = ? WHERE id = ?",
            (json.dumps(payload), tactic_id),
        )
        self._conn.commit()

    def save_team(self, team: TeamRow) -> None:
        self._conn.execute(
            """
            INSERT INTO teams (
                id, user_id, name,
                front_mech_id, front_tactic_id,
                middle_mech_id, middle_tactic_id,
                back_mech_id, back_tactic_id,
                queued
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                team.id,
                team.user_id,
                team.name,
                team.front_mech_id,
                team.front_tactic_id,
                team.middle_mech_id,
                team.middle_tactic_id,
                team.back_mech_id,
                team.back_tactic_id,
            ),
        )
        self._conn.commit()

    def get_team(self, team_id: str) -> TeamRow | None:
        row = self._conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
        if row is None:
            return None
        return TeamRow(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            front_mech_id=row["front_mech_id"],
            front_tactic_id=row["front_tactic_id"],
            middle_mech_id=row["middle_mech_id"],
            middle_tactic_id=row["middle_tactic_id"],
            back_mech_id=row["back_mech_id"],
            back_tactic_id=row["back_tactic_id"],
        )

    def queue_team(self, team_id: str) -> None:
        self._conn.execute("UPDATE teams SET queued = 1 WHERE id = ?", (team_id,))
        self._conn.commit()

    def find_queued_opponent(self, user_id: str, rating: int) -> TeamRow | None:
        row = self._conn.execute(
            """
            SELECT teams.* FROM teams
            JOIN users ON users.id = teams.user_id
            WHERE teams.queued = 1
              AND teams.user_id != ?
              AND ABS(users.rating - ?) <= 300
            ORDER BY ABS(users.rating - ?)
            LIMIT 1
            """,
            (user_id, rating, rating),
        ).fetchone()
        if row is None:
            return None
        return self.get_team(row["id"])

    def dequeue_team(self, team_id: str) -> None:
        self._conn.execute("UPDATE teams SET queued = 0 WHERE id = ?", (team_id,))
        self._conn.commit()

    def save_battle(
        self,
        battle_id: str,
        player_a_id: str,
        player_b_id: str | None,
        team_a_id: str,
        team_b_id: str | None,
        seed: int,
        winner_team_id: str | None,
        turns: int,
        log_text: str,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO battles (
                id, player_a_id, player_b_id, team_a_id, team_b_id,
                seed, winner_team_id, turns, log_text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                battle_id,
                player_a_id,
                player_b_id,
                team_a_id,
                team_b_id,
                seed,
                winner_team_id,
                turns,
                log_text,
                datetime.now(UTC).isoformat(),
            ),
        )
        self._conn.commit()

    def get_battle(self, battle_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM battles WHERE id = ?", (battle_id,)).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "seed": row["seed"],
            "winner_team_id": row["winner_team_id"],
            "turns": row["turns"],
            "log": row["log_text"],
        }

    def get_ranking(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT name, rating FROM users ORDER BY rating DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{"team_name": row["name"], "rating": row["rating"]} for row in rows]

    def set_entitlement(self, user_id: str, entitlement_key: str, is_active: bool) -> None:
        self._conn.execute(
            """
            INSERT INTO user_entitlements (user_id, entitlement_key, is_active)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, entitlement_key) DO UPDATE SET is_active = excluded.is_active
            """,
            (user_id, entitlement_key, int(is_active)),
        )
        self._conn.commit()

    def get_entitlements(self, user_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT entitlement_key, is_active FROM user_entitlements WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return [{"key": row["entitlement_key"], "is_active": bool(row["is_active"])} for row in rows]
