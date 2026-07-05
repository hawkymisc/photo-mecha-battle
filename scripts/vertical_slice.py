#!/usr/bin/env python3
"""Phase 1 vertical slice: capture → analyze → mech → preset → battle → log."""

from __future__ import annotations

from photo_mecha_battle.api.store import InMemoryStore, build_demo_cpu_team
from photo_mecha_battle.models import Position, Team, TeamSlot
from photo_mecha_battle.tactics import TacticPreset, build_preset


def main() -> None:
    store = InMemoryStore()

    print("=== Photo Mecha Battle — Vertical Slice ===\n")

    # PLAN D-013: 型はプレイヤー選択ではなく特徴量からの自動推定（docs/03 form_inference/1.0）。
    # 被写体ごとに異なる型が判明する流れをデモする（石→獣型、ペン→人型、傘→鳥形）。
    labels_and_names = [
        ("stone", "石メカ・前衛"),
        ("pen", "ペンメカ・中衛"),
        ("umbrella", "傘メカ・後衛"),
    ]
    records = []
    for index, (label, name) in enumerate(labels_and_names, start=1):
        capture = store.create_capture(label)
        candidates = store.detect_objects(capture.id)
        obj = store.segment_object(capture.id, str(candidates[0]["label"]))
        records.append(store.create_mech(obj.id, name))
        print(f"[{index}] 撮影→検出→セグメント label={label} info_score={obj.info_score:.3f}")

    mech_front, mech_middle, mech_back = records
    print("[4] メカ生成完了（型は特徴量から自動推定）")
    for record in (mech_front, mech_middle, mech_back):
        stats = record.mech.stats
        print(
            f"    {record.mech.name} ({record.mech.form.value}) "
            f"HP={stats.hp} ATK={stats.atk} DEF={stats.defense} SPD={stats.spd}"
        )

    presets = {
        Position.FRONT: TacticPreset.MELEE,
        Position.MIDDLE: TacticPreset.BOMBARDMENT,
        Position.BACK: TacticPreset.SNIPER,
    }
    print(f"[5] 戦術プリセット {[p.name for p in presets.values()]}")

    player_team = Team(
        id="player",
        name="Player",
        slots=[
            TeamSlot(mech=mech_front.mech, position=Position.FRONT),
            TeamSlot(mech=mech_middle.mech, position=Position.MIDDLE),
            TeamSlot(mech=mech_back.mech, position=Position.BACK),
        ],
    )
    player_tactics = {position: build_preset(preset) for position, preset in presets.items()}
    cpu_team, cpu_tactics = build_demo_cpu_team()

    battle = store.run_battle(player_team, player_tactics, cpu_team, cpu_tactics, seed=42)
    print("[6] オートバトル完了")
    print()
    print(battle.result.format_log())
    print()
    print(f"seed={battle.result.seed}")
    print(f"winner={battle.result.winner_team_id or 'draw'}")
    print(f"turns={battle.result.turns}")


if __name__ == "__main__":
    main()
