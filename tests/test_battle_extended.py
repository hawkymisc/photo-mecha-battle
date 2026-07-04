from __future__ import annotations

import random
from unittest.mock import patch

import pytest

from photo_mecha_battle.battle import (
    ACTION_PROFILES,
    BattleEngine,
    DamageEvent,
    TurnLogEntry,
    _Actor,
)
from photo_mecha_battle.models import Mech, MechForm, MechStats, Position, Team, TeamSlot
from photo_mecha_battle.tactics import (
    ActionType,
    Condition,
    ConditionKind,
    TacticSet,
    TacticSlot,
    build_preset,
    TacticPreset,
)
from tests.conftest import sample_team, tactics_from_presets


def _custom_tactic(slots: list[TacticSlot], fallback: ActionType = ActionType.NORMAL_ATTACK) -> TacticSet:
    return TacticSet.from_slots("custom", slots, fallback)


def _single_mech_team(team_id: str, mech: Mech, position: Position = Position.FRONT) -> Team:
    return Team(id=team_id, name=team_id, slots=[TeamSlot(mech=mech, position=position)])


def test_turn_log_formats_note_and_defeat_suffix():
    note_entry = TurnLogEntry(
        turn=1,
        actor_team="a",
        actor_position=Position.FRONT,
        actor_name="A",
        condition_label="test",
        action=ActionType.DEFEND,
        note="防御態勢を取る",
    )
    assert "防御態勢を取る" in note_entry.format()

    defeat_entry = TurnLogEntry(
        turn=1,
        actor_team="a",
        actor_position=Position.FRONT,
        actor_name="A",
        condition_label="test",
        action=ActionType.NORMAL_ATTACK,
        damage_events=[DamageEvent("x", "Target", 99, defeated=True)],
    )
    assert "（撃破）" in defeat_entry.format()


def test_defend_evade_and_charge_actions_are_logged():
    engine = BattleEngine()
    defender = Mech("d", "Def", MechForm.HUMAN, MechStats(100, 10, 50, 10, 10, 10), current_hp=20, current_en=5)
    team_a = _single_mech_team("a", defender)
    enemy = Mech("e", "Enemy", MechForm.BEAST, MechStats(100, 10, 50, 10, 10, 10))
    team_b = _single_mech_team("b", enemy)

    defend_tactics = {Position.FRONT: _custom_tactic([TacticSlot(Condition(ConditionKind.ALWAYS), ActionType.DEFEND)])}
    result = engine.simulate(team_a, defend_tactics, team_b, defend_tactics, seed=1)
    assert "防御態勢を取る" in result.format_log()

    evade_mech = Mech("ev", "Ev", MechForm.BIRD, MechStats(100, 50, 30, 80, 50, 100), current_hp=100, current_en=100)
    evade_team = _single_mech_team("ev", evade_mech)
    close_enemy = Mech("ce", "Close", MechForm.BEAST, MechStats(100, 30, 40, 10, 10, 10))
    close_team = _single_mech_team("ce", close_enemy)
    evade_tactics = {Position.FRONT: build_preset(TacticPreset.HIT_AND_RUN)}
    evade_result = engine.simulate(evade_team, evade_tactics, close_team, evade_tactics, seed=3)
    assert any("回避行動" in entry.format() for entry in evade_result.log_entries)

    sniper = Mech("s", "S", MechForm.HUMAN, MechStats(80, 60, 40, 50, 70, 10), current_hp=80, current_en=10)
    sniper_team = _single_mech_team("s", sniper)
    sniper_tactics = {Position.FRONT: build_preset(TacticPreset.SNIPER)}
    charge_result = engine.simulate(sniper_team, sniper_tactics, close_team, sniper_tactics, seed=5)
    assert any("ENを" in entry.format() for entry in charge_result.log_entries)


