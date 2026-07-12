"""features/1.0 のゴールデンフィクスチャ生成スクリプト。

docs/09 テスト方針「共有ロジックは同一入力でクライアント/サーバー一致テスト」のための
正本データを生成する。決定的に描画した RGBA crop（アルファ = 確定マスク）と、
サーバー実装（`analyze_rgba_crop`）で算出した特徴量・info_score・型を JSON に書き出す。

iOS / Android クライアントの features/1.0 移植は、この PNG を入力として同じ値
（許容差 ε=0.05 以内、docs/09）を再現しなければならない。

再生成: python scripts/generate_golden_features.py
出力: tests/golden/*.png, tests/golden/golden_features.json
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from photo_mecha_battle.features import FEATURES_ALGO_VERSION
from photo_mecha_battle.mech_stats import FORM_INFERENCE_VERSION, compute_info_score, infer_form
from photo_mecha_battle.vision.analysis import analyze_rgba_crop

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "tests" / "golden"


def _elongated_crop() -> Image.Image:
    """細長い高コントラスト被写体（bird 型に寄る想定の傘・ペン類の proxy）。"""
    image = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((88, 10, 112, 190), fill=(30, 60, 160, 255))
    draw.polygon([(60, 10), (140, 10), (100, 50)], fill=(200, 40, 40, 255))
    return image


def _round_crop() -> Image.Image:
    """丸く画面占有の大きい被写体（beast 型に寄る想定の石・ボール類の proxy）。"""
    image = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((20, 30, 180, 180), fill=(110, 90, 70, 255))
    draw.ellipse((60, 70, 100, 110), fill=(90, 70, 50, 255))
    return image


def _symmetric_crop() -> Image.Image:
    """左右対称でエッジの多い被写体（human 型に寄る想定の工具類の proxy）。"""
    image = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 20, 120, 180), fill=(60, 140, 60, 255))
    for y in range(30, 180, 20):
        draw.rectangle((50, y, 150, y + 8), fill=(220, 180, 40, 255))
    return image


GOLDEN_CASES = {
    "elongated": _elongated_crop,
    "round": _round_crop,
    "symmetric": _symmetric_crop,
}


def generate() -> dict[str, object]:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "algo_version": FEATURES_ALGO_VERSION,
        "form_inference_version": FORM_INFERENCE_VERSION,
        "tolerance": 0.05,
        "cases": {},
    }
    for name, builder in GOLDEN_CASES.items():
        crop = builder()
        image_name = f"{name}.png"
        crop.save(GOLDEN_DIR / image_name)
        analysis = analyze_rgba_crop(crop)
        manifest["cases"][name] = {
            "image": image_name,
            "background_mix": analysis.background_mix,
            "features": analysis.features.__dict__,
            "info_score": compute_info_score(analysis.features),
            "form": infer_form(analysis.features).value,
        }
    (GOLDEN_DIR / "golden_features.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    result = generate()
    print(f"wrote {len(result['cases'])} golden cases to {GOLDEN_DIR}")
