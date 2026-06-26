from __future__ import annotations

from photo_mecha_battle.features import FeatureVector
from photo_mecha_battle.models import Mech, MechForm, MechStats

INFO_SCORE_WEIGHTS = {
    "visual_entropy": 0.25,
    "edge_complexity": 0.20,
    "color_diversity": 0.15,
    "shape_complexity": 0.15,
    "semantic_rarity": 0.10,
    "capture_quality": 0.10,
    "size_balance": 0.05,
}

FORM_BASE_STATS: dict[MechForm, MechStats] = {
    MechForm.BIRD: MechStats(hp=75, atk=58, defense=32, spd=88, tec=72, en=70, luck=5),
    MechForm.HUMAN: MechStats(hp=95, atk=62, defense=48, spd=55, tec=78, en=85, luck=5),
    MechForm.BEAST: MechStats(hp=125, atk=72, defense=68, spd=38, tec=48, en=75, luck=5),
}

STAT_MIN = 10
STAT_MAX = 200


def compute_info_score(features: FeatureVector) -> float:
    return (
        INFO_SCORE_WEIGHTS["visual_entropy"] * features.visual_entropy
        + INFO_SCORE_WEIGHTS["edge_complexity"] * features.edge_complexity
        + INFO_SCORE_WEIGHTS["color_diversity"] * features.color_diversity
        + INFO_SCORE_WEIGHTS["shape_complexity"] * features.shape_complexity
        + INFO_SCORE_WEIGHTS["semantic_rarity"] * features.semantic_rarity
        + INFO_SCORE_WEIGHTS["capture_quality"] * features.capture_quality
        + INFO_SCORE_WEIGHTS["size_balance"] * features.size_balance
    )


def _clamp(value: int) -> int:
    return max(STAT_MIN, min(STAT_MAX, value))


def derive_stats(features: FeatureVector, form: MechForm) -> MechStats:
    base = FORM_BASE_STATS[form]
    info_score = compute_info_score(features)

    hp = _clamp(base.hp + int(features.area * 35))
    defense = _clamp(base.defense + int(features.roundness * 22))
    spd = _clamp(base.spd + int(features.elongation * 28))
    tec = _clamp(base.tec + int(features.symmetry * 18) + int(features.edge_complexity * 8))
    en = _clamp(base.en + int(features.visual_entropy * 25) + int(info_score * 12))
    atk = _clamp(base.atk + int(features.edge_complexity * 18))
    luck = _clamp(base.luck + int(features.semantic_rarity * 12) + int(info_score * 8))

    quality_penalty = max(0.0, 0.5 - features.capture_quality)
    if quality_penalty > 0:
        penalty = int(quality_penalty * 30)
        hp = _clamp(hp - penalty)
        atk = _clamp(atk - penalty // 2)

    return MechStats(hp=hp, atk=atk, defense=defense, spd=spd, tec=tec, en=en, luck=luck)


def build_mech(
    mech_id: str,
    name: str,
    form: MechForm,
    features: FeatureVector,
) -> Mech:
    return Mech(
        id=mech_id,
        name=name,
        form=form,
        stats=derive_stats(features, form),
    )