def test_turret_preset_defends_when_hp_at_or_below_30_percent():
    """PLAN D-002: 砲台型は（迎撃条件が不成立の場合）自分HPが30%以下で防御が発動する。

    旧実装では「自分HPが70%以下→通常砲撃」が防御スロットより前段にあり、
    HP30%以下の状況でも常に70%以下条件が先勝ちして防御に到達できなかった。
    `engine.simulate()` は開始時に `clone_for_battle()` で HP/EN を満タンにリセットするため、
    ここでは `_choose_action` を直接呼び、任意の HP 状態での条件評価だけを検証する。
    """
    engine = BattleEngine()
    turret_mech = Mech(
        "t", "Turret", MechForm.HUMAN, MechStats(100, 50, 60, 30, 40, 80), current_hp=30, current_en=50
    )
    team_a = _single_mech_team("a", turret_mech)
    actor = _Actor(team=team_a, slot=team_a.slots[0], tactic=build_preset(TacticPreset.TURRET))

    # BIRD 形態は TARGET_CLOSE_RANGE（迎撃条件）を満たさないため、防御スロットの到達性を検証できる。
    enemy = Mech("e", "Enemy", MechForm.BIRD, MechStats(100, 40, 40, 60, 40, 80))
    team_b = _single_mech_team("b", enemy, position=Position.BACK)
    target = team_b.slots[0]

    condition_label, action = engine._choose_action(actor, team_b, target, turn=1)
    assert condition_label == "自分HPが30%以下"
    assert action == ActionType.DEFEND


def test_en_shortage_falls_back_when_fallback_is_unaffordable():
    engine = BattleEngine()
    mech = Mech("m", "M", MechForm.HUMAN, MechStats(100, 80, 40, 50, 50, 5), current_hp=100, current_en=5)
    team_a = _single_mech_team("a", mech)
    enemy = Mech("e", "E", MechForm.BEAST, MechStats(100, 10, 40, 10, 10, 10))
    team_b = _single_mech_team("b", enemy)
    tactics = {
        Position.FRONT: _custom_tactic(
            [TacticSlot(Condition(ConditionKind.SELF_HP_BELOW, 5), ActionType.HIGH_POWER_ATTACK)],
            ActionType.HIGH_POWER_ATTACK,
        )
    }
    result = engine.simulate(team_a, tactics, team_b, tactics, seed=2)
    assert any("EN不足" in entry.format() for entry in result.log_entries)


def test_type_modifier_covers_advantage_disadvantage_and_neutral():
    engine = BattleEngine()
    assert engine._type_modifier(MechForm.BIRD, MechForm.BEAST) == pytest.approx(1.15)
    assert engine._type_modifier(MechForm.BIRD, MechForm.HUMAN) == pytest.approx(0.90)
    assert engine._type_modifier(MechForm.BIRD, MechForm.BIRD) == pytest.approx(1.0)


def test_damage_modifiers_for_special_actions():
    engine = BattleEngine()
    attacker = Mech("atk", "Atk", MechForm.HUMAN, MechStats(100, 100, 10, 50, 50, 100), current_hp=100, current_en=100)
    bird = Mech("bird", "Bird", MechForm.BIRD, MechStats(100, 10, 10, 90, 50, 50), current_hp=100, current_en=100)
    tank = Mech("tank", "Tank", MechForm.BEAST, MechStats(100, 10, 90, 10, 50, 50), current_hp=100, current_en=100, defending=True)
    actor = _Actor(team=_single_mech_team("a", attacker), slot=TeamSlot(mech=attacker, position=Position.MIDDLE), tactic=_custom_tactic([]))

    accuracy_profile = ACTION_PROFILES[ActionType.ACCURACY_ATTACK]
    anti_bird = engine._calculate_damage(
        actor, TeamSlot(mech=bird, position=Position.BACK), ActionType.ACCURACY_ATTACK, accuracy_profile, random.Random(1)
    )
    normal = engine._calculate_damage(
        actor, TeamSlot(mech=bird, position=Position.BACK), ActionType.NORMAL_ATTACK, ACTION_PROFILES[ActionType.NORMAL_ATTACK], random.Random(1)
    )
    assert anti_bird >= normal

    pierce_profile = ACTION_PROFILES[ActionType.PIERCE_ATTACK]
    pierce = engine._calculate_damage(
        actor, TeamSlot(mech=tank, position=Position.FRONT), ActionType.PIERCE_ATTACK, pierce_profile, random.Random(2)
    )
    defended = engine._calculate_damage(
        actor, TeamSlot(mech=tank, position=Position.FRONT), ActionType.NORMAL_ATTACK, ACTION_PROFILES[ActionType.NORMAL_ATTACK], random.Random(2)
    )
    assert pierce > 0
    assert defended < pierce or defended <= pierce


