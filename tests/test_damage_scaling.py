"""PLAN D-010: ダメージ式のスケーリング係数 K（docs/05 ダメージ式）。

旧式 `ATK × SkillPower / (DEF + 100)` は現実的なステータス帯（ATK 58〜90 前後）で
素点が常に 1.0 未満となり、`max(1, ...)` により全打撃が 1 ダメージへ潰れて
全バトルがターン上限の引き分けになっていた（Issue #23）。
PO 承認済みの案 A に従い、分子にスケーリング係数 K を導入する。
分母の `+100` はソフトアーマー正規化定数として維持する。
"""

from __future__ import annotations

from photo_mecha_battle.battle import (
    ACTION_PROFILES,
    DAMAGE_SCALING,
    BattleEngine,
    _Actor,
)
from photo_mecha_battle.models import Mech, MechForm, MechStats, Position, Team, TeamSlot
from photo_mecha_battle.tactics import (
    ActionType,
    Condition,
    ConditionKind,
    TacticPreset,
    TacticSet,
    TacticSlot,
)
from tests.conftest import sample_team, tactics_from_presets


class _FixedRng:
    """乱数補正・クリティカル判定を無効化した決定的スタブ。"""

    def uniform(self, _low: float, _high: float) -> float:
        return 1.0

    def random(self) -> float:
        return 1.0


def _plain_actor(mech: Mech, position: Position) -> _Actor:
    team = Team(id="a", name="a", slots=[TeamSlot(mech=mech, position=position)])
    return _Actor(team=team, slot=team.slots[0], tactic=TacticSet.from_slots("empty", [], ActionType.NORMAL_ATTACK))


def test_calibration_example_matches_docs05():
    """docs/05 キャリブレーション例: ATK=80, DEF=50, K=60 → 32 ダメージ。

    型相性・位置補正・乱数・クリティカルをすべて 1.0 に固定し、
    素点 `ATK × SkillPower × K / (DEF + 100)` だけを検証する。
    （攻撃側 FRONT: 攻撃補正 1.0、対象側 MIDDLE: 防御補正 1.0）
    """
    attacker = Mech("atk", "Attacker", MechForm.HUMAN, MechStats(100, 80, 50, 50, 50, 50, luck=0))
    defender = Mech("def", "Defender", MechForm.HUMAN, MechStats(100, 80, 50, 50, 50, 50, luck=0), current_hp=100)
    engine = BattleEngine()
    actor = _plain_actor(attacker, Position.FRONT)

    damage = engine._calculate_damage(
        actor,
        TeamSlot(mech=defender, position=Position.MIDDLE),
        ActionType.NORMAL_ATTACK,
        ACTION_PROFILES[ActionType.NORMAL_ATTACK],
        _FixedRng(),
    )

    assert DAMAGE_SCALING == 60
    assert damage == int(80 * 1.0 * DAMAGE_SCALING / (50 + 100)) == 32


def test_realistic_stat_band_produces_meaningful_damage():
    """現実的ステータス帯（derive_stats の出力域）で 1 ダメージに潰れないこと。"""
    attacker = Mech("atk", "Attacker", MechForm.BIRD, MechStats(75, 58, 32, 88, 72, 70, luck=0))
    tank = Mech("def", "Tank", MechForm.BIRD, MechStats(160, 60, 90, 38, 48, 75, luck=0), current_hp=160)
    engine = BattleEngine()
    actor = _plain_actor(attacker, Position.BACK)

    damage = engine._calculate_damage(
        actor,
        TeamSlot(mech=tank, position=Position.MIDDLE),
        ActionType.NORMAL_ATTACK,
        ACTION_PROFILES[ActionType.NORMAL_ATTACK],
        _FixedRng(),
    )

    # 最弱 ATK × 後衛補正 0.9 vs 最硬 DEF でも 1 ダメージ床に張り付かない
    assert damage >= 10


def test_realistic_teams_reach_a_decision():
    """Issue #23 回帰: 実ステータス帯の同型チーム同士でも決着がつくこと。

    修正前は全打撃 1 ダメージのため 20 戦全てがターン上限の引き分けだった。
    決定的エンジンなので seed ごとの結果は安定して再現される。
    """
    engine = BattleEngine()
    decided = 0
    for seed in range(1, 21):
        team_a = sample_team("a", "Alpha")
        team_b = sample_team("b", "Beta")
        tactics_a = tactics_from_presets(
            {
                team_a.slots[0].position: TacticPreset.MELEE,
                team_a.slots[1].position: TacticPreset.BOMBARDMENT,
                team_a.slots[2].position: TacticPreset.SNIPER,
            }
        )
        tactics_b = tactics_from_presets(
            {
                team_b.slots[0].position: TacticPreset.TURRET,
                team_b.slots[1].position: TacticPreset.HIT_AND_RUN,
                team_b.slots[2].position: TacticPreset.SNIPER,
            }
        )
        result = engine.simulate(team_a, tactics_a, team_b, tactics_b, seed=seed)
        if result.winner_team_id is not None:
            decided += 1

    # 引き分けが例外的な結果であること（バランス上ゼロは要求しない）。
    # 対戦条件: conftest.sample_team（HP 80〜120 / ATK 65〜75 / DEF 35〜60 の 3 機編成）、
    # 近接+爆撃+狙撃 vs 砲台+ヒットアンドアウェイ+狙撃、max_turns=30。
    assert decided >= 15, f"20 戦中 {decided} 戦しか決着せず（引き分け {20 - decided} 戦）— K の縮小か HP 帯の変更を疑う"


