"""docs/09 主経路: POST /mechs（multipart 直登録）のテスト。

クライアント厚め構成では、モバイルクライアントが撮影〜特徴量算出まで行い、
crop（アルファ = 確定マスクの RGBA PNG）+ features を 1 リクエストで送る。
サーバーは phash / クォータ / 安全性 / 特徴量再計算で検証してから確定する。
"""

import json
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from photo_mecha_battle.api.app import app
from photo_mecha_battle.api.limits import FREE_DAILY_MECHS
from photo_mecha_battle.features import FEATURES_ALGO_VERSION
from photo_mecha_battle.vision.analysis import analyze_rgba_crop

client = TestClient(app)


def _crop_image(seed_color: tuple[int, int, int] = (30, 60, 160)) -> Image.Image:
    image = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((88, 10, 112, 190), fill=(*seed_color, 255))
    draw.polygon([(60, 10), (140, 10), (100, 50)], fill=(200, 40, 40, 255))
    return image


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _client_payload(image: Image.Image, name: str = "直登録メカ", **overrides) -> dict:
    """クライアントが正しく features/1.0 を実装した場合の申告値を作る。"""
    analysis = analyze_rgba_crop(image)
    payload = {
        "name": name,
        "algo_version": FEATURES_ALGO_VERSION,
        "bbox": [0.2, 0.3, 0.7, 0.8],
        "features": dict(analysis.features.__dict__),
    }
    payload.update(overrides)
    return payload


def _post_direct(headers: dict, image: Image.Image, payload: dict):
    return client.post(
        "/mechs",
        headers=headers,
        data={"payload": json.dumps(payload)},
        files={"crop": ("crop.png", _png_bytes(image), "image/png")},
    )


def test_direct_registration_returns_confirmed_mech(auth_headers):
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    image = _crop_image()
    response = _post_direct(headers, image, _client_payload(image))
    assert response.status_code == 200
    body = response.json()
    assert body["form"] in {"bird", "human", "beast"}
    assert body["form_inference_version"] == "form_inference/1.0"
    assert body["algo_version"] == FEATURES_ALGO_VERSION
    assert set(body["stats"]) == {"hp", "atk", "defense", "spd", "tec", "en", "luck"}
    assert body["art_url"] is not None and body["art_url"].startswith("/media/")
    assert body["info_score"] > 0
    # サーバー確定値の features が返る（クライアント申告と一致するケース）
    assert set(body["features"]) == set(_client_payload(image)["features"])

    # 登録済みメカとして一覧・詳細から参照できる
    listed = client.get("/mechs", headers=headers).json()["mechs"]
    assert any(entry["id"] == body["id"] for entry in listed)


def test_direct_registration_consumes_capture_and_mech_quota(auth_headers):
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    before = client.get("/users/quotas", headers=headers).json()
    image = _crop_image()
    assert _post_direct(headers, image, _client_payload(image)).status_code == 200
    after = client.get("/users/quotas", headers=headers).json()
    assert after["captures"]["used"] == before["captures"]["used"] + 1
    assert after["mechs"]["used"] == before["mechs"]["used"] + 1