def test_evade_can_nullify_damage():
    engine = BattleEngine()
    attacker = Mech("atk", "Atk", MechForm.HUMAN, MechStats(100, 100, 10, 50, 50, 100), current_hp=100, current_en=100)
    evader = Mech("ev", "Ev", MechForm.BIRD, MechStats(100, 10, 10, 90, 50, 50), current_hp=100, current_en=100, evading=True)
    actor = _Actor(team=_single_mech_team("a", attacker), slot=TeamSlot(mech=attacker, position=Position.FRONT), tactic=_custom_tactic([]))
    profile = ACTION_PROFILES[ActionType.NORMAL_ATTACK]

    with patch.object(random.Random, "random", return_value=0.1):
        assert engine._calculate_damage(
            actor, TeamSlot(mech=evader, position=Position.FRONT), ActionType.NORMAL_ATTACK, profile, random.Random(0)
        ) == 0


def test_finisher_execute_penalty_above_threshold():
    engine = BattleEngine()
    attacker = Mech("atk", "Atk", MechForm.HUMAN, MechStats(100, 100, 10, 50, 50, 100), current_hp=100, current_en=100)
    healthy = Mech("hp", "Healthy", MechForm.BEAST, MechStats(100, 10, 10, 10, 50, 50), current_hp=100, current_en=100)
    actor = _Actor(team=_single_mech_team("a", attacker), slot=TeamSlot(mech=attacker, position=Position.FRONT), tactic=_custom_tactic([]))
    profile = ACTION_PROFILES[ActionType.FINISHER]
    high_hp_damage = engine._calculate_damage(
        actor, TeamSlot(mech=healthy, position=Position.FRONT), ActionType.FINISHER, profile, random.Random(3)
    )
    healthy.current_hp = 20
    low_hp_damage = engine._calculate_damage(
        actor, TeamSlot(mech=healthy, position=Position.FRONT), ActionType.FINISHER, profile, random.Random(3)
    )
    assert low_hp_damage >= high_hp_damage


def test_area_and_backline_target_selection():
    engine = BattleEngine()
    attacker = Mech("atk", "Atk", MechForm.HUMAN, MechStats(100, 80, 40, 50, 50, 100), current_hp=100, current_en=100)
    actor = _Actor(
        team=_single_mech_team("a", attacker),
        slot=TeamSlot(mech=attacker, position=Position.MIDDLE),
        tactic=_custom_tactic([]),
    )
    enemy_team = Team(
        id="b",
        name="B",
        slots=[
            TeamSlot(mech=Mech("f", "F", MechForm.BEAST, MechStats(50, 10, 10, 10, 10, 10), current_hp=50, current_en=10), position=Position.FRONT),
            TeamSlot(mech=Mech("m", "M", MechForm.HUMAN, MechStats(50, 10, 10, 10, 10, 10), current_hp=50, current_en=10), position=Position.MIDDLE),
            TeamSlot(mech=Mech("b", "B", MechForm.BIRD, MechStats(50, 10, 10, 10, 10, 10), current_hp=50, current_en=10), position=Position.BACK),
        ],
    )
    area_targets = engine._select_targets(actor, enemy_team, ActionType.AREA_ATTACK, enemy_team.slots[0])
    assert len(area_targets) == 3
    back_targets = engine._select_targets(actor, enemy_team, ActionType.BACKLINE_ATTACK, enemy_team.slots[0])
    assert back_targets[0].position == Position.BACK


