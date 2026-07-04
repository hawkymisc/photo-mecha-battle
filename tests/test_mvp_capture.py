from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from photo_mecha_battle.api.app import app
from photo_mecha_battle.api.limits import (
    FREE_DAILY_CAPTURES,
    FREE_DAILY_MECHS,
    PREMIUM_DAILY_CAPTURES,
    PREMIUM_DAILY_MECHS,
)

client = TestClient(app)

# conftest.py の fresh_game_store フィクスチャが PMB_ADMIN_TOKEN にこの値を設定する。
ADMIN_TOKEN = "test-admin-secret"


def _image_bytes() -> bytes:
    image = Image.new("RGB", (256, 256), (230, 230, 230))
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 80, 180, 180), fill=(180, 40, 40))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _register() -> dict:
    return client.post("/auth/register", json={"name": "MVP"}).json()


def test_photo_upload_pipeline(auth_headers):
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    upload = client.post(
        "/captures/upload",
        headers=headers,
        files={"file": ("test.jpg", _image_bytes(), "image/jpeg")},
    )
    assert upload.status_code == 200
    capture_id = upload.json()["id"]

    detect = client.post(f"/captures/{capture_id}/detect").json()
    assert len(detect["candidates"]) >= 1
    bbox = detect["candidates"][0]["bbox"]

    segment = client.post(
        f"/captures/{capture_id}/segment",
        json={"label": "object", "bbox": bbox},
    ).json()
    assert segment["info_score"] > 0

    mech = client.post(
        "/mechs",
        headers=headers,
        json={"object_id": segment["id"], "form": "bird", "name": "写真メカ"},
    ).json()
    assert mech["art_url"] is not None
    assert mech["art_url"].startswith("/media/")


def test_duplicate_capture_rejected(auth_headers):
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    payload = _image_bytes()
    first = client.post(
        "/captures/upload",
        headers=headers,
        files={"file": ("test.jpg", payload, "image/jpeg")},
    )
    assert first.status_code == 200
    second = client.post(
        "/captures/upload",
        headers=headers,
        files={"file": ("test.jpg", payload, "image/jpeg")},
    )
    assert second.status_code == 409


def test_quotas_endpoint(auth_headers):
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    quotas = client.get("/users/quotas", headers=headers).json()
    assert quotas["captures"]["limit"] == FREE_DAILY_CAPTURES
    assert quotas["mechs"]["limit"] == FREE_DAILY_MECHS


def test_revenuecat_webhook_grants_entitlements():
    user = _register()
    response = client.post(
        "/billing/revenuecat/webhook",
        json={
            "event": {
                "type": "INITIAL_PURCHASE",
                "app_user_id": user["user_id"],
            }
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    keys = {item["key"] for item in body["entitlements"] if item["is_active"]}
    assert keys == {"premium_tactics", "extra_tactic_slots", "battle_log_summary", "generation_boost"}


def test_revenuecat_cancellation_revokes_entitlements():
    user = _register()
    client.post(
        "/billing/revenuecat/webhook",
        json={"event": {"type": "INITIAL_PURCHASE", "app_user_id": user["user_id"]}},
    )
    response = client.post(
        "/billing/revenuecat/webhook",
        json={"event": {"type": "CANCELLATION", "app_user_id": user["user_id"]}},
    )
    body = response.json()
    assert body["applied"] is True
    assert all(not item["is_active"] for item in body["entitlements"])


def test_face_like_capture_is_blocked(auth_headers):
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    image = Image.new("RGB", (240, 240), (235, 235, 235))
    draw = ImageDraw.Draw(image)
    draw.ellipse((50, 40, 190, 220), fill=(222, 184, 135))
    draw.ellipse((85, 100, 105, 120), fill=(40, 30, 25))
    draw.ellipse((135, 100, 155, 120), fill=(40, 30, 25))
    draw.arc((90, 150, 150, 190), start=20, end=160, fill=(90, 50, 40), width=4)
    buffer = BytesIO()
    image.save(buffer, format="JPEG")

    response = client.post(
        "/captures/upload",
        headers=headers,
        files={"file": ("face.jpg", buffer.getvalue(), "image/jpeg")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "face_detected"


def test_non_quota_entitlements_do_not_change_capture_quota(auth_headers):
    """docs/06: クォータ拡大は generation_boost のみに紐づく。他の Entitlement では拡大しない。"""
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    client.post(
        "/billing/entitlements",
        json={"entitlement_key": "premium_tactics", "is_active": True},
        headers={**headers, "X-Admin-Token": ADMIN_TOKEN},
    )
    quotas = client.get("/users/quotas", headers=headers).json()
    assert quotas["captures"]["limit"] == FREE_DAILY_CAPTURES
    assert quotas["mechs"]["limit"] == FREE_DAILY_MECHS


def test_generation_boost_entitlement_increases_capture_quota(auth_headers):
    """docs/06 生成クォータ（確定）: generation_boost 保有者は 50/日・30/日 に拡大される。"""
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    client.post(
        "/billing/entitlements",
        json={"entitlement_key": "generation_boost", "is_active": True},
        headers={**headers, "X-Admin-Token": ADMIN_TOKEN},
    )
    quotas = client.get("/users/quotas", headers=headers).json()
    assert quotas["captures"]["limit"] == PREMIUM_DAILY_CAPTURES
    assert quotas["mechs"]["limit"] == PREMIUM_DAILY_MECHS
