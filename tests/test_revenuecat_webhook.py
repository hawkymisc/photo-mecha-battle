"""PLAN D-005: POST /billing/revenuecat/webhook のテストマトリクス。

docs/06 Webhook イベント処理（MVP）: entitlement_ids に基づく個別付与/失効、
event.id による冪等性、Authorization ヘッダーによる認証を検証する。
"""

from fastapi.testclient import TestClient

from photo_mecha_battle.api.app import app
from tests.conftest import REVENUECAT_WEBHOOK_SECRET

client = TestClient(app)


def _register() -> dict:
    return client.post("/auth/register", json={"name": "Billing"}).json()


def _post_event(event: dict, *, authorization: str | None = REVENUECAT_WEBHOOK_SECRET):
    headers = {"Authorization": authorization} if authorization is not None else {}
    return client.post("/billing/revenuecat/webhook", headers=headers, json={"event": event})


def test_initial_purchase_grants_only_listed_entitlements():
    user = _register()
    response = _post_event(
        {
            "id": "evt-grant-1",
            "type": "INITIAL_PURCHASE",
            "app_user_id": user["user_id"],
            "entitlement_ids": ["premium_tactics", "generation_boost"],
        }
    )
    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    active_keys = {item["key"] for item in body["entitlements"] if item["is_active"]}
    assert active_keys == {"premium_tactics", "generation_boost"}


def test_renewal_and_uncancellation_are_treated_as_grant_events():
    user = _register()
    for event_id, event_type in [("evt-renew", "RENEWAL"), ("evt-uncancel", "UNCANCELLATION")]:
        response = _post_event(
            {
                "id": event_id,
                "type": event_type,
                "app_user_id": user["user_id"],
                "entitlement_ids": ["cosmetic_pack_access"],
            }
        )
        assert response.json()["applied"] is True


def test_cancellation_revokes_only_listed_entitlements():
    user = _register()
    _post_event(
        {
            "id": "evt-grant-2",
            "type": "INITIAL_PURCHASE",
            "app_user_id": user["user_id"],
            "entitlement_ids": ["premium_tactics", "extra_tactic_slots"],
        }
    )
    response = _post_event(
        {
            "id": "evt-cancel-1",
            "type": "CANCELLATION",
            "app_user_id": user["user_id"],
            "entitlement_ids": ["premium_tactics"],
        }
    )
    body = response.json()
    assert body["applied"] is True
    by_key = {item["key"]: item["is_active"] for item in body["entitlements"]}
    assert by_key["premium_tactics"] is False
    assert by_key["extra_tactic_slots"] is True


def test_expiration_is_treated_as_revoke_event():
    user = _register()
    _post_event(
        {
            "id": "evt-grant-3",
            "type": "INITIAL_PURCHASE",
            "app_user_id": user["user_id"],
            "entitlement_ids": ["battle_log_summary"],
        }
    )
    response = _post_event(
        {
            "id": "evt-expire-1",
            "type": "EXPIRATION",
            "app_user_id": user["user_id"],
            "entitlement_ids": ["battle_log_summary"],
        }
    )
    body = response.json()
    assert body["applied"] is True
    assert all(not item["is_active"] for item in body["entitlements"])


def test_deprecated_singular_entitlement_id_is_used_as_fallback():
    user = _register()
    response = _post_event(
        {
            "id": "evt-legacy-1",
            "type": "INITIAL_PURCHASE",
            "app_user_id": user["user_id"],
            "entitlement_id": "premium_tactics",
        }
    )
    body = response.json()
    assert body["applied"] is True
    active_keys = {item["key"] for item in body["entitlements"] if item["is_active"]}
    assert active_keys == {"premium_tactics"}


def test_unknown_event_type_is_ignored():
    user = _register()
    response = _post_event(
        {
            "id": "evt-unknown-1",
            "type": "TRANSFER",
            "app_user_id": user["user_id"],
            "entitlement_ids": ["premium_tactics"],
        }
    )
    body = response.json()
    assert body["applied"] is False
    assert body["reason"] == "ignored_event"


