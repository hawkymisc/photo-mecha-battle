import pytest

from photo_mecha_battle.features import FeatureVector
from photo_mecha_battle.mech_stats import compute_info_score, derive_stats
from photo_mecha_battle.models import MechForm


def sample_features(**overrides: float) -> FeatureVector:
    defaults = {
        "visual_entropy": 0.6,
        "edge_complexity": 0.5,
        "color_diversity": 0.4,
        "shape_complexity": 0.45,
        "semantic_rarity": 0.3,
        "capture_quality": 0.8,
        "size_balance": 0.7,
        "area": 0.5,
        "elongation": 0.4,
        "roundness": 0.5,
        "symmetry": 0.6,
    }
    defaults.update(overrides)
    return FeatureVector(**defaults)


def test_info_score_matches_docs_weights():
    features = sample_features(
        visual_entropy=1.0,
        edge_complexity=0.0,
        color_diversity=0.0,
        shape_complexity=0.0,
        semantic_rarity=0.0,
        capture_quality=0.0,
        size_balance=0.0,
    )
    assert compute_info_score(features) == pytest.approx(0.25)


def test_bird_form_favors_speed_over_beast():
    features = sample_features()
    bird = derive_stats(features, MechForm.BIRD)
    beast = derive_stats(features, MechForm.BEAST)
    assert bird.spd > beast.spd
    assert beast.hp > bird.hp


def test_elongation_increases_speed():
    base = derive_stats(sample_features(elongation=0.1), MechForm.HUMAN)
    fast = derive_stats(sample_features(elongation=0.9), MechForm.HUMAN)
    assert fast.spd > base.spd


def test_low_capture_quality_reduces_combat_stats():
    good = derive_stats(sample_features(capture_quality=0.9), MechForm.HUMAN)
    poor = derive_stats(sample_features(capture_quality=0.1), MechForm.HUMAN)
    assert poor.hp < good.hp
    assert poor.atk < good.atk


def test_feature_values_must_be_normalized():
    with pytest.raises(ValueError):
        FeatureVector(
            visual_entropy=1.5,
            edge_complexity=0.5,
            color_diversity=0.4,
            shape_complexity=0.45,
            semantic_rarity=0.3,
            capture_quality=0.8,
            size_balance=0.7,
            area=0.5,
            elongation=0.4,
            roundness=0.5,
            symmetry=0.6,
        )
