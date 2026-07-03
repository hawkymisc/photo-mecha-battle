from __future__ import annotations

from photo_mecha_battle.models import MechForm
from photo_mecha_battle.tactics import (
    ActionType,
    Condition,
    ConditionKind,
    TacticSet,
    TacticSlot,
)


def _serialize_threshold(threshold: float | int | MechForm | None) -> str | int | float | None:
    if isinstance(threshold, MechForm):
        return threshold.value
    return threshold


def _deserialize_threshold(
    kind: ConditionKind,
    threshold: str | int | float | None,
) -> float | int | MechForm | None:
    if kind == ConditionKind.TARGET_FORM and isinstance(threshold, str):
        return MechForm(threshold)
    return threshold


def tactic_set_to_payload(tactic: TacticSet) -> dict[str, object]:
    return {
        "name": tactic.name,
        "slots": [
            {
                "condition": {
                    "kind": slot.condition.kind.value,
                    "threshold": _serialize_threshold(slot.condition.threshold),
                },
                "action": slot.action.value,
            }
            for slot in tactic.slots
        ],
        "fallback_action": tactic.fallback_action.value,
    }


def tactic_set_from_payload(payload: dict[str, object]) -> TacticSet:
    slots: list[TacticSlot] = []
    for raw_slot in payload["slots"]:  # type: ignore[index]
        condition_data = raw_slot["condition"]
        kind = ConditionKind(condition_data["kind"])
        threshold = _deserialize_threshold(kind, condition_data.get("threshold"))
        slots.append(
            TacticSlot(
                condition=Condition(kind=kind, threshold=threshold),
                action=ActionType(raw_slot["action"]),
            )
        )
    return TacticSet.from_slots(
        str(payload["name"]),
        slots,
        ActionType(str(payload["fallback_action"])),
    )
