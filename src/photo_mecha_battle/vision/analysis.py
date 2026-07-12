from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageFilter, ImageStat

from photo_mecha_battle.features import FeatureVector


@dataclass(frozen=True)
class QualityScores:
    mask_confidence: float
    target_size: float
    blur: float
    brightness: float
    background_mix: float
    safety: float

    def as_dict(self) -> dict[str, float]:
        return {
            "mask_confidence": self.mask_confidence,
            "target_size": self.target_size,
            "blur": self.blur,
            "brightness": self.brightness,
            "background_mix": self.background_mix,
            "safety": self.safety,
        }


def perceptual_hash(image: Image.Image, size: int = 8) -> str:
    gray = image.convert("L").resize((size, size))
    pixels = list(gray.getdata())
    average = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= average else "0" for pixel in pixels)
    return f"{int(bits, 2):016x}"


def hamming_distance(left: str, right: str) -> int:
    value = int(left, 16) ^ int(right, 16)
    return value.bit_count()


def estimate_blur(image: Image.Image) -> float:
    edges = image.convert("L").filter(ImageFilter.FIND_EDGES)
    variance = ImageStat.Stat(edges).var[0]
    return max(0.0, min(1.0, variance / 2000.0))


def estimate_brightness(image: Image.Image) -> float:
    mean = ImageStat.Stat(image.convert("L")).mean[0] / 255.0
    if mean < 0.2:
        return mean / 0.2 * 0.5
    if mean > 0.85:
        return max(0.0, 1.0 - (mean - 0.85) / 0.15)
    return 1.0


def _entropy_from_histogram(image: Image.Image) -> float:
    histogram = image.convert("L").histogram()
    total = sum(histogram)
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in histogram:
        if count == 0:
            continue
        probability = count / total
        entropy -= probability * math.log2(probability)
    return min(1.0, entropy / 8.0)


def _edge_density(image: Image.Image) -> float:
    edges = image.convert("L").filter(ImageFilter.FIND_EDGES)
    edge_pixels = sum(1 for value in edges.getdata() if value > 40)
    return min(1.0, edge_pixels / max(1, image.width * image.height) * 8.0)


def _color_diversity(image: Image.Image) -> float:
    sample = image.convert("RGB").resize((64, 64))
    colors = {sample.getpixel((x, y)) for x in range(sample.width) for y in range(sample.height)}
    return min(1.0, len(colors) / 256.0)


def _shape_metrics(mask: Image.Image) -> tuple[float, float, float, float, float]:
    alpha = mask.split()[-1]
    bbox = alpha.getbbox() or (0, 0, alpha.width, alpha.height)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    area_ratio = (width * height) / max(1, alpha.width * alpha.height)
    elongation = min(1.0, max(width, height) / max(1, min(width, height)) / 3.0)
    roundness = 1.0 - elongation * 0.5
    symmetry = 1.0 - abs(width - height) / max(1, width + height)
    size_balance = 1.0 - abs(area_ratio - 0.35) / 0.35
    return area_ratio, elongation, roundness, symmetry, max(0.0, min(1.0, size_balance))


# docs/09 クライアント厚め経路: crop は「アルファチャンネル = 確定マスク」の RGBA を正とする。
# クライアント（iOS/Android）の features/1.0 移植はこの導出と同一でなければならない。
MASK_FOREGROUND_THRESHOLD = 128


@dataclass(frozen=True)
class CropAnalysis:
    features: FeatureVector
    mask: Image.Image
    background_mix: float
    foreground_ratio: float


def analyze_rgba_crop(crop: Image.Image) -> CropAnalysis:
    """RGBA crop 単体から特徴量を導出する（docs/09 主経路のサーバー再計算・共有正本）。"""
    rgba = crop if crop.mode == "RGBA" else crop.convert("RGBA")
    mask = rgba.getchannel("A")
    foreground = sum(1 for value in mask.getdata() if value >= MASK_FOREGROUND_THRESHOLD)
    total = max(1, rgba.width * rgba.height)
    foreground_ratio = foreground / total
    background_mix = max(0.0, min(1.0, 1.0 - foreground_ratio))
    features = extract_features(rgba, mask, background_mix)
    return CropAnalysis(
        features=features,
        mask=mask,
        background_mix=background_mix,
        foreground_ratio=foreground_ratio,
    )


def extract_features(crop: Image.Image, mask: Image.Image, background_mix: float) -> FeatureVector:
    rgb = crop.convert("RGB")
    area_ratio, elongation, roundness, symmetry, size_balance = _shape_metrics(mask)
    capture_quality = min(estimate_brightness(rgb), estimate_blur(rgb))
    return FeatureVector(
        visual_entropy=_entropy_from_histogram(rgb),
        edge_complexity=_edge_density(rgb),
        color_diversity=_color_diversity(rgb),
        shape_complexity=min(1.0, (elongation + (1.0 - roundness)) / 2.0),
        semantic_rarity=min(1.0, _color_diversity(rgb) * 0.7 + _edge_density(rgb) * 0.3),
        capture_quality=capture_quality,
        size_balance=size_balance,
        area=area_ratio,
        elongation=elongation,
        roundness=roundness,
        symmetry=symmetry,
    )


def evaluate_quality(
    image: Image.Image,
    mask: Image.Image,
    mask_confidence: float,
    background_mix: float,
) -> QualityScores:
    area_ratio, _, _, _, size_balance = _shape_metrics(mask)
    return QualityScores(
        mask_confidence=mask_confidence,
        target_size=size_balance,
        blur=estimate_blur(image),
        brightness=estimate_brightness(image),
        background_mix=background_mix,
        safety=1.0,
    )