def test_condition_matching_branches():
    engine = BattleEngine()
    actor_mech = Mech("a", "A", MechForm.HUMAN, MechStats(100, 50, 40, 50, 50, 30), current_hp=20, current_en=25)
    actor = _Actor(team=_single_mech_team("a", actor_mech), slot=TeamSlot(mech=actor_mech, position=Position.FRONT), tactic=_custom_tactic([]))
    target = TeamSlot(
        mech=Mech("t", "T", MechForm.BEAST, MechStats(100, 50, 85, 90, 50, 50), current_hp=15, current_en=50, defending=True),
        position=Position.FRONT,
    )
    enemy_team = Team(id="b", name="B", slots=[target])

    assert engine._condition_matches(Condition(ConditionKind.SELF_HP_BELOW, 30), actor, enemy_team, target, 1)
    assert engine._condition_matches(Condition(ConditionKind.SELF_EN_AT_LEAST, 20), actor, enemy_team, target, 1)
    assert engine._condition_matches(Condition(ConditionKind.SELF_EN_BELOW, 30), actor, enemy_team, target, 1)
    assert engine._condition_matches(Condition(ConditionKind.TARGET_FORM, MechForm.BEAST), actor, enemy_team, target, 1)
    assert engine._condition_matches(Condition(ConditionKind.TARGET_HP_BELOW, 20), actor, enemy_team, target, 1)
    assert engine._condition_matches(Condition(ConditionKind.TARGET_DEF_HIGH, None), actor, enemy_team, target, 1)
    assert engine._condition_matches(Condition(ConditionKind.TARGET_SPD_HIGH, None), actor, enemy_team, target, 1)
    assert engine._condition_matches(Condition(ConditionKind.TARGET_DEFENDING, None), actor, enemy_team, target, 1)
    assert engine._condition_matches(Condition(ConditionKind.TARGET_CLOSE_RANGE, None), actor, enemy_team, target, 1)
    assert engine._condition_matches(Condition(ConditionKind.TARGET_BACKLINE_PRESENT, None), actor, enemy_team, target, 1) is False
    assert engine._condition_matches(Condition(ConditionKind.TARGET_FORM, MechForm.BIRD), actor, enemy_team, None, 1) is False

    back_target = TeamSlot(
        mech=Mech("back", "Back", MechForm.BIRD, MechStats(50, 10, 10, 10, 10, 10), current_hp=50, current_en=10),
        position=Position.BACK,
    )
    enemy_with_back = Team(id="b2", name="B2", slots=[target, back_target])
    assert engine._condition_matches(
        Condition(ConditionKind.TARGET_BACKLINE_PRESENT, None), actor, enemy_with_back, target, 1
    )
    assert engine._condition_matches(
        Condition(ConditionKind.ENEMIES_REMAINING_AT_LEAST, 2), actor, enemy_with_back, target, 1
    )


def test_hp_ratio_and_spend_en_edge_cases():
    engine = BattleEngine()
    empty_hp = Mech("e", "E", MechForm.HUMAN, MechStats(0, 10, 10, 10, 10, 10), current_hp=0, current_en=None)
    assert engine._hp_ratio(empty_hp) == 0.0
    engine._spend_en(empty_hp, 10)

    mech = Mech("m", "M", MechForm.HUMAN, MechStats(100, 10, 10, 10, 10, 10), current_hp=100, current_en=5)
    engine._spend_en(mech, 10)
    assert mech.current_en == 0


def test_skips_dead_actor_and_ends_at_max_turns():
    engine = BattleEngine()
    engine.max_turns = 2
    dead = Mech("dead", "Dead", MechForm.HUMAN, MechStats(10, 5, 5, 5, 5, 5), current_hp=0, current_en=0)
    alive = Mech("live", "Live", MechForm.HUMAN, MechStats(200, 5, 80, 5, 5, 5), current_hp=200, current_en=5)
    tank = Mech("tank", "Tank", MechForm.BEAST, MechStats(200, 5, 80, 5, 5, 5), current_hp=200, current_en=5)
    team_a = Team(
        id="a",
        name="A",
        slots=[
            TeamSlot(mech=dead, position=Position.FRONT),
            TeamSlot(mech=alive, position=Position.MIDDLE),
        ],
    )
    team_b = _single_mech_team("b", tank)
    tactics = tactics_from_presets({Position.FRONT: TacticPreset.TURRET, Position.MIDDLE: TacticPreset.TURRET})
    result = engine.simulate(team_a, tactics, team_b, tactics, seed=99)
    assert result.turns == 2
    assert result.winner_team_id is None