def test_direct_registration_rejects_feature_mismatch(auth_headers):
    """docs/09 信頼モデル: 差分 > ε(0.05) は reject（黙って上書きしない）。"""
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    image = _crop_image()
    payload = _client_payload(image)
    payload["features"]["elongation"] = min(1.0, payload["features"]["elongation"] + 0.2)
    response = _post_direct(headers, image, payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "feature_mismatch"
    assert detail["dimension"] == "elongation"
    assert detail["tolerance"] == 0.05


def test_direct_registration_accepts_small_feature_drift(auth_headers):
    """ε 以内のずれ（プラットフォーム間の丸め差）は受理し、サーバー値で確定する。"""
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    image = _crop_image()
    payload = _client_payload(image)
    server_value = payload["features"]["visual_entropy"]
    payload["features"]["visual_entropy"] = min(1.0, server_value + 0.04)
    response = _post_direct(headers, image, payload)
    assert response.status_code == 200
    # 応答はサーバー再計算値（クライアント申告値ではない）
    assert abs(response.json()["features"]["visual_entropy"] - server_value) < 1e-9


def test_direct_registration_rejects_unsupported_algo_version(auth_headers):
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    image = _crop_image()
    payload = _client_payload(image, algo_version="features/0.9")
    response = _post_direct(headers, image, payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "unsupported_algo_version"
    assert detail["supported"] == [FEATURES_ALGO_VERSION]


def test_direct_registration_rejects_duplicate_crop(auth_headers):
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    image = _crop_image()
    payload = _client_payload(image)
    assert _post_direct(headers, image, payload).status_code == 200
    assert _post_direct(headers, image, payload).status_code == 409


def test_direct_registration_blocks_face_like_crop(auth_headers):
    """docs/02 安全性ゲートは直登録経路でもスキップされない（AGENTS.md 不変条件5）。"""
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    image = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((50, 40, 190, 220), fill=(222, 184, 135, 255))
    draw.ellipse((85, 100, 105, 120), fill=(40, 30, 25, 255))
    draw.ellipse((135, 100, 155, 120), fill=(40, 30, 25, 255))
    draw.arc((90, 150, 150, 190), start=20, end=160, fill=(90, 50, 40), width=4)
    payload = _client_payload(image, name="顔メカ")
    response = _post_direct(headers, image, payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "unsafe_capture"
    assert detail["reason"] == "face_detected"


def test_direct_registration_returns_429_when_mech_quota_exhausted(auth_headers, fresh_game_store):
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    user_id = auth_headers["user"]["user_id"]
    for _ in range(FREE_DAILY_MECHS):
        fresh_game_store.db.increment_quota(user_id, "mechs_used")
    image = _crop_image()
    response = _post_direct(headers, image, _client_payload(image))
    assert response.status_code == 429


def test_direct_registration_rejects_missing_parts(auth_headers):
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    image = _crop_image()
    # crop 欠落
    no_crop = client.post(
        "/mechs",
        headers=headers,
        data={"payload": json.dumps(_client_payload(image))},
        files={"unrelated": ("x.png", _png_bytes(image), "image/png")},
    )
    assert no_crop.status_code == 400
    # payload 欠落
    no_payload = client.post(
        "/mechs",
        headers=headers,
        files={"crop": ("crop.png", _png_bytes(image), "image/png")},
    )
    assert no_payload.status_code == 400


def test_direct_registration_rejects_invalid_payload_and_features(auth_headers):
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    image = _crop_image()
    broken_json = client.post(
        "/mechs",
        headers=headers,
        data={"payload": "{not json"},
        files={"crop": ("crop.png", _png_bytes(image), "image/png")},
    )
    assert broken_json.status_code == 422

    payload = _client_payload(image)
    payload["features"]["visual_entropy"] = 1.5  # 範囲外
    out_of_range = _post_direct(headers, image, payload)
    assert out_of_range.status_code == 422

    payload = _client_payload(image)
    payload["features"]["unknown_dimension"] = 0.5  # 未知次元
    unknown = _post_direct(headers, image, payload)
    assert unknown.status_code == 422


def test_direct_registration_rejects_undecodable_image(auth_headers):
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    image = _crop_image()
    response = client.post(
        "/mechs",
        headers=headers,
        data={"payload": json.dumps(_client_payload(image))},
        files={"crop": ("crop.png", b"not-a-png", "image/png")},
    )
    assert response.status_code == 400

    empty = client.post(
        "/mechs",
        headers=headers,
        data={"payload": json.dumps(_client_payload(image))},
        files={"crop": ("crop.png", b"", "image/png")},
    )
    assert empty.status_code == 400


def test_json_path_still_requires_valid_body(auth_headers):
    """互換経路（JSON）は従来どおり。壊れた JSON は 422。"""
    headers = {"X-User-Token": auth_headers["X-User-Token"], "Content-Type": "application/json"}
    response = client.post("/mechs", headers=headers, content="{broken")
    assert response.status_code == 422
