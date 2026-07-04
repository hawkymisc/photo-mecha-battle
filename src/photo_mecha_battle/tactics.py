from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from photo_mecha_battle.models import MechForm, Position


class ActionType(str, Enum):
    NORMAL_ATTACK = "normal_attack"
    HIGH_POWER_ATTACK = "high_power_attack"
    ACCURACY_ATTACK = "accuracy_attack"
    PIERCE_ATTACK = "pierce_attack"
    AREA_ATTACK = "area_attack"
    DEFEND = "defend"
    EVADE = "evade"
    CHARGE = "charge"
    DISRUPT = "disrupt"
    FINISHER = "finisher"
    CLOSE_ATTACK = "close_attack"
    INTERCEPT = "intercept"
    BACKLINE_ATTACK = "backline_attack"
    SNIPER_SHOT = "sniper_shot"
    HEAVY_ARTILLERY = "heavy_artillery"
    NORMAL_SHOT = "normal_shot"
    NORMAL_SHELL = "normal_shell"


ACTION_LABELS = {
    ActionType.NORMAL_ATTACK: "通常攻撃",
    ActionType.HIGH_POWER_ATTACK: "高威力攻撃",
    ActionType.ACCURACY_ATTACK: "命中重視攻撃",
    ActionType.PIERCE_ATTACK: "貫通攻撃",
    ActionType.AREA_ATTACK: "範囲攻撃",
    ActionType.DEFEND: "防御",
    ActionType.EVADE: "回避行動",
    ActionType.CHARGE: "チャージ",
    ActionType.DISRUPT: "妨害",
    ActionType.FINISHER: "追撃",
    ActionType.CLOSE_ATTACK: "接近攻撃",
    ActionType.INTERCEPT: "迎撃",
    ActionType.BACKLINE_ATTACK: "後衛攻撃",
    ActionType.SNIPER_SHOT: "狙撃",
    ActionType.HEAVY_ARTILLERY: "重砲撃",
    ActionType.NORMAL_SHOT: "通常射撃",
    ActionType.NORMAL_SHELL: "通常砲撃",
}


class ConditionKind(str, Enum):
    SELF_HP_BELOW = "self_hp_below"
    SELF_EN_AT_LEAST = "self_en_at_least"
    SELF_EN_BELOW = "self_en_below"
    TARGET_FORM = "target_form"
    TARGET_HP_BELOW = "target_hp_below"
    TARGET_DEF_HIGH = "target_def_high"
    TARGET_SPD_HIGH = "target_spd_high"
    ENEMIES_REMAINING_AT_LEAST = "enemies_remaining_at_least"
    TARGET_DEFENDING = "target_defending"
    TARGET_CLOSE_RANGE = "target_close_range"
    TARGET_BACKLINE_PRESENT = "target_backline_present"
    ALWAYS = "always"


@dataclass(frozen=True)
class Condition:
    kind: ConditionKind
    threshold: float | int | MechForm | None = None

    def label(self) -> str:
        if self.kind == ConditionKind.SELF_HP_BELOW:
            return f"自分HPが{int(self.threshold)}%以下"
        if self.kind == ConditionKind.SELF_EN_AT_LEAST:
            return f"自分ENが{int(self.threshold)}以上"
        if self.kind == ConditionKind.SELF_EN_BELOW:
            return f"自分ENが{int(self.threshold)}未満"
        if self.kind == ConditionKind.TARGET_FORM:
            form_labels = {
                MechForm.BIRD: "鳥形",
                MechForm.HUMAN: "人型",
                MechForm.BEAST: "獣型",
            }
            return f"相手が{form_labels.get(self.threshold, self.threshold)}"
        if self.kind == ConditionKind.TARGET_HP_BELOW:
            return f"相手HPが{int(self.threshold)}%以下"
        if self.kind == ConditionKind.TARGET_DEF_HIGH:
            return "相手DEFが高い"
        if self.kind == ConditionKind.TARGET_SPD_HIGH:
            return "相手SPDが高い"
        if self.kind == ConditionKind.ENEMIES_REMAINING_AT_LEAST:
            return "敵が複数残っている"
        if self.kind == ConditionKind.TARGET_DEFENDING:
            return "相手が防御中"
        if self.kind == ConditionKind.TARGET_CLOSE_RANGE:
            return "相手が接近型"
        if self.kind == ConditionKind.TARGET_BACKLINE_PRESENT:
            return "相手後衛が残っている"
        return "常時"


@dataclass(frozen=True)
class TacticSlot:
    condition: Condition
    action: ActionType


@dataclass(frozen=True)
class TacticSet:
    name: str
    slots: tuple[TacticSlot, ...]
    fallback_action: ActionType

    @classmethod
    def from_slots(
        cls,
        name: str,
        slots: list[TacticSlot],
        fallback_action: ActionType,
    ) -> TacticSet:
        if len(slots) > 4:
            raise ValueError("tactic set supports at most 4 slots")
        return cls(name=name, slots=tuple(slots), fallback_action=fallback_action)


