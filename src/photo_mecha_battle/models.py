from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MechForm(str, Enum):
    BIRD = "bird"
    HUMAN = "human"
    BEAST = "beast"


class Position(str, Enum):
    FRONT = "front"
    MIDDLE = "middle"
    BACK = "back"


POSITION_LABELS = {
    Position.FRONT: "前衛",
    Position.MIDDLE: "中衛",
    Position.BACK: "後衛",
}


@dataclass(frozen=True)
class MechStats:
    hp: int
    atk: int
    defense: int
    spd: int
    tec: int
    en: int
    luck: int = 0


@dataclass
class Mech:
    id: str
    name: str
    form: MechForm
    stats: MechStats
    current_hp: int | None = None
    current_en: int | None = None
    defending: bool = False
    evading: bool = False

    def clone_for_battle(self) -> Mech:
        return Mech(
            id=self.id,
            name=self.name,
            form=self.form,
            stats=self.stats,
            current_hp=self.stats.hp,
            current_en=self.stats.en,
        )


@dataclass
class TeamSlot:
    mech: Mech
    position: Position


@dataclass
class Team:
    id: str
    name: str
    slots: list[TeamSlot] = field(default_factory=list)

    def living_slots(self) -> list[TeamSlot]:
        return [slot for slot in self.slots if slot.mech.current_hp and slot.mech.current_hp > 0]
