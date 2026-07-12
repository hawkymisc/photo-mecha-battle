"""Tests for Phase 0a LoRA dataset preparation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from photo_mecha_battle.models import MechForm
from photo_mecha_battle.vision.lora_dataset import (
    BIRD_TRIGGER_WORD,
    PHASE0_BIRD_PAIR_COUNT,
    build_synthetic_bird_dataset,
    caption_for_form,
    ingest_target_images,
    kohya_subset_dir_name,
    validate_kohya_train_dir,
)


def test_caption_includes_trigger_word() -> None:
    caption = caption_for_form(MechForm.BIRD)
    assert BIRD_TRIGGER_WORD in caption
    assert "bird form" in caption


def test_kohya_subset_dir_name_format() -> None:
    assert kohya_subset_dir_name(10, BIRD_TRIGGER_WORD) == "10_pmbbirdmech"


def test_build_synthetic_bird_dataset_creates_fifty_pairs(tmp_path: Path) -> None:
    report = build_synthetic_bird_dataset(tmp_path, count=PHASE0_BIRD_PAIR_COUNT, seed_start=2000)
    assert report["pair_count"] == PHASE0_BIRD_PAIR_COUNT
    assert report["validation"]["ok"] is True

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["synthetic"] is True
    assert len(manifest["entries"]) == PHASE0_BIRD_PAIR_COUNT

    first_crop = tmp_path / manifest["entries"][0]["crop_path"]
    first_target = tmp_path / manifest["entries"][0]["target_path"]
    assert first_crop.is_file()
    assert first_target.is_file()
    assert first_target.with_suffix(".txt").is_file()


def test_build_synthetic_dataset_is_deterministic(tmp_path: Path) -> None:
    left = build_synthetic_bird_dataset(tmp_path / "a", count=3, seed_start=42)
    right = build_synthetic_bird_dataset(tmp_path / "b", count=3, seed_start=42)
    assert left["validation"]["image_count"] == right["validation"]["image_count"]

    left_manifest = json.loads((tmp_path / "a" / "manifest.json").read_text(encoding="utf-8"))
    right_manifest = json.loads((tmp_path / "b" / "manifest.json").read_text(encoding="utf-8"))
    assert left_manifest["entries"] == right_manifest["entries"]


def test_validate_kohya_train_dir_reports_missing_caption(tmp_path: Path) -> None:
    subset = tmp_path / "10_test"
    subset.mkdir()
    image = subset / "sample.png"
    image.write_bytes(b"not-a-real-png")

    result = validate_kohya_train_dir(subset, min_images=1)
    assert result["ok"] is False
    assert any("missing caption" in err for err in result["errors"])


def test_ingest_target_images(tmp_path: Path) -> None:
    source = tmp_path / "incoming"
    source.mkdir()
    from PIL import Image

    Image.new("RGB", (64, 64), (255, 0, 0)).save(source / "a.png")
    Image.new("RGB", (64, 64), (0, 255, 0)).save(source / "b.png")

    output = tmp_path / "dataset"
    report = ingest_target_images(source, output, form=MechForm.BIRD)
    assert report["pair_count"] == 2
    assert report["validation"]["ok"] is True


def test_build_synthetic_bird_dataset_rejects_zero_count(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="count must be >= 1"):
        build_synthetic_bird_dataset(tmp_path, count=0)
