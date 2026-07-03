from photo_mecha_battle.api.store import InMemoryStore, _features_for_label
from photo_mecha_battle.models import MechForm


def test_detect_objects_returns_candidate_for_capture():
    store = InMemoryStore()
    capture = store.create_capture("umbrella")
    candidates = store.detect_objects(capture.id)
    assert candidates[0]["label"] == "umbrella"
    assert candidates[0]["confidence"] == 0.91


def test_unknown_label_uses_default_features():
    features = _features_for_label("unknown-object")
    umbrella = _features_for_label("umbrella")
    assert features == umbrella


def test_stone_label_has_rounder_shape_than_umbrella():
    stone = _features_for_label("stone")
    umbrella = _features_for_label("umbrella")
    assert stone.roundness > umbrella.roundness


def test_create_mech_persists_in_store():
    store = InMemoryStore()
    capture = store.create_capture()
    obj = store.segment_object(capture.id, "stone")
    record = store.create_mech(obj.id, MechForm.BEAST, "Test")
    assert store.mechs[record.id].mech.name == "Test"
