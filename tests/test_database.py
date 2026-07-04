from datetime import UTC, datetime

from photo_mecha_battle.api.database import Database


def test_user_and_ranking_persist_across_connections():
    db = Database(":memory:")
    user = db.create_user("Persist")
    db.save_mech(user.id, "m1", "obj1", "bird", "Mech", {"hp": 10, "atk": 10, "defense": 10, "spd": 10, "tec": 10, "en": 10, "luck": 0})
    db.update_rating(user.id, 50)
    ranking = db.get_ranking()
    assert ranking[0]["rating"] == 1050
    mechs = db.list_mechs(user.id)
    assert mechs[0]["name"] == "Mech"


def test_save_and_get_battle_includes_structured_log():
    """PLAN D-003 / docs/05: log_text に加えて構造化ログ（log_entries）を保存・取得できる。"""
    db = Database(":memory:")
    user_a = db.create_user("PlayerA")
    log_entries = [
        {
            "turn": 1,
            "actor_team": "a",
            "actor_position": "front",
            "actor_name": "Mech",
            "condition_label": "常時",
            "action": "normal_attack",
            "damage_events": [
                {"target_id": "e", "target_name": "Enemy", "damage": 10, "defeated": False}
            ],
            "note": "",
        }
    ]
    db.save_battle("battle-1", user_a.id, None, "team-a", None, 42, "team-a", 1, "Turn 1\n...", log_entries)
    fetched = db.get_battle("battle-1")
    assert fetched["log_entries"] == log_entries
    assert fetched["log"] == "Turn 1\n..."
    db.close()


def test_get_battle_falls_back_when_log_json_missing():
    """PLAN D-003: log_json 列を持たない（マイグレーション前の）既存行でも読み出せる。"""
    db = Database(":memory:")
    user_a = db.create_user("Legacy")
    db._conn.execute(
        """
        INSERT INTO battles (
            id, player_a_id, player_b_id, team_a_id, team_b_id,
            seed, winner_team_id, turns, log_text, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "legacy-battle",
            user_a.id,
            None,
            "team-a",
            None,
            1,
            "team-a",
            1,
            "Turn 1\nlegacy text",
            datetime.now(UTC).isoformat(),
        ),
    )
    db._conn.commit()

    fetched = db.get_battle("legacy-battle")
    assert fetched["log_entries"] is None
    assert fetched["log"] == "Turn 1\nlegacy text"
    db.close()
