import pytest
from fastapi.testclient import TestClient

from photo_mecha_battle.api.app import app
from photo_mecha_battle.models import MechForm

client = TestClient(app)


def test_vertical_slice_via_api():
    capture = client.post("/captures", json={"label": "umbrella"}).json()
    segment = client.post(
        f"/captures/{capture['id']}/segment",
        json={"label": "umbrella"},
    ).json()
    mech = client.post(
        "/mechs",
        json={
            "object_id": segment["id"],
            "form": MechForm.BIRD.value,
            "name": "APIメカ",
        },
    ).json()
    battle = client.post(
        "/battles",
        json={
            "team_name": "API Team",
            "seed": 42,
            "slots": [
                {"mech_id": mech["id"], "position": "front", "preset": "melee"},
                {"mech_id": mech["id"], "position": "middle", "preset": "bombardment"},
                {"mech_id": mech["id"], "position": "back", "preset": "sniper"},
            ],
        },
    ).json()

    assert battle["seed"] == 42
    assert "Turn 1" in battle["log"]
    fetched = client.get(f"/battles/{battle['id']}").json()
    assert fetched["log"] == battle["log"]


def test_tactic_presets_listed():
    response = client.get("/tactic-presets")
    assert response.status_code == 200
    presets = response.json()["presets"]
    assert any(item["id"] == "melee" for item in presets)