def test_crit_damage_with_high_luck():
    engine = BattleEngine()
    lucky = Mech("lucky", "Lucky", MechForm.HUMAN, MechStats(100, 100, 10, 50, 50, 100, luck=500), current_hp=100, current_en=100)
    target = Mech("t", "T", MechForm.BEAST, MechStats(100, 10, 10, 10, 50, 50), current_hp=100, current_en=100)
    actor = _Actor(team=_single_mech_team("a", lucky), slot=TeamSlot(mech=lucky, position=Position.FRONT), tactic=_custom_tactic([]))
    profile = ACTION_PROFILES[ActionType.NORMAL_ATTACK]

    with patch.object(random.Random, "random", return_value=0.0):
        crit_damage = engine._calculate_damage(
            actor, TeamSlot(mech=target, position=Position.FRONT), ActionType.NORMAL_ATTACK, profile, random.Random(0)
        )
    normal_damage = engine._calculate_damage(
        actor, TeamSlot(mech=target, position=Position.FRONT), ActionType.NORMAL_ATTACK, profile, random.Random(4)
    )
    assert crit_damage >= normal_damage


def test_intercept_bonus_against_frontline():
    engine = BattleEngine()
    attacker = Mech("atk", "Atk", MechForm.HUMAN, MechStats(100, 100, 10, 50, 50, 100), current_hp=100, current_en=100)
    target = Mech("t", "T", MechForm.BEAST, MechStats(100, 10, 10, 10, 50, 50), current_hp=100, current_en=100)
    actor = _Actor(team=_single_mech_team("a", attacker), slot=TeamSlot(mech=attacker, position=Position.FRONT), tactic=_custom_tactic([]))
    intercept_profile = ACTION_PROFILES[ActionType.INTERCEPT]
    intercept_damage = engine._calculate_damage(
        actor, TeamSlot(mech=target, position=Position.FRONT), ActionType.INTERCEPT, intercept_profile, random.Random(5)
    )
    assert intercept_damage > 0


def test_slot_skipped_when_action_unaffordable():
    engine = BattleEngine()
    mech = Mech("m", "M", MechForm.HUMAN, MechStats(100, 50, 40, 50, 50, 10), current_hp=100, current_en=0)
    actor = _Actor(
        team=_single_mech_team("a", mech),
        slot=TeamSlot(mech=mech, position=Position.FRONT),
        tactic=_custom_tactic(
            [TacticSlot(Condition(ConditionKind.ALWAYS), ActionType.SNIPER_SHOT)],
            ActionType.NORMAL_ATTACK,
        ),
    )
    enemy = Team(id="b", name="B", slots=[TeamSlot(mech=Mech("e", "E", MechForm.BEAST, MechStats(100, 10, 10, 10, 10, 10), current_hp=100, current_en=10), position=Position.FRONT)])
    label, action = engine._choose_action(actor, enemy, enemy.slots[0], 1)
    assert label == "基本行動"
    assert action == ActionType.NORMAL_ATTACK


def test_select_primary_target_returns_none_when_no_living_enemies():
    engine = BattleEngine()
    actor = _Actor(
        team=_single_mech_team("a", Mech("a", "A", MechForm.HUMAN, MechStats(10, 10, 10, 10, 10, 10), current_hp=10, current_en=10)),
        slot=TeamSlot(mech=Mech("a", "A", MechForm.HUMAN, MechStats(10, 10, 10, 10, 10, 10), current_hp=10, current_en=10), position=Position.FRONT),
        tactic=_custom_tactic([]),
    )
    empty_team = Team(id="b", name="B", slots=[])
    assert engine._select_primary_target(actor, empty_team) is None
    assert engine._select_targets(actor, empty_team, ActionType.NORMAL_ATTACK, None) == []


def test_can_execute_when_en_is_untracked():
    engine = BattleEngine()
    mech = Mech("m", "M", MechForm.HUMAN, MechStats(10, 10, 10, 10, 10, 10), current_hp=10, current_en=None)
    assert engine._can_execute(ActionType.SNIPER_SHOT, mech) is True


def test_damage_skips_target_with_uninitialized_hp():
    engine = BattleEngine()
    attacker = Mech("atk", "Atk", MechForm.HUMAN, MechStats(100, 100, 10, 50, 50, 100), current_hp=100, current_en=100)
    broken = Mech("broken", "Broken", MechForm.BEAST, MechStats(100, 10, 10, 10, 50, 50), current_hp=None, current_en=50)
    actor = _Actor(team=_single_mech_team("a", attacker), slot=TeamSlot(mech=attacker, position=Position.FRONT), tactic=_custom_tactic([]))
    entry = engine._resolve_actor_turn(
        1,
        actor,
        Team(id="b", name="B", slots=[TeamSlot(mech=broken, position=Position.FRONT)]),
        random.Random(0),
    )
    assert entry.damage_events == []


