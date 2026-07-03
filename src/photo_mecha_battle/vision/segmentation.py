from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageChops


@dataclass(frozen=True)
class SegmentationResult:
    crop: Image.Image
    mask: Image.Image
    mask_confidence: float
    background_mix: float


def _normalize_bbox(bbox: list[float]) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = bbox
    return max(0.0, x1), max(0.0, y1), min(1.0, x2), min(1.0, y2)


def segment_bbox(image: Image.Image, bbox: list[float]) -> SegmentationResult:
    width, height = image.size
    x1, y1, x2, y2 = _normalize_bbox(bbox)
    left, top, right, bottom = (
        int(x1 * width),
        int(y1 * height),
        int(x2 * width),
        int(y2 * height),
    )
    crop = image.crop((left, top, right, bottom)).convert("RGBA")
    corner = crop.getpixel((0, 0))[:3]
    mask_pixels = []
    foreground = 0
    for r, g, b, _a in crop.getdata():
        distance = abs(r - corner[0]) + abs(g - corner[1]) + abs(b - corner[2])
        if distance > 55:
            mask_pixels.append(255)
            foreground += 1
        else:
            mask_pixels.append(0)
    mask = Image.new("L", crop.size)
    mask.putdata(mask_pixels)
    masked = crop.copy()
    masked.putalpha(mask)
    background_mix = 1.0 - (foreground / max(1, crop.width * crop.height))
    confidence = min(0.98, 0.5 + foreground / max(1, crop.width * crop.height))
    return SegmentationResult(
        crop=masked,
        mask=mask,
        mask_confidence=confidence,
        background_mix=max(0.0, min(1.0, background_mix)),
    )


def image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
