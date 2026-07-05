"""Phase 0 diagnostics for reproducible mech art (MVP stylize baseline)."""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

from PIL import Image

from photo_mecha_battle.models import MechForm
from photo_mecha_battle.vision.mech_art import render_mech_art

DEFAULT_CROP_SIZE = 128


def make_deterministic_crop(seed: int, size: int = DEFAULT_CROP_SIZE) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGB", (size, size))
    pixels = img.load()
    for y in range(size):
        for x in range(size):
            pixels[x, y] = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
    return img


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_mvp_stylize_baseline(seed: int, output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    crop = make_deterministic_crop(seed)
    crop_path = output_dir / f"crop_seed{seed}.png"
    crop.save(crop_path)

    artifacts: dict[str, object] = {"crop_sha256": sha256_bytes(crop_path.read_bytes())}
    form_results: dict[str, str] = {}

    for form in MechForm:
        art_bytes = render_mech_art(crop, form)
        art_path = output_dir / f"mech_{form.value}_seed{seed}.png"
        art_path.write_bytes(art_bytes)
        form_results[form.value] = sha256_bytes(art_bytes)

    artifacts["forms"] = form_results
    artifacts["crop_path"] = str(crop_path)
    return artifacts
