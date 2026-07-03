from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageStat


@dataclass(frozen=True)
class DetectionCandidate:
    candidate_id: str
    label: str
    bbox: list[float]
    confidence: float


def detect_candidates(image: Image.Image, max_candidates: int = 3) -> list[DetectionCandidate]:
    width, height = image.size
    gray = image.convert("L")
    scored_regions: list[tuple[float, tuple[int, int, int, int]]] = []

    grid = 3
    cell_w = width // grid
    cell_h = height // grid
    for row in range(grid):
        for col in range(grid):
            left = col * cell_w
            top = row * cell_h
            right = width if col == grid - 1 else (col + 1) * cell_w
            bottom = height if row == grid - 1 else (row + 1) * cell_h
            region = gray.crop((left, top, right, bottom))
            score = ImageStat.Stat(region).stddev[0]
            center_bias = 1.0 - (abs(col - 1) + abs(row - 1)) * 0.1
            scored_regions.append((score * center_bias, (left, top, right, bottom)))

    scored_regions.sort(reverse=True, key=lambda item: item[0])
    candidates: list[DetectionCandidate] = []
    for index, (score, box) in enumerate(scored_regions[:max_candidates]):
        left, top, right, bottom = box
        bbox = [left / width, top / height, right / width, bottom / height]
        candidates.append(
            DetectionCandidate(
                candidate_id=f"cand-{index}",
                label="object",
                bbox=bbox,
                confidence=min(0.99, 0.55 + score / 100.0),
            )
        )
    return candidates
