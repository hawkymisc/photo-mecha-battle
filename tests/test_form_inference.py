"""PLAN D-013: メカ型の自動推定（docs/03 `form_inference/1.0`）。

メカ型（bird/human/beast）はプレイヤー選択ではなく、FeatureVector から
決定的に自動推定する（PO 決定済み: config/po_pending_decisions.json
form_inference_policy）。`POST /mechs` はクライアント送信の `form` を
無視し、サーバー推定で確定する（docs/09 信頼モデル）。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from photo_mecha_battle.api.app import app
from photo_mecha_battle.features import FeatureVector
from photo_mecha_battle.mech_stats import (
    FORM_INFERENCE_VERSION,
    _resolve_form,
    form_scores,
    infer_form,
)
from photo_mecha_battle.models import MechForm

client = TestClient(app)


def _vector(**overrides: float) -> FeatureVector:
    defaults = dict(
        visual_entropy=0.5,
        edge_complexity=0.5,
        color_diversity=0.5,
        shape_complexity=0.5,
        semantic_rarity=0.5,
        capture_quality=0.9,
        size_balance=0.5,
        area=0.5,
        elongation=0.5,
        roundness=0.5,
        symmetry=0.5,
    )
    defaults.update(overrides)
    return FeatureVector(**defaults)


# docs/03 代表例（PoC デモ用プリセット特徴量）
UMBRELLA = _vector(elongation=0.82, roundness=0.30, area=0.45, symmetry=0.55, edge_complexity=0.42, shape_complexity=0.50)
STONE = _vector(elongation=0.20, roundness=0.85, area=0.70, symmetry=0.50, edge_complexity=0.30, shape_complexity=0.35)
PEN = _vector(elongation=0.45, roundness=0.55, area=0.40, symmetry=0.75, edge_complexity=0.65, shape_complexity=0.60)


def test_version_constant():
    assert FORM_INFERENCE_VERSION == "form_inference/1.0"


def test_representative_examples_from_docs03():
    """docs/03 代表例: 傘→bird（高 elongation）、石→beast（高 roundness+area）、ペン→human。"""
    assert infer_form(UMBRELLA) == MechForm.BIRD
    assert infer_form(STONE) == MechForm.BEAST
    assert infer_form(PEN) == MechForm.HUMAN


def test_inference_is_deterministic():
    """同一 FeatureVector に対し常に同一の form を返す。"""
    for _ in range(5):
        assert infer_form(UMBRELLA) == MechForm.BIRD
        assert infer_form(STONE) == MechForm.BEAST


def test_scores_are_weighted_sums_per_docs03():
    """スコア式の固定（docs/03 の加重和と一致すること）。"""
    scores = form_scores(UMBRELLA)
    assert scores[MechForm.BIRD] == (
        0.50 * 0.82 + 0.30 * (1 - 0.30) + 0.20 * (1 - abs(0.45 - 0.35))
    )
    assert scores[MechForm.BEAST] == (0.45 * 0.30 + 0.35 * 0.45 + 0.20 * (1 - 0.82))
    assert scores[MechForm.HUMAN] == (
        0.35 * 0.55 + 0.30 * 0.42 + 0.20 * (1 - abs(0.82 - 0.30)) + 0.15 * 0.50
    )


def test_tiebreak_priority_human_bird_beast():
    """同点（差 1e-9 未満）のタイブレークは human > bird > beast の機械的順序。"""
    tied = {MechForm.BIRD: 0.5, MechForm.HUMAN: 0.5, MechForm.BEAST: 0.5}
    assert _resolve_form(tied) == MechForm.HUMAN

    bird_vs_beast = {MechForm.BIRD: 0.5, MechForm.HUMAN: 0.2, MechForm.BEAST: 0.5}
    assert _resolve_form(bird_vs_beast) == MechForm.BIRD

    # 1e-9 未満の差は同点扱い
    nearly_tied = {MechForm.BIRD: 0.5, MechForm.HUMAN: 0.5 - 1e-10, MechForm.BEAST: 0.3}
    assert _resolve_form(nearly_tied) == MechForm.HUMAN

    # 1e-9 以上の差は同点ではない
    distinct = {MechForm.BIRD: 0.5, MechForm.HUMAN: 0.5 - 1e-8, MechForm.BEAST: 0.3}
    assert _resolve_form(distinct) == MechForm.BIRD


def test_boundary_all_zero_and_all_one_features():
    """境界値: 全次元 0.0 / 1.0 でも例外なくいずれかの型に決まる。"""
    zero = _vector(**{k: 0.0 for k in (
        "visual_entropy", "edge_complexity", "color_diversity", "shape_complexity",
        "semantic_rarity", "capture_quality", "size_balance", "area",
        "elongation", "roundness", "symmetry",
    )})
    one = _vector(**{k: 1.0 for k in (
        "visual_entropy", "edge_complexity", "color_diversity", "shape_complexity",
        "semantic_rarity", "capture_quality", "size_balance", "area",
        "elongation", "roundness", "symmetry",
    )})
    assert infer_form(zero) in tuple(MechForm)
    assert infer_form(one) in tuple(MechForm)


def _create_mech_via_api(auth_headers, label: str, payload_extra: dict | None = None) -> dict:
    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    capture = client.post("/captures", json={"label": label}).json()
    segment = client.post(
        f"/captures/{capture['id']}/segment",
        json={"label": label},
    ).json()
    body = {"object_id": segment["id"], "name": f"{label}メカ"}
    if payload_extra:
        body.update(payload_extra)
    response = client.post("/mechs", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_post_mechs_infers_form_server_side(auth_headers):
    """`POST /mechs` は form 無しで受理し、サーバー推定の form と版数を返す。"""
    mech = _create_mech_via_api(auth_headers, "umbrella")
    assert mech["form"] == "bird"
    assert mech["form_inference_version"] == "form_inference/1.0"

    stone_mech = _create_mech_via_api(auth_headers, "stone")
    assert stone_mech["form"] == "beast"


def test_post_mechs_ignores_client_form(auth_headers):
    """クライアントが form を送っても 400 にせず、サーバー推定で上書きする。"""
    mech = _create_mech_via_api(auth_headers, "umbrella", {"form": "beast"})
    assert mech["form"] == "bird"  # クライアント指定の beast は無視される


def test_post_mechs_works_for_db_persisted_object_after_restart(fresh_game_store, auth_headers, monkeypatch):
    """プロセス再起動後（セッション objects が空）でも、DB 保存済み object からメカを作れる。

    `POST /mechs` の存在チェックは DB 側の extracted_objects も許可するため、
    推定・生成も DB の features_json から FeatureVector を復元して動く必要がある。
    """
    from io import BytesIO

    from PIL import Image, ImageDraw

    from photo_mecha_battle.api import app as app_module
    from photo_mecha_battle.api.game_store import GameStore

    headers = {"X-User-Token": auth_headers["X-User-Token"]}
    image = Image.new("RGB", (256, 256), (230, 230, 230))
    ImageDraw.Draw(image).rectangle((80, 80, 180, 180), fill=(180, 40, 40))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")

    upload = client.post(
        "/captures/upload",
        headers=headers,
        files={"file": ("restart.jpg", buffer.getvalue(), "image/jpeg")},
    ).json()
    detect = client.post(f"/captures/{upload['id']}/detect").json()
    segment = client.post(
        f"/captures/{upload['id']}/segment",
        json={"label": "object", "bbox": detect["candidates"][0]["bbox"]},
    ).json()

    # 再起動をシミュレート: 同じ DB を共有する新しい GameStore（セッション objects は空）
    restarted = GameStore(fresh_game_store.db, data_dir=fresh_game_store.image_storage.root)
    monkeypatch.setattr(app_module, "store", restarted)
    assert segment["id"] not in restarted.objects

    response = client.post(
        "/mechs",
        headers=headers,
        json={"object_id": segment["id"], "name": "再起動後メカ"},
    )
    assert response.status_code == 200, response.text
    mech = response.json()
    assert mech["form"] in ("bird", "human", "beast")
    assert mech["form_inference_version"] == "form_inference/1.0"
