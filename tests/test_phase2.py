from fastapi.testclient import TestClient

from photo_mecha_battle.api.app import app
from photo_mecha_battle.tactics import ActionType, ConditionKind, TacticPreset, build_preset

client = TestClient(app)


def _register(name: str) -> dict:
    return client.post("/auth/register", json={"name": name}).json()


def _headers(token: str) -> dict[str, str]:
    return {"X-User-Token": token}


def _build_team_assets(token: str, label: str = "umbrella"):
    capture = client.post("/captures", json={"label": label}).json()
    segment = client.post(f"/captures/{capture['id']}/segment", json={"label": label}).json()
    mech_ids = []
    for form, name in [("bird", "前衛"), ("human", "中衛"), ("beast", "後衛")]:
        mech = client.post(
            "/mechs",
            json={"object_id": segment["id"], "form": form, "name": name},
            headers=_headers(token),
        ).json()
        mech_ids.append(mech["id"])

    preset = build_preset(TacticPreset.MELEE)
    tactic_ids = []
    for index in range(3):
        tactic = client.post(
            "/tactics",
            json={
                "name": f"戦術{index}",
                "slots": [
                    {
                        "condition_kind": slot.condition.kind.value,
                        "condition_threshold": slot.condition.threshold.value
                        if hasattr(slot.condition.threshold, "value")
                        else slot.condition.threshold,
                        "action": slot.action.value,
                    }
                    for slot in preset.slots
                ],
                "fallback_action": preset.fallback_action.value,
            },
            headers=_headers(token),
        ).json()
        tactic_ids.append(tactic["id"])

    team = client.post(
        "/teams",
        json={
            "name": "Test Team",
            "slots": [
                {"mech_id": mech_ids[0], "tactic_id": tactic_ids[0], "position": "front"},
                {"mech_id": mech_ids[1], "tactic_id": tactic_ids[1], "position": "middle"},
                {"mech_id": mech_ids[2], "tactic_id": tactic_ids[2], "position": "back"},
            ],
        },
        headers=_headers(token),
    ).json()
    return team


def test_register_and_persisted_mech_list():
    user = _register("Alpha")
    team = _build_team_assets(user["token"])
    mechs = client.get("/mechs", headers=_headers(user["token"])).json()["mechs"]
    assert len(mechs) == 3
    assert client.get(f"/teams/{team['id']}", headers=_headers(user["token"])).status_code == 200


def test_tactic_editor_roundtrip():
    user = _register("Tactician")
    tactic = client.post(
        "/tactics",
        json={
            "name": "カスタム",
            "slots": [
                {
                    "condition_kind": ConditionKind.SELF_HP_BELOW.value,
                    "condition_threshold": 30,
                    "action": ActionType.DEFEND.value,
                }
            ],
            "fallback_action": ActionType.NORMAL_ATTACK.value,
        },
        headers=_headers(user["token"]),
    ).json()
    updated = client.put(
        f"/tactics/{tactic['id']}",
        json={
            "name": "カスタム改",
            "slots": [
                {
                    "condition_kind": ConditionKind.TARGET_FORM.value,
                    "condition_threshold": "bird",
                    "action": ActionType.ACCURACY_ATTACK.value,
                }
            ],
            "fallback_action": ActionType.NORMAL_SHOT.value,
        },
        headers=_headers(user["token"]),
    ).json()
    assert updated["name"] == "カスタム改"
    fetched = client.get(f"/tactics/{tactic['id']}").json()
    assert fetched["fallback_action"] == ActionType.NORMAL_SHOT.value


def test_async_pvp_match_and_ranked_battle():
    player_a = _register("PlayerA")
    player_b = _register("PlayerB")
    team_a = _build_team_assets(player_a["token"])
    team_b = _build_team_assets(player_b["token"], label="stone")

    client.post("/battles/match", json={"team_id": team_a["id"]}, headers=_headers(player_a["token"]))
    match_b = client.post(
        "/battles/match",
        json={"team_id": team_b["id"]},
        headers=_headers(player_b["token"]),
    ).json()
    assert match_b["matched"] is True

    battle = client.post(
        "/battles/ranked",
        json={"team_id": team_a["id"], "seed": 42},
        headers=_headers(player_a["token"]),
    ).json()
    assert "Turn 1" in battle["log"]
    ranking = client.get("/ranking").json()["entries"]
    assert len(ranking) >= 2


def test_invalid_token_returns_401():
    response = client.get("/auth/me", headers={"X-User-Token": "invalid"})
    assert response.status_code == 401


def test_ranked_battle_against_cpu_updates_rating():
    user = _register("Solo")
    team = _build_team_assets(user["token"])
    battle = client.post(
        "/battles/ranked",
        json={"team_id": team["id"], "seed": 7},
        headers=_headers(user["token"]),
    ).json()
    assert "rating" in battle
    assert client.get("/ranking").json()["entries"]


def test_billing_entitlement_stub():
    user = _register("Buyer")
    status = client.get("/billing/status", headers=_headers(user["token"])).json()
    assert "entitlements" in status
    updated = client.post(
        "/billing/entitlements",
        json={"entitlement_key": "premium_tactics", "is_active": True},
        headers=_headers(user["token"]),
    ).json()
    assert any(item["key"] == "premium_tactics" and item["is_active"] for item in updated["entitlements"])
