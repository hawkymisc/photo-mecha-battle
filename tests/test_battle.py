from photo_mecha_battle import BattleEngine
from photo_mecha_battle.models import MechStats
from photo_mecha_battle.tactics import TacticPreset
from tests.conftest import sample_team, tactics_from_presets


def test_battle_is_deterministic_for_same_seed():
    engine = BattleEngine()
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

    first = engine.simulate(team_a, tactics_a, team_b, tactics_b, seed=42)
    second = engine.simulate(team_a, tactics_a, team_b, tactics_b, seed=42)

    assert first.winner_team_id == second.winner_team_id
    assert first.turns == second.turns
    assert first.format_log() == second.format_log()


def test_battle_log_contains_condition_and_action():
    engine = BattleEngine()
    team_a = sample_team("a", "Alpha")
    team_b = sample_team("b", "Beta")
    tactics = tactics_from_presets({slot.position: TacticPreset.MELEE for slot in team_a.slots})
    enemy_tactics = tactics_from_presets({slot.position: TacticPreset.MELEE for slot in team_b.slots})

    result = engine.simulate(team_a, tactics, team_b, enemy_tactics, seed=7)
    log = result.format_log()

    assert "Turn 1" in log
    assert "条件「" in log
    assert "を実行" in log


def test_aggressive_team_can_finish_battle():
    engine = BattleEngine()
    team_a = sample_team("a", "Alpha")
    team_b = sample_team("b", "Beta")
    for slot in team_a.slots:
        slot.mech.stats = MechStats(
            hp=slot.mech.stats.hp,
            atk=250,
            defense=10,
            spd=99,
            tec=slot.mech.stats.tec,
            en=100,
            luck=0,
        )
    for slot in team_b.slots:
        slot.mech.stats = MechStats(hp=30, atk=20, defense=10, spd=10, tec=10, en=20)
    tactics = tactics_from_presets({slot.position: TacticPreset.SNIPER for slot in team_a.slots})
    enemy_tactics = tactics_from_presets({slot.position: TacticPreset.MELEE for slot in team_b.slots})

    result = engine.simulate(team_a, tactics, team_b, enemy_tactics, seed=11)

    assert result.winner_team_id == "a"
    assert result.turns < engine.max_turns
