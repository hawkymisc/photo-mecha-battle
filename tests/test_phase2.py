from fastapi.testclient import TestClient

from photo_mecha_battle.api.app import app
from photo_mecha_battle.api.limits import (
    FREE_DAILY_CAPTURES,
    FREE_DAILY_MECHS,
    PREMIUM_DAILY_CAPTURES,
    PREMIUM_DAILY_MECHS,
)
from photo_mecha_battle.tactics import ActionType, ConditionKind, TacticPreset, build_preset

client = TestClient(app)

# conftest.py の fresh_game_store フィクスチャが PMB_ADMIN_TOKEN にこの値を設定する。
ADMIN_TOKEN = "test-admin-secret"


def _register(name: str) -> dict:
    return client.post("/auth/register", json={"name": name}).json()


def _headers(token: str) -> dict[str, str]:
    return {"X-User-Token": token}


def _admin_headers(token: str) -> dict[str, str]:
    return {"X-User-Token": token, "X-Admin-Token": ADMIN_TOKEN}


def _admin_headers(token: str) -> dict[str, str]:
    return {"X-User-Token": token, "X-Admin-Token": ADMIN_TOKEN}


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


def test_ranked_battle_ignores_client_seed_and_generates_server_seed():
    user = _register("SeedTester")
    team = _build_team_assets(user["token"])

    battle = client.post(
        "/battles/ranked",
        json={"team_id": team["id"], "seed": 42},
        headers=_headers(user["token"]),
    ).json()

    # docs/09 信頼モデル / PLAN D-007: クライアント送信 seed は無視され、サーバーが生成する。
    assert battle["seed"] != 42
    assert isinstance(battle["seed"], int)

    stored = client.get(f"/battles/{battle['id']}", headers=_headers(user["token"])).json()
    assert stored["seed"] == battle["seed"]


def test_ranked_battle_without_seed_field_still_succeeds():
    user = _register("SeedOmitted")
    team = _build_team_assets(user["token"])

    response = client.post(
        "/battles/ranked",
        json={"team_id": team["id"]},
        headers=_headers(user["token"]),
    )
    assert response.status_code == 200
    assert isinstance(response.json()["seed"], int)