class TacticPreset(str, Enum):
    MELEE = "melee"
    HIT_AND_RUN = "hit_and_run"
    SNIPER = "sniper"
    BOMBARDMENT = "bombardment"
    TURRET = "turret"


PRESET_LABELS = {
    TacticPreset.MELEE: "近接戦闘型",
    TacticPreset.HIT_AND_RUN: "中距離ヒットアンドアウェイ型",
    TacticPreset.SNIPER: "遠距離狙撃型",
    TacticPreset.BOMBARDMENT: "爆撃型",
    TacticPreset.TURRET: "砲台型",
}


def build_preset(preset: TacticPreset) -> TacticSet:
    builders = {
        TacticPreset.MELEE: _melee_preset,
        TacticPreset.HIT_AND_RUN: _hit_and_run_preset,
        TacticPreset.SNIPER: _sniper_preset,
        TacticPreset.BOMBARDMENT: _bombardment_preset,
        TacticPreset.TURRET: _turret_preset,
    }
    return builders[preset]()


def _melee_preset() -> TacticSet:
    return TacticSet.from_slots(
        PRESET_LABELS[TacticPreset.MELEE],
        [
            TacticSlot(Condition(ConditionKind.SELF_HP_BELOW, 30), ActionType.DEFEND),
            TacticSlot(Condition(ConditionKind.TARGET_SPD_HIGH, None), ActionType.CLOSE_ATTACK),
            TacticSlot(Condition(ConditionKind.SELF_EN_AT_LEAST, 80), ActionType.HIGH_POWER_ATTACK),
            TacticSlot(Condition(ConditionKind.TARGET_HP_BELOW, 25), ActionType.FINISHER),
        ],
        ActionType.NORMAL_ATTACK,
    )


def _hit_and_run_preset() -> TacticSet:
    return TacticSet.from_slots(
        PRESET_LABELS[TacticPreset.HIT_AND_RUN],
        [
            TacticSlot(Condition(ConditionKind.TARGET_CLOSE_RANGE, None), ActionType.EVADE),
            TacticSlot(Condition(ConditionKind.SELF_HP_BELOW, 40), ActionType.EVADE),
            TacticSlot(Condition(ConditionKind.SELF_EN_AT_LEAST, 60), ActionType.HIGH_POWER_ATTACK),
            TacticSlot(Condition(ConditionKind.TARGET_HP_BELOW, 25), ActionType.FINISHER),
        ],
        ActionType.NORMAL_ATTACK,
    )


def _sniper_preset() -> TacticSet:
    return TacticSet.from_slots(
        PRESET_LABELS[TacticPreset.SNIPER],
        [
            TacticSlot(Condition(ConditionKind.TARGET_HP_BELOW, 30), ActionType.SNIPER_SHOT),
            TacticSlot(Condition(ConditionKind.TARGET_FORM, MechForm.BIRD), ActionType.ACCURACY_ATTACK),
            TacticSlot(Condition(ConditionKind.SELF_EN_BELOW, 40), ActionType.CHARGE),
            TacticSlot(Condition(ConditionKind.SELF_EN_AT_LEAST, 80), ActionType.SNIPER_SHOT),
        ],
        ActionType.NORMAL_SHOT,
    )


def _bombardment_preset() -> TacticSet:
    return TacticSet.from_slots(
        PRESET_LABELS[TacticPreset.BOMBARDMENT],
        [
            TacticSlot(Condition(ConditionKind.ENEMIES_REMAINING_AT_LEAST, 2), ActionType.AREA_ATTACK),
            TacticSlot(Condition(ConditionKind.TARGET_DEFENDING, None), ActionType.HIGH_POWER_ATTACK),
            TacticSlot(Condition(ConditionKind.SELF_EN_BELOW, 40), ActionType.CHARGE),
            TacticSlot(Condition(ConditionKind.TARGET_BACKLINE_PRESENT, None), ActionType.BACKLINE_ATTACK),
        ],
        ActionType.NORMAL_ATTACK,
    )


def _turret_preset() -> TacticSet:
    # docs/04 砲台型: 「自分HPが70%以下→通常砲撃」を防御より前段に置くと、防御条件（30%以下）が
    # 先勝ち評価で常に到達不能になる shadowing バグがあった（PLAN D-002）。通常砲撃は基本行動で
    # 表現済みのため、当該スロットは削除し docs/04 の3スロット構成に合わせる。
    return TacticSet.from_slots(
        PRESET_LABELS[TacticPreset.TURRET],
        [
            TacticSlot(Condition(ConditionKind.TARGET_CLOSE_RANGE, None), ActionType.INTERCEPT),
            TacticSlot(Condition(ConditionKind.SELF_HP_BELOW, 30), ActionType.DEFEND),
            TacticSlot(Condition(ConditionKind.SELF_EN_AT_LEAST, 80), ActionType.HEAVY_ARTILLERY),
        ],
        ActionType.NORMAL_SHELL,
    )
