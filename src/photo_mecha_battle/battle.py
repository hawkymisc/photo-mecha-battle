from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

from photo_mecha_battle.models import (
    POSITION_LABELS,
    Mech,
    MechForm,
    Position,
    Team,
    TeamSlot,
)
from photo_mecha_battle.tactics import (
    ACTION_LABELS,
    ActionType,
    Condition,
    ConditionKind,
    TacticSet,
)

TYPE_ADVANTAGE = {
    MechForm.BIRD: MechForm.BEAST,
    MechForm.BEAST: MechForm.HUMAN,
    MechForm.HUMAN: MechForm.BIRD,
}

ADVANTAGE_MULTIPLIER = 1.15
DISADVANTAGE_MULTIPLIER = 0.90

POSITION_ATTACK_MODIFIER = {
    Position.FRONT: 1.0,
    Position.MIDDLE: 0.95,
    Position.BACK: 0.9,
}

POSITION_DEFENSE_MODIFIER = {
    Position.FRONT: 1.1,
    Position.MIDDLE: 1.0,
    Position.BACK: 0.85,
}

ACTION_PROFILES: dict[ActionType, dict[str, float | bool]] = {
    ActionType.NORMAL_ATTACK: {"power": 1.0, "en_cost": 0, "targets": 1},
    ActionType.HIGH_POWER_ATTACK: {"power": 1.5, "en_cost": 30, "targets": 1},
    ActionType.ACCURACY_ATTACK: {"power": 0.95, "en_cost": 15, "targets": 1, "anti_bird": True},
    ActionType.PIERCE_ATTACK: {"power": 1.1, "en_cost": 20, "targets": 1, "anti_def": True},
    ActionType.AREA_ATTACK: {"power": 0.75, "en_cost": 25, "targets": 3},
    ActionType.DEFEND: {"power": 0.0, "en_cost": 0, "targets": 0, "defend": True},
    ActionType.EVADE: {"power": 0.0, "en_cost": 10, "targets": 0, "evade": True},
    ActionType.CHARGE: {"power": 0.0, "en_cost": 0, "targets": 0, "charge": 25},
    ActionType.DISRUPT: {"power": 0.4, "en_cost": 20, "targets": 1},
    ActionType.FINISHER: {"power": 1.35, "en_cost": 20, "targets": 1, "execute": True},
    ActionType.CLOSE_ATTACK: {"power": 1.15, "en_cost": 15, "targets": 1},
    ActionType.INTERCEPT: {"power": 1.2, "en_cost": 15, "targets": 1, "intercept": True},
    ActionType.BACKLINE_ATTACK: {"power": 1.0, "en_cost": 20, "targets": 1, "prefer_back": True},
    ActionType.SNIPER_SHOT: {"power": 1.45, "en_cost": 35, "targets": 1},
    ActionType.HEAVY_ARTILLERY: {"power": 1.6, "en_cost": 40, "targets": 1},
    ActionType.NORMAL_SHOT: {"power": 0.95, "en_cost": 0, "targets": 1},
    ActionType.NORMAL_SHELL: {"power": 1.05, "en_cost": 0, "targets": 1},
}


@dataclass
class DamageEvent:
    target_id: str
    target_name: str
    damage: int
    defeated: bool


@dataclass
class TurnLogEntry:
    turn: int
    actor_team: str
    actor_position: Position
    actor_name: str
    condition_label: str
    action: ActionType
    damage_events: list[DamageEvent] = field(default_factory=list)
    note: str = ""

    def format(self) -> str:
        lines = [
            f"Turn {self.turn}",
            f"{POSITION_LABELS[self.actor_position]}：条件「{self.condition_label}」が成立",
            f"→ {ACTION_LABELS[self.action]}を実行",
        ]
        if self.damage_events:
            for event in self.damage_events:
                suffix = "（撃破）" if event.defeated else ""
                lines.append(f"→ {event.target_name}に{event.damage}ダメージ{suffix}")
        elif self.note:
            lines.append(f"→ {self.note}")
        return "\n".join(lines)


@dataclass
class BattleResult:
    seed: int
    winner_team_id: str | None
    turns: int
    log_entries: list[TurnLogEntry]

    def format_log(self) -> str:
        return "\n\n".join(entry.format() for entry in self.log_entries)


@dataclass
class _Actor:
    team: Team
    slot: TeamSlot
    tactic: TacticSet


