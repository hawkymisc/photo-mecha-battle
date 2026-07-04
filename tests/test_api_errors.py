from fastapi.testclient import TestClient

from photo_mecha_battle.api.app import app

client = TestClient(app)


def test_get_capture_detect_endpoint():
    capture = client.post("/captures", json={"label": "umbrella"}).json()
    detected = client.post(f"/captures/{capture['id']}/detect").json()
    assert detected["candidates"][0]["label"] == "umbrella"


def test_analyze_object_endpoint():
    capture = client.post("/captures", json={"label": "umbrella"}).json()
    segment = client.post(f"/captures/{capture['id']}/segment", json={"label": "umbrella"}).json()
    analyzed = client.post(f"/objects/{segment['id']}/analyze").json()
    assert analyzed["info_score"] > 0


def test_capture_not_found_returns_404():
    response = client.post("/captures/missing/detect")
    assert response.status_code == 404


def test_segment_unknown_capture_returns_404():
    response = client.post("/captures/missing/segment", json={"label": "umbrella"})
    assert response.status_code == 404


def test_analyze_unknown_object_returns_404():
    response = client.post("/objects/missing/analyze")
    assert response.status_code == 404


def test_create_mech_with_unknown_object_returns_404(auth_headers):
    response = client.post(
        "/mechs",
        json={"object_id": "missing", "form": "bird", "name": "ghost"},
        headers={"X-User-Token": auth_headers["X-User-Token"]},
    )
    assert response.status_code == 404


def test_get_unknown_mech_returns_404():
    assert client.get("/mechs/missing").status_code == 404


def test_battle_requires_three_slots(auth_headers):
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    capture = client.post("/captures", json={"label": "umbrella"}).json()
    segment = client.post(f"/captures/{capture['id']}/segment", json={"label": "umbrella"}).json()
    mech = client.post(
        "/mechs",
        json={"object_id": segment["id"], "form": "bird", "name": "solo"},
        headers=headers,
    ).json()
    response = client.post(
        "/battles",
        json={
            "team_name": "Solo",
            "seed": 1,
            "slots": [{"mech_id": mech["id"], "position": "front", "preset": "melee"}],
        },
    )
    assert response.status_code == 400


def test_battle_rejects_unknown_mech():
    response = client.post(
        "/battles",
        json={
            "team_name": "Bad",
            "seed": 1,
            "slots": [
                {"mech_id": "missing", "position": "front", "preset": "melee"},
                {"mech_id": "missing", "position": "middle", "preset": "melee"},
                {"mech_id": "missing", "position": "back", "preset": "melee"},
            ],
        },
    )
    assert response.status_code == 404


def test_get_unknown_battle_returns_404(auth_headers):
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    assert client.get("/battles/missing", headers=headers).status_code == 404


def test_get_battle_without_token_returns_401():
    assert client.get("/battles/missing").status_code == 401


def test_get_mech_and_ranking_endpoints(auth_headers):
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    capture = client.post("/captures", json={"label": "stone"}).json()
    segment = client.post(f"/captures/{capture['id']}/segment", json={"label": "stone"}).json()
    mech = client.post(
        "/mechs",
        json={"object_id": segment["id"], "form": "beast", "name": "石メカ"},
        headers=headers,
    ).json()
    fetched = client.get(f"/mechs/{mech['id']}").json()
    assert fetched["name"] == "石メカ"
    ranking = client.get("/ranking").json()
    assert ranking["entries"][0]["rating"] == 1000
