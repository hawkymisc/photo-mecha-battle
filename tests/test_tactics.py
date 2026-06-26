import pytest

from photo_mecha_battle.tactics import (
    ActionType,
    Condition,
    ConditionKind,
    TacticPreset,
    TacticSet,
    TacticSlot,
    build_preset,
)


def test_all_presets_have_four_slots_and_fallback():
    for preset in TacticPreset:
        tactic = build_preset(preset)
        assert len(tactic.slots) == 4
        assert isinstance(tactic.fallback_action, ActionType)


def test_tactic_set_rejects_more_than_four_slots():
    slots = [
        TacticSlot(Condition(ConditionKind.ALWAYS), ActionType.NORMAL_ATTACK)
        for _ in range(5)
    ]
    with pytest.raises(ValueError, match="at most 4 slots"):
        TacticSet.from_slots("too many", slots, ActionType.NORMAL_ATTACK)


def test_condition_labels_are_human_readable():
    tactic = build_preset(TacticPreset.SNIPER)
    labels = [slot.condition.label() for slot in tactic.slots]
    assert "相手が鳥形" in labels
    assert "自分ENが80以上" in labels
