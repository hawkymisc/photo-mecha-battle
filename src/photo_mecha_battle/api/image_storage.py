from __future__ import annotations

import uuid
from pathlib import Path


class ImageStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        for sub in ("captures", "masks", "crops", "art"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def save_capture(self, user_id: str, data: bytes, suffix: str) -> Path:
        path = self.root / "captures" / f"{user_id}_{uuid.uuid4().hex}{suffix}"
        path.write_bytes(data)
        return path

    def save_mask(self, object_id: str, data: bytes) -> Path:
        path = self.root / "masks" / f"{object_id}.png"
        path.write_bytes(data)
        return path

    def save_crop(self, object_id: str, data: bytes) -> Path:
        path = self.root / "crops" / f"{object_id}.png"
        path.write_bytes(data)
        return path

    def save_art(self, mech_id: str, data: bytes) -> Path:
        path = self.root / "art" / f"{mech_id}.png"
        path.write_bytes(data)
        return path

    def public_url(self, path: Path, mount_prefix: str = "/media") -> str:
        relative = path.relative_to(self.root).as_posix()
        return f"{mount_prefix}/{relative}"
