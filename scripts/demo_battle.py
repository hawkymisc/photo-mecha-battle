#!/usr/bin/env python3
from __future__ import annotations

from photo_mecha_battle import BattleEngine
from photo_mecha_battle.tactics import TacticPreset
from tests.conftest import sample_team, tactics_from_presets


def main() -> None:
    engine = BattleEngine()
    team_a = sample_team("player", "Player")
    team_b = sample_team("cpu", "CPU")
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

    result = engine.simulate(team_a, tactics_a, team_b, tactics_b, seed=42)
    print(result.format_log())
    print()
    print(f"seed={result.seed}")
    print(f"winner={result.winner_team_id or 'draw'}")
    print(f"turns={result.turns}")


if __name__ == "__main__":
    main()