def test_unknown_app_user_id_is_reported():
    response = _post_event(
        {
            "id": "evt-unknown-user-1",
            "type": "INITIAL_PURCHASE",
            "app_user_id": "does-not-exist",
            "entitlement_ids": ["premium_tactics"],
        }
    )
    body = response.json()
    assert body["applied"] is False
    assert body["reason"] == "user_not_found"


def test_missing_entitlement_ids_is_reported_and_not_applied():
    user = _register()
    response = _post_event(
        {
            "id": "evt-missing-ent-1",
            "type": "INITIAL_PURCHASE",
            "app_user_id": user["user_id"],
        }
    )
    body = response.json()
    assert body["applied"] is False
    assert body["reason"] == "missing_entitlement_ids"


def test_entitlement_ids_with_only_unknown_keys_is_reported():
    user = _register()
    response = _post_event(
        {
            "id": "evt-unknown-ent-1",
            "type": "INITIAL_PURCHASE",
            "app_user_id": user["user_id"],
            "entitlement_ids": ["some_future_entitlement"],
        }
    )
    body = response.json()
    assert body["applied"] is False
    assert body["reason"] == "no_known_entitlements"


def test_unknown_entitlement_ids_are_filtered_but_known_ones_still_applied():
    user = _register()
    response = _post_event(
        {
            "id": "evt-mixed-ent-1",
            "type": "INITIAL_PURCHASE",
            "app_user_id": user["user_id"],
            "entitlement_ids": ["premium_tactics", "some_future_entitlement"],
        }
    )
    body = response.json()
    assert body["applied"] is True
    active_keys = {item["key"] for item in body["entitlements"] if item["is_active"]}
    assert active_keys == {"premium_tactics"}


def test_duplicate_event_id_is_not_applied_twice():
    user = _register()
    event = {
        "id": "evt-dup-1",
        "type": "INITIAL_PURCHASE",
        "app_user_id": user["user_id"],
        "entitlement_ids": ["premium_tactics"],
    }
    first = _post_event(event)
    assert first.json()["applied"] is True

    second = _post_event(event)
    body = second.json()
    assert body["applied"] is False
    assert body["reason"] == "duplicate_event"


def test_missing_app_user_id_returns_400():
    response = _post_event({"id": "evt-no-user-1", "type": "INITIAL_PURCHASE", "entitlement_ids": ["premium_tactics"]})
    assert response.status_code == 400


def test_missing_event_id_returns_400():
    user = _register()
    response = _post_event(
        {"type": "INITIAL_PURCHASE", "app_user_id": user["user_id"], "entitlement_ids": ["premium_tactics"]}
    )
    assert response.status_code == 400


def test_missing_authorization_header_returns_401():
    user = _register()
    response = _post_event(
        {
            "id": "evt-auth-1",
            "type": "INITIAL_PURCHASE",
            "app_user_id": user["user_id"],
            "entitlement_ids": ["premium_tactics"],
        },
        authorization=None,
    )
    assert response.status_code == 401


def test_wrong_authorization_header_returns_401():
    user = _register()
    response = _post_event(
        {
            "id": "evt-auth-2",
            "type": "INITIAL_PURCHASE",
            "app_user_id": user["user_id"],
            "entitlement_ids": ["premium_tactics"],
        },
        authorization="wrong-secret",
    )
    assert response.status_code == 401


def test_webhook_disabled_when_secret_not_configured(monkeypatch):
    monkeypatch.delenv("PMB_REVENUECAT_WEBHOOK_SECRET", raising=False)
    user = _register()
    response = _post_event(
        {
            "id": "evt-auth-3",
            "type": "INITIAL_PURCHASE",
            "app_user_id": user["user_id"],
            "entitlement_ids": ["premium_tactics"],
        }
    )
    assert response.status_code == 401
