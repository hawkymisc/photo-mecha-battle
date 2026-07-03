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


@pytest.mark.parametrize(
    ("kind", "threshold", "expected"),
    [
        (ConditionKind.TARGET_DEF_HIGH, None, "相手DEFが高い"),
        (ConditionKind.TARGET_SPD_HIGH, None, "相手SPDが高い"),
        (ConditionKind.TARGET_DEFENDING, None, "相手が防御中"),
        (ConditionKind.TARGET_CLOSE_RANGE, None, "相手が接近型"),
        (ConditionKind.TARGET_BACKLINE_PRESENT, None, "相手後衛が残っている"),
        (ConditionKind.ENEMIES_REMAINING_AT_LEAST, 2, "敵が複数残っている"),
        (ConditionKind.ALWAYS, None, "常時"),
        (ConditionKind.SELF_EN_BELOW, 40, "自分ENが40未満"),
        (ConditionKind.TARGET_HP_BELOW, 30, "相手HPが30%以下"),
    ],
)
def test_all_condition_labels(kind, threshold, expected):
    assert Condition(kind, threshold).label() == expected
