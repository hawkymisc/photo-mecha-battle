from io import BytesIO

from PIL import Image, ImageDraw

from photo_mecha_battle.vision.analysis import (
    assess_capture_safety,
    detect_face_like_region,
    extract_features,
    hamming_distance,
    perceptual_hash,
)
from photo_mecha_battle.vision.detection import detect_candidates
from photo_mecha_battle.vision.segmentation import segment_bbox


def _synthetic_image() -> Image.Image:
    image = Image.new("RGB", (240, 240), (235, 235, 235))
    draw = ImageDraw.Draw(image)
    draw.rectangle((70, 70, 170, 170), fill=(210, 60, 60))
    return image


def test_perceptual_hash_is_stable():
    image = _synthetic_image()
    assert perceptual_hash(image) == perceptual_hash(image)


def test_hamming_distance_for_identical_hashes():
    image = _synthetic_image()
    value = perceptual_hash(image)
    assert hamming_distance(value, value) == 0


def test_detect_candidates_returns_regions():
    candidates = detect_candidates(_synthetic_image())
    assert len(candidates) >= 1
    assert all(len(candidate.bbox) == 4 for candidate in candidates)


def test_segment_bbox_produces_features():
    image = _synthetic_image()
    segmentation = segment_bbox(image, [0.2, 0.2, 0.8, 0.8])
    features = extract_features(segmentation.crop, segmentation.mask, segmentation.background_mix)
    assert 0.0 <= features.visual_entropy <= 1.0
    assert features.capture_quality > 0.0


def test_assess_capture_safety_ok_for_normal_image():
    status, reason = assess_capture_safety(_synthetic_image(), "abc")
    assert status == "ok"
    assert reason is None


def _face_like_image() -> Image.Image:
    image = Image.new("RGB", (240, 240), (235, 235, 235))
    draw = ImageDraw.Draw(image)
    draw.ellipse((50, 40, 190, 220), fill=(222, 184, 135))
    draw.ellipse((85, 100, 105, 120), fill=(40, 30, 25))
    draw.ellipse((135, 100, 155, 120), fill=(40, 30, 25))
    draw.arc((90, 150, 150, 190), start=20, end=160, fill=(90, 50, 40), width=4)
    return image


def test_detect_face_like_region_flags_portrait_texture():
    assert detect_face_like_region(_face_like_image()) is True


def test_detect_face_like_region_ignores_flat_skin_colored_object():
    image = Image.new("RGB", (240, 240), (235, 235, 235))
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 60, 180, 180), fill=(222, 184, 135))
    assert detect_face_like_region(image) is False


def test_detect_face_like_region_ignores_saturated_solid_color():
    assert detect_face_like_region(_synthetic_image()) is False


def test_assess_capture_safety_blocks_face_like_images():
    status, reason = assess_capture_safety(_face_like_image(), "abc")
    assert status == "blocked"
    assert reason == "face_detected"
