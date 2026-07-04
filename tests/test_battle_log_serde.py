from photo_mecha_battle.battle import DamageEvent, TurnLogEntry
from photo_mecha_battle.battle_log_serde import (
    battle_log_from_payload,
    battle_log_to_payload,
    damage_event_from_payload,
    damage_event_to_payload,
    log_entry_from_payload,
    log_entry_to_payload,
)
from photo_mecha_battle.models import Position
from photo_mecha_battle.tactics import ActionType


def test_damage_event_round_trips():
    event = DamageEvent(target_id="e1", target_name="Enemy", damage=42, defeated=True)
    payload = damage_event_to_payload(event)
    assert payload == {"target_id": "e1", "target_name": "Enemy", "damage": 42, "defeated": True}
    assert damage_event_from_payload(payload) == event


def test_log_entry_round_trips_with_damage_events():
    entry = TurnLogEntry(
        turn=3,
        actor_team="a",
        actor_position=Position.BACK,
        actor_name="Sniper",
        condition_label="自分ENが80以上",
        action=ActionType.SNIPER_SHOT,
        damage_events=[DamageEvent("e1", "Enemy", 41, True)],
        note="",
    )
    payload = log_entry_to_payload(entry)
    assert payload["actor_position"] == "back"
    assert payload["action"] == "sniper_shot"
    assert payload["damage_events"] == [
        {"target_id": "e1", "target_name": "Enemy", "damage": 41, "defeated": True}
    ]
    assert log_entry_from_payload(payload) == entry


def test_log_entry_round_trips_with_note_only():
    entry = TurnLogEntry(
        turn=1,
        actor_team="b",
        actor_position=Position.FRONT,
        actor_name="Guard",
        condition_label="自分HPが30%以下",
        action=ActionType.DEFEND,
        note="防御態勢を取る",
    )
    payload = log_entry_to_payload(entry)
    assert payload["damage_events"] == []
    assert payload["note"] == "防御態勢を取る"
    assert log_entry_from_payload(payload) == entry


def test_battle_log_round_trips_a_full_turn_sequence():
    entries = [
        TurnLogEntry(
            turn=1,
            actor_team="a",
            actor_position=Position.FRONT,
            actor_name="A",
            condition_label="常時",
            action=ActionType.NORMAL_ATTACK,
            damage_events=[DamageEvent("b-front", "B", 12, False)],
        ),
        TurnLogEntry(
            turn=1,
            actor_team="b",
            actor_position=Position.FRONT,
            actor_name="B",
            condition_label="基本行動",
            action=ActionType.NORMAL_ATTACK,
            damage_events=[DamageEvent("a-front", "A", 9, False)],
        ),
    ]
    payload = battle_log_to_payload(entries)
    assert len(payload) == 2
    assert battle_log_from_payload(payload) == entries
