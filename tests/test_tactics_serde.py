from photo_mecha_battle.models import MechForm
from photo_mecha_battle.tactics import ActionType, Condition, ConditionKind, TacticSet, TacticSlot
from photo_mecha_battle.tactics_serde import tactic_set_from_payload, tactic_set_to_payload


def test_tactic_roundtrip_preserves_slots():
    from photo_mecha_battle.tactics import TacticPreset, build_preset

    original = build_preset(TacticPreset.BOMBARDMENT)
    payload = tactic_set_to_payload(original)
    restored = tactic_set_from_payload(payload)
    assert restored.name == original.name
    assert len(restored.slots) == len(original.slots)
    assert restored.fallback_action == original.fallback_action
    assert restored.slots[0].action == original.slots[0].action


def test_target_form_threshold_roundtrip():
    tactic = TacticSet.from_slots(
        "form-test",
        [TacticSlot(Condition(ConditionKind.TARGET_FORM, MechForm.BIRD), ActionType.ACCURACY_ATTACK)],
        ActionType.NORMAL_ATTACK,
    )
    payload = tactic_set_to_payload(tactic)
    restored = tactic_set_from_payload(payload)
    assert restored.slots[0].condition.threshold == MechForm.BIRD
