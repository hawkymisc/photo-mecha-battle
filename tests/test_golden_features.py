"""features/1.0 ゴールデンフィクスチャの整合テスト。

tests/golden/ の PNG + golden_features.json は iOS / Android クライアントの
特徴量移植（docs/09 テスト方針）の正本。このテストはサーバー実装が
フィクスチャと完全一致することを固定し、アルゴリズム変更時に
algo_version の更新・フィクスチャ再生成を強制する。

再生成: python scripts/generate_golden_features.py
"""

import json
from pathlib import Path

import pytest
from PIL import Image

from photo_mecha_battle.features import FEATURES_ALGO_VERSION
from photo_mecha_battle.mech_stats import (
    FORM_INFERENCE_VERSION,
    compute_info_score,
    infer_form,
)
from photo_mecha_battle.vision.analysis import analyze_rgba_crop

GOLDEN_DIR = Path(__file__).parent / "golden"
MANIFEST = json.loads((GOLDEN_DIR / "golden_features.json").read_text(encoding="utf-8"))


def test_manifest_versions_match_implementation():
    assert MANIFEST["algo_version"] == FEATURES_ALGO_VERSION
    assert MANIFEST["form_inference_version"] == FORM_INFERENCE_VERSION


@pytest.mark.parametrize("case_name", sorted(MANIFEST["cases"]))
def test_golden_case_matches_server_implementation(case_name):
    case = MANIFEST["cases"][case_name]
    crop = Image.open(GOLDEN_DIR / case["image"])
    analysis = analyze_rgba_crop(crop)

    assert analysis.background_mix == pytest.approx(case["background_mix"], abs=1e-9)
    for dimension, expected in case["features"].items():
        actual = getattr(analysis.features, dimension)
        assert actual == pytest.approx(expected, abs=1e-9), dimension
    assert compute_info_score(analysis.features) == pytest.approx(case["info_score"], abs=1e-9)
    assert infer_form(analysis.features).value == case["form"]
