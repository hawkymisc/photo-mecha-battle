from photo_mecha_battle.models import Mech, MechForm, MechStats, Position, Team, TeamSlot
from photo_mecha_battle.tactics import TacticPreset, build_preset


def sample_team(team_id: str, name: str) -> Team:
    return Team(
        id=team_id,
        name=name,
        slots=[
            TeamSlot(
                mech=Mech(
                    id=f"{team_id}-front",
                    name=f"{name}前衛",
                    form=MechForm.BEAST,
                    stats=MechStats(hp=120, atk=70, defense=60, spd=40, tec=45, en=80),
                ),
                position=Position.FRONT,
            ),
            TeamSlot(
                mech=Mech(
                    id=f"{team_id}-middle",
                    name=f"{name}中衛",
                    form=MechForm.HUMAN,
                    stats=MechStats(hp=100, atk=65, defense=50, spd=55, tec=70, en=90),
                ),
                position=Position.MIDDLE,
            ),
            TeamSlot(
                mech=Mech(
                    id=f"{team_id}-back",
                    name=f"{name}後衛",
                    form=MechForm.BIRD,
                    stats=MechStats(hp=80, atk=75, defense=35, spd=85, tec=80, en=100),
                ),
                position=Position.BACK,
            ),
        ],
    )


def tactics_from_presets(mapping: dict[Position, TacticPreset]):
    return {position: build_preset(preset) for position, preset in mapping.items()}
