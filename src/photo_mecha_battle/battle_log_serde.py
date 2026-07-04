"""docs/05 バトルログ「ログエントリの構造（正）」の JSON シリアライズ。

PLAN D-003: `battles.log_text`（整形済みテキストのみ）に加えて構造化ログを保存し、
クライアント演出再生（docs/09）が turn / actor / condition_label / action / damage_events
を個別に参照できるようにする。
"""

from __future__ import annotations

from typing import Any

from photo_mecha_battle.battle import DamageEvent, TurnLogEntry
from photo_mecha_battle.models import Position
from photo_mecha_battle.tactics import ActionType


def damage_event_to_payload(event: DamageEvent) -> dict[str, Any]:
    return {
        "target_id": event.target_id,
        "target_name": event.target_name,
        "damage": event.damage,
        "defeated": event.defeated,
    }


def damage_event_from_payload(payload: dict[str, Any]) -> DamageEvent:
    return DamageEvent(
        target_id=payload["target_id"],
        target_name=payload["target_name"],
        damage=payload["damage"],
        defeated=payload["defeated"],
    )


def log_entry_to_payload(entry: TurnLogEntry) -> dict[str, Any]:
    return {
        "turn": entry.turn,
        "actor_team": entry.actor_team,
        "actor_position": entry.actor_position.value,
        "actor_name": entry.actor_name,
        "condition_label": entry.condition_label,
        "action": entry.action.value,
        "damage_events": [damage_event_to_payload(event) for event in entry.damage_events],
        "note": entry.note,
    }


def log_entry_from_payload(payload: dict[str, Any]) -> TurnLogEntry:
    return TurnLogEntry(
        turn=payload["turn"],
        actor_team=payload["actor_team"],
        actor_position=Position(payload["actor_position"]),
        actor_name=payload["actor_name"],
        condition_label=payload["condition_label"],
        action=ActionType(payload["action"]),
        damage_events=[damage_event_from_payload(item) for item in payload.get("damage_events", [])],
        note=payload.get("note", ""),
    )


def battle_log_to_payload(entries: list[TurnLogEntry]) -> list[dict[str, Any]]:
    return [log_entry_to_payload(entry) for entry in entries]


def battle_log_from_payload(payload: list[dict[str, Any]]) -> list[TurnLogEntry]:
    return [log_entry_from_payload(item) for item in payload]