def test_winner_detected_when_enemy_team_is_already_defeated():
    engine = BattleEngine()
    winner_mech = Mech("w", "W", MechForm.HUMAN, MechStats(100, 200, 10, 99, 50, 100), current_hp=100, current_en=100)
    winner_team = _single_mech_team("winner", winner_mech)
    dead_enemy = Mech("d", "D", MechForm.BEAST, MechStats(10, 10, 10, 1, 10, 10), current_hp=0, current_en=0)
    enemy_team = _single_mech_team("loser", dead_enemy)
    tactics = {Position.FRONT: _custom_tactic([TacticSlot(Condition(ConditionKind.ALWAYS), ActionType.NORMAL_ATTACK)])}
    result = engine.simulate(winner_team, tactics, enemy_team, tactics, seed=1)
    assert result.winner_team_id == "winner"


def test_unhandled_condition_kind_returns_false():
    engine = BattleEngine()
    actor_mech = Mech("a", "A", MechForm.HUMAN, MechStats(100, 50, 40, 50, 50, 30), current_hp=100, current_en=30)
    actor = _Actor(team=_single_mech_team("a", actor_mech), slot=TeamSlot(mech=actor_mech, position=Position.FRONT), tactic=_custom_tactic([]))

    class FakeCondition:
        kind = "unsupported"
        threshold = None

        def label(self) -> str:
            return "unsupported"

    assert engine._condition_matches(FakeCondition(), actor, _single_mech_team("b", actor_mech), None, 1) is False


def test_charge_action_logs_recovery():
    engine = BattleEngine()
    mech = Mech("m", "M", MechForm.HUMAN, MechStats(100, 50, 40, 50, 50, 10), current_hp=100, current_en=10)
    actor = _Actor(
        team=_single_mech_team("a", mech),
        slot=TeamSlot(mech=mech, position=Position.FRONT),
        tactic=_custom_tactic([TacticSlot(Condition(ConditionKind.ALWAYS), ActionType.CHARGE)]),
    )
    charge_entry = engine._resolve_actor_turn(
        1,
        actor,
        _single_mech_team("b", Mech("e", "E", MechForm.BEAST, MechStats(100, 10, 40, 10, 10, 10), current_hp=100, current_en=10)),
        random.Random(0),
    )
    assert "ENを" in charge_entry.note


def test_select_targets_when_primary_is_dead():
    engine = BattleEngine()
    attacker = Mech("atk", "Atk", MechForm.HUMAN, MechStats(100, 50, 40, 50, 50, 100), current_hp=100, current_en=100)
    actor = _Actor(team=_single_mech_team("a", attacker), slot=TeamSlot(mech=attacker, position=Position.FRONT), tactic=_custom_tactic([]))
    dead_primary = TeamSlot(mech=Mech("d", "D", MechForm.BEAST, MechStats(10, 10, 10, 10, 10, 10), current_hp=0, current_en=0), position=Position.FRONT)
    living = TeamSlot(mech=Mech("l", "L", MechForm.BIRD, MechStats(50, 10, 10, 10, 10, 10), current_hp=50, current_en=10), position=Position.MIDDLE)
    enemy_team = Team(id="b", name="B", slots=[dead_primary, living])
    targets = engine._select_targets(actor, enemy_team, ActionType.NORMAL_ATTACK, dead_primary)
    assert targets == [living]


def test_disrupt_stays_a_deterministic_low_power_attack_pending_status_effect_design():
    """PLAN D-006 (blocked): 状態異常システム未設計のため `disrupt` は能力低下効果を持たず、

    決定的な低威力攻撃（威力 0.4、能力低下や追加効果なし）のままであることが暫定の受入基準。
    状態異常システムの設計・実装時に、この暫定挙動を意図的に変更したことが分かるよう
    回帰テストとして固定する（docs/04 行動候補注記 / config/po_pending_decisions.json 参照）。
    """
    profile = ACTION_PROFILES[ActionType.DISRUPT]
    assert profile["power"] == 0.4
    assert profile.get("targets") == 1
    # 能力低下・状態異常フラグ（例: "debuff", "status_effect"）がまだ存在しないことを確認する。
    assert set(profile.keys()) == {"power", "en_cost", "targets"}