def test_boundary_min_atk_vs_max_def_does_not_explode():
    """境界: STAT_MIN の ATK × STAT_MAX の DEF でも 1 以上の整数ダメージに収まる。"""
    weakest = Mech("w", "Weakest", MechForm.HUMAN, MechStats(100, 10, 10, 50, 50, 50, luck=0))
    hardest = Mech("h", "Hardest", MechForm.HUMAN, MechStats(200, 10, 200, 50, 50, 50, luck=0), current_hp=200)
    engine = BattleEngine()
    actor = _plain_actor(weakest, Position.FRONT)

    damage = engine._calculate_damage(
        actor,
        TeamSlot(mech=hardest, position=Position.MIDDLE),
        ActionType.NORMAL_ATTACK,
        ACTION_PROFILES[ActionType.NORMAL_ATTACK],
        _FixedRng(),
    )

    # 10×60/(200+100) = 2.0 — 床(1)に潰れず、かつ低倍率が保たれる
    assert damage == 2


def test_low_skill_power_scales_below_normal_attack():
    """境界: 最低威力スキル（disrupt 0.4）が通常攻撃比で正しく縮小される。"""
    attacker = Mech("atk", "Attacker", MechForm.HUMAN, MechStats(100, 80, 50, 50, 50, 50, luck=0))
    defender = Mech("def", "Defender", MechForm.HUMAN, MechStats(100, 80, 50, 50, 50, 50, luck=0), current_hp=100)
    engine = BattleEngine()
    actor = _plain_actor(attacker, Position.FRONT)
    target = TeamSlot(mech=defender, position=Position.MIDDLE)

    disrupt = engine._calculate_damage(
        actor, target, ActionType.DISRUPT, ACTION_PROFILES[ActionType.DISRUPT], _FixedRng()
    )

    # 80×0.4×60/150 = 12.8 → 12（通常攻撃 32 の 0.4 倍相当）
    assert disrupt == 12


def test_type_modifier_ordering_preserved_after_scaling():
    """型相性（有利 1.15 / 同等 1.00 / 不利 0.90）の順序がスケーリング後も保たれる。"""
    engine = BattleEngine()

    def damage_vs(defender_form: MechForm) -> int:
        attacker = Mech("atk", "Attacker", MechForm.HUMAN, MechStats(100, 80, 50, 50, 50, 50, luck=0))
        defender = Mech("def", "Defender", defender_form, MechStats(100, 80, 50, 50, 50, 50, luck=0), current_hp=100)
        actor = _plain_actor(attacker, Position.FRONT)
        return engine._calculate_damage(
            actor,
            TeamSlot(mech=defender, position=Position.MIDDLE),
            ActionType.NORMAL_ATTACK,
            ACTION_PROFILES[ActionType.NORMAL_ATTACK],
            _FixedRng(),
        )

    # 人型 > 鳥形（有利）、人型 = 人型（同等）、人型 < 獣型は不利
    advantage = damage_vs(MechForm.BIRD)
    neutral = damage_vs(MechForm.HUMAN)
    disadvantage = damage_vs(MechForm.BEAST)
    assert advantage > neutral > disadvantage
    assert advantage == int(32 * 1.15)
    assert disadvantage == int(32 * 0.90)


def test_no_damage_matchup_still_ends_at_max_turns_as_draw():
    """境界: 双方が防御し続ける対戦はターン上限で終了し、引き分け（winner None）となる。"""
    engine = BattleEngine()
    team_a = sample_team("a", "Alpha")
    team_b = sample_team("b", "Beta")
    defend_only = TacticSet.from_slots(
        "defend-only",
        [TacticSlot(Condition(ConditionKind.ALWAYS), ActionType.DEFEND)],
        ActionType.DEFEND,
    )
    tactics = {slot.position: defend_only for slot in team_a.slots}

    result = engine.simulate(team_a, tactics, team_b, tactics, seed=1)

    assert result.winner_team_id is None
    assert result.turns == engine.max_turns


def test_scaled_damage_is_deterministic_for_same_seed():
    """スケーリング導入後も同一 seed → 同一結果の決定性が維持されること。"""
    engine = BattleEngine()
    team_a = sample_team("a", "Alpha")
    team_b = sample_team("b", "Beta")
    tactics = tactics_from_presets({slot.position: TacticPreset.MELEE for slot in team_a.slots})
    enemy_tactics = tactics_from_presets({slot.position: TacticPreset.MELEE for slot in team_b.slots})

    first = engine.simulate(team_a, tactics, team_b, enemy_tactics, seed=99)
    team_a2 = sample_team("a", "Alpha")
    team_b2 = sample_team("b", "Beta")
    second = engine.simulate(team_a2, tactics, team_b2, enemy_tactics, seed=99)

    assert first.winner_team_id == second.winner_team_id
    assert first.turns == second.turns
    assert first.format_log() == second.format_log()
