from photo_mecha_battle.models import Mech, MechForm, MechStats, Position, Team, TeamSlot


def test_mech_clone_for_battle_resets_state():
    mech = Mech(
        id="m1",
        name="Test",
        form=MechForm.BIRD,
        stats=MechStats(hp=80, atk=50, defense=30, spd=70, tec=60, en=90),
        current_hp=10,
        current_en=5,
        defending=True,
        evading=True,
    )
    cloned = mech.clone_for_battle()
    assert cloned.current_hp == 80
    assert cloned.current_en == 90
    assert cloned.defending is False
    assert cloned.evading is False


def test_team_living_slots_excludes_defeated_mechs():
    team = Team(
        id="t",
        name="T",
        slots=[
            TeamSlot(
                mech=Mech("a", "A", MechForm.HUMAN, MechStats(10, 10, 10, 10, 10, 10), current_hp=0, current_en=0),
                position=Position.FRONT,
            ),
            TeamSlot(
                mech=Mech("b", "B", MechForm.HUMAN, MechStats(10, 10, 10, 10, 10, 10), current_hp=5, current_en=5),
                position=Position.BACK,
            ),
        ],
    )
    living = team.living_slots()
    assert len(living) == 1
    assert living[0].mech.id == "b"