def test_team_update_roundtrip():
    user = _register("Editor")
    team = _build_team_assets(user["token"])
    original = client.get(f"/teams/{team['id']}", headers=_headers(user["token"])).json()

    preset = build_preset(TacticPreset.SNIPER)
    new_tactic = client.post(
        "/tactics",
        json={
            "name": "改訂戦術",
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
        headers=_headers(user["token"]),
    ).json()

    updated = client.put(
        f"/teams/{team['id']}",
        json={
            "name": "Renamed Team",
            "slots": [
                {"mech_id": original["front_mech_id"], "tactic_id": new_tactic["id"], "position": "front"},
                {"mech_id": original["middle_mech_id"], "tactic_id": original["middle_tactic_id"], "position": "middle"},
                {"mech_id": original["back_mech_id"], "tactic_id": original["back_tactic_id"], "position": "back"},
            ],
        },
        headers=_headers(user["token"]),
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed Team"

    fetched = client.get(f"/teams/{team['id']}", headers=_headers(user["token"])).json()
    assert fetched["front_tactic_id"] == new_tactic["id"]


def test_team_update_requires_ownership():
    owner = _register("Owner")
    intruder = _register("Intruder")
    team = _build_team_assets(owner["token"])
    original = client.get(f"/teams/{team['id']}", headers=_headers(owner["token"])).json()

    response = client.put(
        f"/teams/{team['id']}",
        json={
            "name": "Hijacked",
            "slots": [
                {"mech_id": original["front_mech_id"], "tactic_id": original["front_tactic_id"], "position": "front"},
                {"mech_id": original["middle_mech_id"], "tactic_id": original["middle_tactic_id"], "position": "middle"},
                {"mech_id": original["back_mech_id"], "tactic_id": original["back_tactic_id"], "position": "back"},
            ],
        },
        headers=_headers(intruder["token"]),
    )
    assert response.status_code == 403


def test_team_update_unknown_team_returns_404():
    user = _register("Ghost")
    team = _build_team_assets(user["token"])
    original = client.get(f"/teams/{team['id']}", headers=_headers(user["token"])).json()
    response = client.put(
        "/teams/missing",
        json={
            "name": "Ghost Team",
            "slots": [
                {"mech_id": original["front_mech_id"], "tactic_id": original["front_tactic_id"], "position": "front"},
                {"mech_id": original["middle_mech_id"], "tactic_id": original["middle_tactic_id"], "position": "middle"},
                {"mech_id": original["back_mech_id"], "tactic_id": original["back_tactic_id"], "position": "back"},
            ],
        },
        headers=_headers(user["token"]),
    )
    assert response.status_code == 404


def test_tactic_simulate_endpoint():
    user = _register("Simulator")
    team = _build_team_assets(user["token"])
    row = client.get(f"/teams/{team['id']}", headers=_headers(user["token"])).json()

    response = client.post(
        f"/tactics/{row['front_tactic_id']}/simulate",
        json={"mech_id": row["front_mech_id"], "seed": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert "Turn 1" in body["log"]
    assert body["seed"] == 3


def test_tactic_simulate_unknown_tactic_returns_404():
    response = client.post(
        "/tactics/missing/simulate",
        json={"mech_id": "missing", "seed": 1},
    )
    assert response.status_code == 404


def test_tactic_simulate_unknown_mech_returns_404():
    user = _register("SimulatorTwo")
    team = _build_team_assets(user["token"])
    row = client.get(f"/teams/{team['id']}", headers=_headers(user["token"])).json()
    response = client.post(
        f"/tactics/{row['front_tactic_id']}/simulate",
        json={"mech_id": "missing", "seed": 1},
    )
    assert response.status_code == 404


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


def test_ranked_battle_view_requires_authentication():
    user = _register("ViewerNoAuth")
    team = _build_team_assets(user["token"])
    battle = client.post(
        "/battles/ranked",
        json={"team_id": team["id"], "seed": 3},
        headers=_headers(user["token"]),
    ).json()
    response = client.get(f"/battles/{battle['id']}")
    assert response.status_code == 401


def test_ranked_battle_view_forbidden_for_third_party():
    player_a = _register("ViewA")
    player_b = _register("ViewB")
    outsider = _register("Outsider")
    team_a = _build_team_assets(player_a["token"])
    team_b = _build_team_assets(player_b["token"], label="stone")

    client.post("/battles/match", json={"team_id": team_a["id"]}, headers=_headers(player_a["token"]))
    client.post("/battles/match", json={"team_id": team_b["id"]}, headers=_headers(player_b["token"]))
    battle = client.post(
        "/battles/ranked",
        json={"team_id": team_a["id"], "seed": 11},
        headers=_headers(player_a["token"]),
    ).json()

    forbidden = client.get(f"/battles/{battle['id']}", headers=_headers(outsider["token"]))
    assert forbidden.status_code == 403

    as_a = client.get(f"/battles/{battle['id']}", headers=_headers(player_a["token"]))
    assert as_a.status_code == 200
    as_b = client.get(f"/battles/{battle['id']}", headers=_headers(player_b["token"]))
    assert as_b.status_code == 200


def test_cpu_ranked_battle_view_restricted_to_player_a():
    user = _register("CpuSolo")
    outsider = _register("CpuOutsider")
    team = _build_team_assets(user["token"])
    battle = client.post(
        "/battles/ranked",
        json={"team_id": team["id"], "seed": 5},
        headers=_headers(user["token"]),
    ).json()

    forbidden = client.get(f"/battles/{battle['id']}", headers=_headers(outsider["token"]))
    assert forbidden.status_code == 403
    allowed = client.get(f"/battles/{battle['id']}", headers=_headers(user["token"]))
    assert allowed.status_code == 200


def test_demo_battle_view_allowed_for_any_authenticated_user():
    user = _register("DemoViewer")
    capture = client.post("/captures", json={"label": "umbrella"}).json()
    segment = client.post(f"/captures/{capture['id']}/segment", json={"label": "umbrella"}).json()
    mech = client.post(
        "/mechs",
        json={"object_id": segment["id"], "form": "bird", "name": "デモメカ"},
        headers=_headers(user["token"]),
    ).json()
    battle = client.post(
        "/battles",
        json={
            "team_name": "Demo Team",
            "seed": 9,
            "slots": [
                {"mech_id": mech["id"], "position": "front", "preset": "melee"},
                {"mech_id": mech["id"], "position": "middle", "preset": "bombardment"},
                {"mech_id": mech["id"], "position": "back", "preset": "sniper"},
            ],
        },
    ).json()

    unauthenticated = client.get(f"/battles/{battle['id']}")
    assert unauthenticated.status_code == 401
    fetched = client.get(f"/battles/{battle['id']}", headers=_headers(user["token"]))
    assert fetched.status_code == 200


def test_billing_entitlement_stub():
    user = _register("Buyer")
    status = client.get("/billing/status", headers=_headers(user["token"])).json()
    assert "entitlements" in status
    updated = client.post(
        "/billing/entitlements",
        json={"entitlement_key": "premium_tactics", "is_active": True},
        headers=_admin_headers(user["token"]),
    ).json()
    assert any(item["key"] == "premium_tactics" and item["is_active"] for item in updated["entitlements"])


def test_billing_entitlement_rejects_unknown_key():
    user = _register("BadBuyer")
    response = client.post(
        "/billing/entitlements",
        json={"entitlement_key": "unlimited_damage", "is_active": True},
        headers=_admin_headers(user["token"]),
    )
    assert response.status_code == 400


def test_billing_entitlement_requires_admin_token():
    """PLAN D-004: 一般ユーザーが自分の Entitlement を管理者トークン無しで変更できない。"""
    user = _register("SelfServe")
    response = client.post(
        "/billing/entitlements",
        json={"entitlement_key": "premium_tactics", "is_active": True},
        headers=_headers(user["token"]),
    )
    assert response.status_code == 403


def test_billing_entitlement_rejects_wrong_admin_token():
    user = _register("Impersonator")
    response = client.post(
        "/billing/entitlements",
        json={"entitlement_key": "premium_tactics", "is_active": True},
        headers={"X-User-Token": user["token"], "X-Admin-Token": "not-the-real-secret"},
    )
    assert response.status_code == 403


def test_billing_entitlement_disabled_when_admin_token_not_configured(monkeypatch):
    """PLAN D-004: PMB_ADMIN_TOKEN 未設定（本番デフォルト）ではエンドポイントを事実上無効化する。"""
    user = _register("ProdLike")
    monkeypatch.delenv("PMB_ADMIN_TOKEN", raising=False)
    response = client.post(
        "/billing/entitlements",
        json={"entitlement_key": "premium_tactics", "is_active": True},
        headers=_admin_headers(user["token"]),
    )
    assert response.status_code == 403


def test_get_billing_entitlements_endpoint():
    user = _register("Lister")
    client.post(
        "/billing/entitlements",
        json={"entitlement_key": "cosmetic_pack_access", "is_active": True},
        headers=_admin_headers(user["token"]),
    )
    listed = client.get("/billing/entitlements", headers=_headers(user["token"])).json()
    assert any(
        item["key"] == "cosmetic_pack_access" and item["is_active"] for item in listed["entitlements"]
    )


def test_billing_sync_reconciles_known_entitlements_only():
    user = _register("Syncer")
    headers = _headers(user["token"])

    synced = client.post(
        "/billing/sync",
        json={"active_entitlements": ["premium_tactics", "battle_log_summary", "not_a_real_key"]},
        headers=headers,
    ).json()
    active_keys = {item["key"] for item in synced["entitlements"] if item["is_active"]}
    assert active_keys == {"premium_tactics", "battle_log_summary"}

    # A subsequent sync without a previously-active key revokes it (full snapshot semantics).
    resynced = client.post(
        "/billing/sync",
        json={"active_entitlements": ["extra_tactic_slots"]},
        headers=headers,
    ).json()
    active_keys_after = {item["key"] for item in resynced["entitlements"] if item["is_active"]}
    assert active_keys_after == {"extra_tactic_slots"}


def test_billing_sync_does_not_change_generation_quota():
    user = _register("SyncQuota")
    headers = _headers(user["token"])
    client.post("/billing/sync", json={"active_entitlements": ["premium_tactics"]}, headers=headers)
    quotas = client.get("/users/quotas", headers=headers).json()
    assert quotas["captures"]["limit"] == FREE_DAILY_CAPTURES
    assert quotas["mechs"]["limit"] == FREE_DAILY_MECHS


def test_billing_sync_with_generation_boost_increases_quota():
    user = _register("SyncBoost")
    headers = _headers(user["token"])
    client.post("/billing/sync", json={"active_entitlements": ["generation_boost"]}, headers=headers)
    quotas = client.get("/users/quotas", headers=headers).json()
    assert quotas["captures"]["limit"] == PREMIUM_DAILY_CAPTURES
    assert quotas["mechs"]["limit"] == PREMIUM_DAILY_MECHS
