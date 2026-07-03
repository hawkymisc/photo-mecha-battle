from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from photo_mecha_battle.battle import BattleEngine, BattleResult
from photo_mecha_battle.features import FeatureVector
from photo_mecha_battle.mech_stats import build_mech, compute_info_score
from photo_mecha_battle.models import Mech, MechForm, Position, Team, TeamSlot
from photo_mecha_battle.tactics import TacticPreset, TacticSet, build_preset


@dataclass
class CaptureRecord:
    id: str
    label: str = "umbrella"
    has_image: bool = False


@dataclass
class ObjectRecord:
    id: str
    capture_id: str
    features: FeatureVector
    info_score: float


@dataclass
class MechRecord:
    id: str
    object_id: str
    mech: Mech


@dataclass
class BattleRecord:
    id: str
    result: BattleResult


@dataclass
class InMemoryStore:
    captures: dict[str, CaptureRecord] = field(default_factory=dict)
    objects: dict[str, ObjectRecord] = field(default_factory=dict)
    mechs: dict[str, MechRecord] = field(default_factory=dict)
    battles: dict[str, BattleRecord] = field(default_factory=dict)

    def create_capture(self, label: str = "umbrella") -> CaptureRecord:
        record = CaptureRecord(id=str(uuid.uuid4()), label=label)
        self.captures[record.id] = record
        return record

    def detect_objects(self, capture_id: str) -> list[dict[str, object]]:
        capture = self.captures[capture_id]
        return [
            {
                "object_id": str(uuid.uuid4()),
                "label": capture.label,
                "bbox": [0.2, 0.3, 0.6, 0.8],
                "confidence": 0.91,
            }
        ]

    def segment_object(self, capture_id: str, label: str) -> ObjectRecord:
        features = _features_for_label(label)
        record = ObjectRecord(
            id=str(uuid.uuid4()),
            capture_id=capture_id,
            features=features,
            info_score=compute_info_score(features),
        )
        self.objects[record.id] = record
        return record

    def create_mech(self, object_id: str, form: MechForm, name: str) -> MechRecord:
        obj = self.objects[object_id]
        mech_id = str(uuid.uuid4())
        mech = build_mech(mech_id, name, form, obj.features)
        record = MechRecord(id=mech_id, object_id=object_id, mech=mech)
        self.mechs[mech_id] = record
        return record

    def run_battle(
        self,
        team_a: Team,
        tactics_a: dict[Position, TacticSet],
        team_b: Team,
        tactics_b: dict[Position, TacticSet],
        seed: int,
    ) -> BattleRecord:
        engine = BattleEngine()
        result = engine.simulate(team_a, tactics_a, team_b, tactics_b, seed=seed)
        record = BattleRecord(id=str(uuid.uuid4()), result=result)
        self.battles[record.id] = record
        return record


def _features_for_label(label: str) -> FeatureVector:
    presets: dict[str, FeatureVector] = {
        "umbrella": FeatureVector(
            visual_entropy=0.55,
            edge_complexity=0.42,
            color_diversity=0.35,
            shape_complexity=0.5,
            semantic_rarity=0.25,
            capture_quality=0.85,
            size_balance=0.75,
            area=0.45,
            elongation=0.82,
            roundness=0.3,
            symmetry=0.55,
        ),
        "stone": FeatureVector(
            visual_entropy=0.4,
            edge_complexity=0.3,
            color_diversity=0.2,
            shape_complexity=0.35,
            semantic_rarity=0.15,
            capture_quality=0.9,
            size_balance=0.8,
            area=0.7,
            elongation=0.2,
            roundness=0.85,
            symmetry=0.5,
        ),
    }
    return presets.get(label, presets["umbrella"])


def build_demo_cpu_team() -> tuple[Team, dict[Position, TacticSet]]:
    cpu_mech = build_mech(
        "cpu-front",
        "CPU前衛",
        MechForm.BEAST,
        _features_for_label("stone"),
    )
    team = Team(
        id="cpu",
        name="CPU",
        slots=[
            TeamSlot(mech=cpu_mech, position=Position.FRONT),
            TeamSlot(
                mech=build_mech("cpu-middle", "CPU中衛", MechForm.HUMAN, _features_for_label("umbrella")),
                position=Position.MIDDLE,
            ),
            TeamSlot(
                mech=build_mech("cpu-back", "CPU後衛", MechForm.BIRD, _features_for_label("umbrella")),
                position=Position.BACK,
            ),
        ],
    )
    tactics = {
        Position.FRONT: build_preset(TacticPreset.TURRET),
        Position.MIDDLE: build_preset(TacticPreset.HIT_AND_RUN),
        Position.BACK: build_preset(TacticPreset.SNIPER),
    }
    return team, tactics
