from __future__ import annotations

from dataclasses import dataclass

# docs/09 クライアント厚め経路: クライアントは特徴量算出アルゴリズムのバージョンを
# `algo_version` として必ず送信し、サーバー実装とずれた場合に拒否・再計算できるようにする。
FEATURES_ALGO_VERSION = "features/1.0"


@dataclass(frozen=True)
class FeatureVector:
    """Normalized image features in the 0.0–1.0 range (see docs/03)."""

    visual_entropy: float
    edge_complexity: float
    color_diversity: float
    shape_complexity: float
    semantic_rarity: float
    capture_quality: float
    size_balance: float
    area: float
    elongation: float
    roundness: float
    symmetry: float

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")
