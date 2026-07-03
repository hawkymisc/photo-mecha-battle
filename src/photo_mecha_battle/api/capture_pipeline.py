from __future__ import annotations

import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image

from photo_mecha_battle.api.database import Database
from photo_mecha_battle.api.image_storage import ImageStorage
from photo_mecha_battle.mech_stats import compute_info_score
from photo_mecha_battle.vision.analysis import (
    assess_capture_safety,
    extract_features,
    evaluate_quality,
    hamming_distance,
    perceptual_hash,
)
from photo_mecha_battle.vision.detection import detect_candidates
from photo_mecha_battle.vision.segmentation import image_to_png_bytes, segment_bbox

DUPLICATE_HASH_DISTANCE = 8


@dataclass(frozen=True)
class PipelineObject:
    id: str
    capture_id: str
    features: object
    info_score: float
    quality: dict[str, float]
    detected_label: str
    crop_url: str | None = None


def load_capture_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def create_capture_from_bytes(
    db: Database,
    storage: ImageStorage,
    user_id: str,
    content: bytes,
    suffix: str = ".jpg",
) -> dict[str, object]:
    image = Image.open(BytesIO(content)).convert("RGB")
    phash = perceptual_hash(image)
    for existing in db.list_capture_hashes(user_id):
        if hamming_distance(phash, existing) <= DUPLICATE_HASH_DISTANCE:
            raise ValueError("duplicate_capture")

    safety_status, safety_reason = assess_capture_safety(image, phash)
    if safety_status == "blocked":
        raise ValueError(f"unsafe_capture:{safety_reason}")

    capture_id = str(uuid.uuid4())
    saved_path = storage.save_capture(user_id, content, suffix)
    db.save_capture(
        capture_id=capture_id,
        user_id=user_id,
        original_path=str(saved_path),
        perceptual_hash=phash,
        safety_status=safety_status,
        quality_json={"safety_reason": safety_reason} if safety_reason else {},
    )
    db.increment_quota(user_id, "captures_used")
    return {
        "id": capture_id,
        "has_image": True,
        "perceptual_hash": phash,
        "safety_status": safety_status,
        "safety_reason": safety_reason,
        "original_url": storage.public_url(saved_path),
    }


def detect_for_capture(db: Database, capture_id: str) -> list[dict[str, object]]:
    row = db.get_capture(capture_id)
    if row is None:
        raise KeyError("capture not found")
    image = load_capture_image(Path(row["original_path"]))
    return [
        {
            "candidate_id": candidate.candidate_id,
            "label": candidate.label,
            "bbox": candidate.bbox,
            "confidence": candidate.confidence,
        }
        for candidate in detect_candidates(image)
    ]


def segment_for_capture(
    db: Database,
    storage: ImageStorage,
    capture_id: str,
    bbox: list[float],
    label: str = "object",
) -> PipelineObject:
    row = db.get_capture(capture_id)
    if row is None:
        raise KeyError("capture not found")
    image = load_capture_image(Path(row["original_path"]))
    segmentation = segment_bbox(image, bbox)
    features = extract_features(segmentation.crop, segmentation.mask, segmentation.background_mix)
    quality = evaluate_quality(
        segmentation.crop,
        segmentation.mask,
        segmentation.mask_confidence,
        segmentation.background_mix,
    )
    object_id = str(uuid.uuid4())
    crop_path = storage.save_crop(object_id, image_to_png_bytes(segmentation.crop))
    mask_path = storage.save_mask(object_id, image_to_png_bytes(segmentation.mask))
    info_score = compute_info_score(features)
    db.save_extracted_object(
        object_id=object_id,
        capture_id=capture_id,
        bbox_json=bbox,
        mask_path=str(mask_path),
        crop_path=str(crop_path),
        features_json=features.__dict__,
        info_score=info_score,
        detected_label=label,
        confidence=segmentation.mask_confidence,
        quality_json=quality.as_dict(),
        safety_status="ok",
    )
    return PipelineObject(
        id=object_id,
        capture_id=capture_id,
        features=features,
        info_score=info_score,
        quality=quality.as_dict(),
        detected_label=label,
        crop_url=storage.public_url(crop_path),
    )