_FACE_SAMPLE_SIZE = 64
_FACE_SKIN_RATIO_MIN = 0.15
_FACE_TEXTURE_RATIO_MIN = 0.04
_FACE_TEXTURE_RATIO_MAX = 0.45
_FACE_ASPECT_MIN = 0.6
_FACE_ASPECT_MAX = 2.2


def _is_skin_tone(r: int, g: int, b: int) -> bool:
    """Classic RGB skin-tone heuristic (Peer et al.), tightened to avoid flagging
    saturated solid-color fills (e.g. a plain red/orange prop) as skin."""
    if not (r > 95 and g > 40 and b > 20):
        return False
    if max(r, g, b) - min(r, g, b) <= 15:
        return False
    if not (r > g >= b + 10):
        return False
    if not (0.55 <= g / r <= 0.9):
        return False
    if not (0.2 <= b / r <= 0.8):
        return False
    return True


def detect_face_like_region(image: Image.Image) -> bool:
    """Lightweight, dependency-free proxy for face presence.

    This is not a real face detector: it flags images that combine a sizeable,
    roughly portrait-shaped skin-tone region with the kind of local texture
    (eyes/mouth/hair edges) a real face produces, as opposed to a flat
    skin-colored object. Used as the docs/02 顔・個人情報 safety gate.
    """
    sample = image.convert("RGB").resize((_FACE_SAMPLE_SIZE, _FACE_SAMPLE_SIZE))
    pixels = list(sample.getdata())
    skin_flags = [_is_skin_tone(r, g, b) for r, g, b in pixels]
    skin_pixel_count = sum(skin_flags)
    if skin_pixel_count / len(skin_flags) < _FACE_SKIN_RATIO_MIN:
        return False

    skin_mask = Image.new("L", sample.size)
    skin_mask.putdata([255 if flag else 0 for flag in skin_flags])
    bbox = skin_mask.getbbox()
    if bbox is None:
        return False
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    if width == 0 or height == 0:
        return False
    aspect = height / width
    if not (_FACE_ASPECT_MIN <= aspect <= _FACE_ASPECT_MAX):
        return False

    edge_pixels = list(sample.convert("L").filter(ImageFilter.FIND_EDGES).getdata())
    textured_skin_pixels = sum(
        1 for is_skin, edge_value in zip(skin_flags, edge_pixels) if is_skin and edge_value > 25
    )
    texture_ratio = textured_skin_pixels / skin_pixel_count
    return _FACE_TEXTURE_RATIO_MIN <= texture_ratio <= _FACE_TEXTURE_RATIO_MAX


_NOISE_ENTROPY_MIN = 0.85
_NOISE_EDGE_DENSITY_MIN = 0.85

_QR_SAMPLE_SIZE = 32
_QR_BLACK_RATIO_MIN = 0.35
_QR_BLACK_RATIO_MAX = 0.65
_QR_TRANSITION_RATIO_MIN = 0.15
_QR_COLOR_DIVERSITY_MAX = 0.3


def detect_noise_image(image: Image.Image) -> bool:
    """docs/02 不正・悪用対策: ノイズ画像 → 自然画像判定、ノイズペナルティ.

    Random static has near-maximal brightness entropy *and* near-maximal edge
    density simultaneously; ordinary photos (even high-entropy ones, e.g.
    smooth gradients) do not combine both.
    """
    rgb = image.convert("RGB")
    return _entropy_from_histogram(rgb) > _NOISE_ENTROPY_MIN and _edge_density(rgb) > _NOISE_EDGE_DENSITY_MIN


def detect_qr_like_pattern(image: Image.Image) -> bool:
    """docs/02 不正・悪用対策: QRコード → パターン検出、スコア制限.

    QR/barcode-style images are near-monochrome, roughly half black/white,
    and made of many small alternating cells, which produces a much higher
    black/white transition density than an ordinary photo.
    """
    gray = image.convert("L").resize((_QR_SAMPLE_SIZE, _QR_SAMPLE_SIZE))
    pixels = list(gray.getdata())
    mean = sum(pixels) / len(pixels)
    binary = [1 if pixel > mean else 0 for pixel in pixels]
    black_ratio = sum(binary) / len(binary)
    if not (_QR_BLACK_RATIO_MIN <= black_ratio <= _QR_BLACK_RATIO_MAX):
        return False

    size = _QR_SAMPLE_SIZE
    transitions = 0
    for y in range(size):
        for x in range(size - 1):
            if binary[y * size + x] != binary[y * size + x + 1]:
                transitions += 1
    for x in range(size):
        for y in range(size - 1):
            if binary[y * size + x] != binary[(y + 1) * size + x]:
                transitions += 1
    transition_ratio = transitions / (size * (size - 1) * 2)
    if transition_ratio < _QR_TRANSITION_RATIO_MIN:
        return False

    return _color_diversity(image) < _QR_COLOR_DIVERSITY_MAX


def assess_capture_safety(image: Image.Image, perceptual_hash_value: str) -> tuple[str, str | None]:
    if detect_face_like_region(image):
        return "blocked", "face_detected"
    if detect_qr_like_pattern(image):
        return "warning", "qr_code_detected"
    if detect_noise_image(image):
        return "warning", "noise_image_detected"
    brightness = estimate_brightness(image)
    blur = estimate_blur(image)
    if brightness < 0.2:
        return "warning", "image_too_dark"
    if blur < 0.05:
        return "warning", "image_too_blurry"
    return "ok", None
