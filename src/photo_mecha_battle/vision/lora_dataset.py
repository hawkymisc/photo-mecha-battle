"""Phase 0a: SD 1.5 LoRA dataset preparation for bird-form mecha stylization."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from photo_mecha_battle.models import MechForm
from photo_mecha_battle.vision.mech_i2i_diag import make_deterministic_crop

PHASE0_DATASET_VERSION = "phase0/1.0"
BIRD_TRIGGER_WORD = "pmbbirdmech"
DEFAULT_TRAIN_REPEATS = 10
DEFAULT_IMAGE_SIZE = 512
PHASE0_BIRD_PAIR_COUNT = 50

_FORM_TRIGGER_WORDS: dict[MechForm, str] = {
    MechForm.BIRD: BIRD_TRIGGER_WORD,
    MechForm.HUMAN: "pmbhumanmech",
    MechForm.BEAST: "pmbbeastmech",
}


@dataclass(frozen=True)
class LoraDatasetEntry:
    id: str
    seed: int
    crop_path: str
    target_path: str
    caption: str
    form: str


def trigger_word_for_form(form: MechForm) -> str:
    return _FORM_TRIGGER_WORDS[form]


def caption_for_form(form: MechForm, trigger_word: str | None = None) -> str:
    word = trigger_word or trigger_word_for_form(form)
    form_label = {
        MechForm.BIRD: "bird form",
        MechForm.HUMAN: "humanoid form",
        MechForm.BEAST: "beast form",
    }[form]
    return (
        f"mecha robot, {form_label}, {word}, preserving silhouette, "
        "original object colors, non-violent, fictional design"
    )


def kohya_subset_dir_name(repeats: int, trigger_word: str) -> str:
    safe = trigger_word.replace(" ", "_")
    return f"{repeats}_{safe}"


def make_synthetic_bird_mecha_target(seed: int, size: int = DEFAULT_IMAGE_SIZE) -> Image.Image:
    """Procedural placeholder target for pipeline validation (not production art)."""
    rng = random.Random(seed)
    img = Image.new("RGB", (size, size), (24, 28, 36))
    draw = ImageDraw.Draw(img)

    body_color = (
        rng.randint(70, 130),
        rng.randint(120, 190),
        rng.randint(170, 230),
    )
    accent = (
        min(255, body_color[0] + 40),
        min(255, body_color[1] + 30),
        min(255, body_color[2] + 20),
    )

    cx, cy = size // 2, size // 2 + 20
    draw.ellipse((cx - 70, cy - 50, cx + 70, cy + 80), fill=body_color, outline=accent, width=3)
    draw.polygon(
        [
            (cx - 120, cy - 10),
            (cx - 40, cy - 30),
            (cx - 40, cy + 10),
        ],
        fill=accent,
    )
    draw.polygon(
        [
            (cx + 120, cy - 10),
            (cx + 40, cy - 30),
            (cx + 40, cy + 10),
        ],
        fill=accent,
    )
    draw.rounded_rectangle((cx - 35, cy - 95, cx + 35, cy - 35), radius=12, fill=accent)
    draw.rectangle((cx - 22, cy - 78, cx + 22, cy - 58), fill=(40, 220, 255))
    draw.rectangle((cx - 28, cy + 70, cx - 10, cy + 120), fill=body_color, outline=accent, width=2)
    draw.rectangle((cx + 10, cy + 70, cx + 28, cy + 120), fill=body_color, outline=accent, width=2)
    return img


def _resize_crop(crop: Image.Image, size: int) -> Image.Image:
    if crop.size == (size, size):
        return crop
    return crop.resize((size, size), Image.Resampling.LANCZOS)


def build_synthetic_bird_dataset(
    output_dir: Path,
    *,
    count: int = PHASE0_BIRD_PAIR_COUNT,
    seed_start: int = 1000,
    image_size: int = DEFAULT_IMAGE_SIZE,
    train_repeats: int = DEFAULT_TRAIN_REPEATS,
) -> dict[str, object]:
    if count < 1:
        raise ValueError("count must be >= 1")

    sources_dir = output_dir / "sources"
    train_dir = output_dir / "train" / kohya_subset_dir_name(train_repeats, BIRD_TRIGGER_WORD)
    sources_dir.mkdir(parents=True, exist_ok=True)
    train_dir.mkdir(parents=True, exist_ok=True)

    caption = caption_for_form(MechForm.BIRD)
    entries: list[LoraDatasetEntry] = []

    for index in range(count):
        seed = seed_start + index
        sample_id = f"bird_{index:03d}"
        crop = _resize_crop(make_deterministic_crop(seed, size=128), image_size)
        target = make_synthetic_bird_mecha_target(seed, size=image_size)

        crop_path = sources_dir / f"{sample_id}_crop.png"
        target_path = train_dir / f"{sample_id}.png"
        caption_path = train_dir / f"{sample_id}.txt"

        crop.save(crop_path)
        target.save(target_path)
        caption_path.write_text(caption, encoding="utf-8")

        entries.append(
            LoraDatasetEntry(
                id=sample_id,
                seed=seed,
                crop_path=str(crop_path.relative_to(output_dir)),
                target_path=str(target_path.relative_to(output_dir)),
                caption=caption,
                form=MechForm.BIRD.value,
            )
        )

    manifest = write_dataset_manifest(output_dir, entries, synthetic=True)
    validation = validate_kohya_train_dir(train_dir, min_images=count)
    return {
        "output_dir": str(output_dir),
        "pair_count": count,
        "manifest_path": str(manifest["manifest_path"]),
        "validation": validation,
    }


def ingest_target_images(
    source_dir: Path,
    output_dir: Path,
    *,
    form: MechForm = MechForm.BIRD,
    train_repeats: int = DEFAULT_TRAIN_REPEATS,
) -> dict[str, object]:
    images = sorted(
        path
        for path in source_dir.iterdir()
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )
    if not images:
        raise ValueError(f"no images found in {source_dir}")

    trigger = trigger_word_for_form(form)
    train_dir = output_dir / "train" / kohya_subset_dir_name(train_repeats, trigger)
    train_dir.mkdir(parents=True, exist_ok=True)
    caption = caption_for_form(form)

    entries: list[LoraDatasetEntry] = []
    for index, image_path in enumerate(images):
        sample_id = f"{form.value}_{index:03d}"
        target_path = train_dir / f"{sample_id}.png"
        with Image.open(image_path) as image:
            image.convert("RGB").save(target_path)
        (train_dir / f"{sample_id}.txt").write_text(caption, encoding="utf-8")
        entries.append(
            LoraDatasetEntry(
                id=sample_id,
                seed=-1,
                crop_path="",
                target_path=str(target_path.relative_to(output_dir)),
                caption=caption,
                form=form.value,
            )
        )

    manifest = write_dataset_manifest(output_dir, entries, synthetic=False)
    validation = validate_kohya_train_dir(train_dir, min_images=len(images))
    return {
        "output_dir": str(output_dir),
        "pair_count": len(images),
        "manifest_path": str(manifest["manifest_path"]),
        "validation": validation,
    }


def validate_kohya_train_dir(train_subset_dir: Path, *, min_images: int = 1) -> dict[str, object]:
    if not train_subset_dir.is_dir():
        return {"ok": False, "errors": [f"missing directory: {train_subset_dir}"]}

    images = sorted(
        path
        for path in train_subset_dir.iterdir()
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )
    errors: list[str] = []
    if len(images) < min_images:
        errors.append(f"expected >= {min_images} images, found {len(images)}")

    for image_path in images:
        caption_path = image_path.with_suffix(".txt")
        if not caption_path.is_file():
            errors.append(f"missing caption: {caption_path.name}")

    return {
        "ok": not errors,
        "image_count": len(images),
        "subset_dir": str(train_subset_dir),
        "errors": errors,
    }


def write_dataset_manifest(
    output_dir: Path,
    entries: list[LoraDatasetEntry],
    *,
    synthetic: bool,
) -> dict[str, object]:
    manifest_path = output_dir / "manifest.json"
    payload = {
        "dataset_version": PHASE0_DATASET_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "synthetic": synthetic,
        "trigger_word": BIRD_TRIGGER_WORD,
        "form": MechForm.BIRD.value,
        "base_model": "runwayml/stable-diffusion-v1-5",
        "train_repeats": DEFAULT_TRAIN_REPEATS,
        "entries": [asdict(entry) for entry in entries],
    }
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"manifest_path": str(manifest_path), "entry_count": len(entries)}
