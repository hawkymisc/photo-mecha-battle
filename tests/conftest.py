import json
from pathlib import Path

import pytest

from photo_mecha_battle.api.database import Database
from photo_mecha_battle.api.game_store import GameStore
from photo_mecha_battle.models import Mech, MechForm, MechStats, Position, Team, TeamSlot
from photo_mecha_battle.tactics import TacticPreset, build_preset

C0_MIN = 90.0
C1_MIN = 80.0


@pytest.fixture(autouse=True)
def fresh_game_store(monkeypatch):
    from photo_mecha_battle.api import app as app_module

    db = Database(":memory:")
    game_store = GameStore(db)
    monkeypatch.setattr(app_module, "store", game_store)
    yield game_store
    db.close()


@pytest.fixture
def auth_headers():
    from fastapi.testclient import TestClient
    from photo_mecha_battle.api.app import app

    client = TestClient(app)
    user = client.post("/auth/register", json={"name": "Tester"}).json()
    return {"X-User-Token": user["token"], "user": user}


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


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if exitstatus != 0:
        return
    if not session.config.pluginmanager.hasplugin("_cov"):
        return

    report_path = Path("coverage.json")
    if not report_path.exists():
        pytest.exit("coverage.json not found; run pytest with --cov-report=json", returncode=1)

    totals = json.loads(report_path.read_text())["totals"]
    c0 = totals["covered_lines"] / totals["num_statements"] * 100
    c1 = totals["covered_branches"] / totals["num_branches"] * 100

    failures: list[str] = []
    if c0 < C0_MIN:
        failures.append(f"C0 (line) coverage {c0:.1f}% < {C0_MIN}%")
    if c1 < C1_MIN:
        failures.append(f"C1 (branch) coverage {c1:.1f}% < {C1_MIN}%")
    if failures:
        pytest.exit("; ".join(failures), returncode=1)