class BattleEngine:
    max_turns: int = 30

    def simulate(
        self,
        team_a: Team,
        tactics_a: dict[Position, TacticSet],
        team_b: Team,
        tactics_b: dict[Position, TacticSet],
        seed: int,
    ) -> BattleResult:
        rng = random.Random(seed)
        team_a = self._clone_team(team_a)
        team_b = self._clone_team(team_b)
        log_entries: list[TurnLogEntry] = []
        winner: str | None = None

        for turn in range(1, self.max_turns + 1):
            self._reset_turn_flags(team_a)
            self._reset_turn_flags(team_b)

            actors = self._build_turn_order(team_a, tactics_a, team_b, tactics_b)
            for actor in actors:
                if not actor.slot.mech.current_hp or actor.slot.mech.current_hp <= 0:
                    continue

                enemy_team = team_b if actor.team.id == team_a.id else team_a
                if not enemy_team.living_slots():
                    winner = actor.team.id
                    break

                entry = self._resolve_actor_turn(turn, actor, enemy_team, rng)
                log_entries.append(entry)

                if not enemy_team.living_slots():
                    winner = actor.team.id
                    break

            if winner:
                return BattleResult(seed=seed, winner_team_id=winner, turns=turn, log_entries=log_entries)

        return BattleResult(seed=seed, winner_team_id=winner, turns=self.max_turns, log_entries=log_entries)

    def _clone_team(self, team: Team) -> Team:
        return Team(
            id=team.id,
            name=team.name,
            slots=[
                TeamSlot(mech=slot.mech.clone_for_battle(), position=slot.position)
                for slot in team.slots
            ],
        )

    def _reset_turn_flags(self, team: Team) -> None:
        for slot in team.slots:
            slot.mech.defending = False
            slot.mech.evading = False

    def _build_turn_order(
        self,
        team_a: Team,
        tactics_a: dict[Position, TacticSet],
        team_b: Team,
        tactics_b: dict[Position, TacticSet],
    ) -> list[_Actor]:
        actors: list[_Actor] = []
        for team, tactics in ((team_a, tactics_a), (team_b, tactics_b)):
            for slot in team.slots:
                if slot.mech.current_hp and slot.mech.current_hp > 0:
                    actors.append(_Actor(team=team, slot=slot, tactic=tactics[slot.position]))
        actors.sort(key=lambda actor: (-actor.slot.mech.stats.spd, actor.team.id, actor.slot.position.value))
        return actors

    def _resolve_actor_turn(
        self,
        turn: int,
        actor: _Actor,
        enemy_team: Team,
        rng: random.Random,
    ) -> TurnLogEntry:
        target = self._select_primary_target(actor, enemy_team)
        condition_label, action = self._choose_action(actor, enemy_team, target, turn)

        profile = ACTION_PROFILES[action]
        mech = actor.slot.mech
        if mech.current_en is not None and mech.current_en < profile.get("en_cost", 0):
            condition_label = "EN不足"
            action = actor.tactic.fallback_action
            profile = ACTION_PROFILES[action]

        if profile.get("defend"):
            mech.defending = True
            return TurnLogEntry(
                turn=turn,
                actor_team=actor.team.id,
                actor_position=actor.slot.position,
                actor_name=mech.name,
                condition_label=condition_label,
                action=action,
                note="防御態勢を取る",
            )

        if profile.get("evade"):
            mech.evading = True
            self._spend_en(mech, int(profile.get("en_cost", 0)))
            return TurnLogEntry(
                turn=turn,
                actor_team=actor.team.id,
                actor_position=actor.slot.position,
                actor_name=mech.name,
                condition_label=condition_label,
                action=action,
                note="回避行動を取る",
            )

        if profile.get("charge"):
            gain = int(profile.get("charge", 0))
            if mech.current_en is not None:
                mech.current_en = min(mech.stats.en, mech.current_en + gain)
            return TurnLogEntry(
                turn=turn,
                actor_team=actor.team.id,
                actor_position=actor.slot.position,
                actor_name=mech.name,
                condition_label=condition_label,
                action=action,
                note=f"ENを{gain}回復",
            )

        targets = self._select_targets(actor, enemy_team, action, target)
        damage_events: list[DamageEvent] = []
        for enemy_slot in targets:
            damage = self._calculate_damage(actor, enemy_slot, action, profile, rng)
            enemy = enemy_slot.mech
            if enemy.current_hp is None:
                continue
            enemy.current_hp = max(0, enemy.current_hp - damage)
            damage_events.append(
                DamageEvent(
                    target_id=enemy.id,
                    target_name=enemy.name,
                    damage=damage,
                    defeated=enemy.current_hp == 0,
                )
            )

        self._spend_en(mech, int(profile.get("en_cost", 0)))
        return TurnLogEntry(
            turn=turn,
            actor_team=actor.team.id,
            actor_position=actor.slot.position,
            actor_name=mech.name,
            condition_label=condition_label,
            action=action,
            damage_events=damage_events,
        )

    def _choose_action(
        self,
        actor: _Actor,
        enemy_team: Team,
        target: TeamSlot | None,
        turn: int,
    ) -> tuple[str, ActionType]:
        for slot in actor.tactic.slots:
            if self._condition_matches(slot.condition, actor, enemy_team, target, turn):
                if self._can_execute(slot.action, actor.slot.mech):
                    return slot.condition.label(), slot.action
        fallback = actor.tactic.fallback_action
        return "基本行動", fallback

    def _condition_matches(
        self,
        condition: Condition,
        actor: _Actor,
        enemy_team: Team,
        target: TeamSlot | None,
        turn: int,
    ) -> bool:
        mech = actor.slot.mech
        kind = condition.kind
        threshold = condition.threshold

        if kind == ConditionKind.ALWAYS:
            return True
        if kind == ConditionKind.SELF_HP_BELOW:
            return self._hp_ratio(mech) <= float(threshold) / 100
        if kind == ConditionKind.SELF_EN_AT_LEAST:
            return (mech.current_en or 0) >= int(threshold)
        if kind == ConditionKind.SELF_EN_BELOW:
            return (mech.current_en or 0) < int(threshold)
        if kind == ConditionKind.ENEMIES_REMAINING_AT_LEAST:
            return len(enemy_team.living_slots()) >= int(threshold)
        if target is None:
            return False
        if kind == ConditionKind.TARGET_FORM:
            return target.mech.form == threshold
        if kind == ConditionKind.TARGET_HP_BELOW:
            return self._hp_ratio(target.mech) <= float(threshold) / 100
        if kind == ConditionKind.TARGET_DEF_HIGH:
            return target.mech.stats.defense >= 80
        if kind == ConditionKind.TARGET_SPD_HIGH:
            return target.mech.stats.spd >= 80
        if kind == ConditionKind.TARGET_DEFENDING:
            return target.mech.defending
        if kind == ConditionKind.TARGET_CLOSE_RANGE:
            return target.mech.form in {MechForm.BEAST, MechForm.HUMAN} and target.position == Position.FRONT
        if kind == ConditionKind.TARGET_BACKLINE_PRESENT:
            return any(
                slot.position == Position.BACK and slot.mech.current_hp and slot.mech.current_hp > 0
                for slot in enemy_team.slots
            )
        return False

    def _can_execute(self, action: ActionType, mech: Mech) -> bool:
        profile = ACTION_PROFILES[action]
        if mech.current_en is None:
            return True
        return mech.current_en >= profile.get("en_cost", 0)

    def _select_primary_target(self, actor: _Actor, enemy_team: Team) -> TeamSlot | None:
        living = enemy_team.living_slots()
        if not living:
            return None
        order = [Position.FRONT, Position.MIDDLE, Position.BACK]
        for position in order:
            for slot in living:
                if slot.position == position:
                    return slot
        return living[0]

    def _select_targets(
        self,
        actor: _Actor,
        enemy_team: Team,
        action: ActionType,
        primary: TeamSlot | None,
    ) -> list[TeamSlot]:
        living = enemy_team.living_slots()
        if not living:
            return []
        profile = ACTION_PROFILES[action]
        if profile.get("prefer_back"):
            backline = [slot for slot in living if slot.position == Position.BACK]
            if backline:
                return [backline[0]]
        if int(profile.get("targets", 1)) >= 3:
            return living[:3]
        if primary and primary in living:
            return [primary]
        return [living[0]]

    def _calculate_damage(
        self,
        actor: _Actor,
        target_slot: TeamSlot,
        action: ActionType,
        profile: dict[str, float | bool],
        rng: random.Random,
    ) -> int:
        attacker = actor.slot.mech
        defender = target_slot.mech
        if defender.evading and rng.random() < 0.35:
            return 0

        skill_power = float(profile.get("power", 1.0))
        if profile.get("execute") and self._hp_ratio(defender) > 0.25:
            skill_power *= 0.85

        base = attacker.stats.atk * skill_power / (defender.stats.defense + 100)
        type_mod = self._type_modifier(attacker.form, defender.form)
        position_mod = POSITION_ATTACK_MODIFIER[actor.slot.position] / POSITION_DEFENSE_MODIFIER[target_slot.position]

        if profile.get("anti_bird") and defender.form == MechForm.BIRD:
            base *= 1.1
        if profile.get("anti_def") and defender.stats.defense >= 80:
            base *= 1.15
        if profile.get("intercept") and target_slot.position == Position.FRONT:
            base *= 1.1
        if defender.defending:
            base *= 0.6

        random_mod = rng.uniform(0.9, 1.1)
        crit_mod = 1.2 if rng.random() < attacker.stats.luck / 500 else 1.0
        damage = int(max(1, base * type_mod * position_mod * random_mod * crit_mod))
        return damage

    def _type_modifier(self, attacker: MechForm, defender: MechForm) -> float:
        if TYPE_ADVANTAGE[attacker] == defender:
            return ADVANTAGE_MULTIPLIER
        if TYPE_ADVANTAGE[defender] == attacker:
            return DISADVANTAGE_MULTIPLIER
        return 1.0

    def _hp_ratio(self, mech: Mech) -> float:
        if not mech.current_hp or mech.stats.hp <= 0:
            return 0.0
        return mech.current_hp / mech.stats.hp

    def _spend_en(self, mech: Mech, amount: int) -> None:
        if mech.current_en is None:
            return
        mech.current_en = max(0, mech.current_en - amount)
