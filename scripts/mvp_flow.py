#!/usr/bin/env python3
"""End-to-end MVP flow: stub capture or optional image file."""

from __future__ import annotations

import argparse
import json
import sys
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw


def _stub_flow(base_url: str) -> dict:
    client = httpx.Client(base_url=base_url, timeout=30.0)
    user = client.post("/auth/register", json={"name": "MVP CLI"}).json()
    headers = {"X-User-Token": user["token"]}
    capture = client.post("/captures", json={"label": "umbrella"}).json()
    segment = client.post(f"/captures/{capture['id']}/segment", json={"label": "umbrella"}).json()
    mech = client.post(
        "/mechs",
        json={"object_id": segment["id"], "form": "bird", "name": "CLIメカ"},
        headers=headers,
    ).json()
    battle = client.post(
        "/battles",
        json={
            "team_name": "CLI",
            "seed": 7,
            "slots": [
                {"mech_id": mech["id"], "position": "front", "preset": "melee"},
                {"mech_id": mech["id"], "position": "middle", "preset": "bombardment"},
                {"mech_id": mech["id"], "position": "back", "preset": "sniper"},
            ],
        },
    ).json()
    return {"user": user, "mech": mech, "battle": battle}


def _image_flow(base_url: str, image_path: Path) -> dict:
    client = httpx.Client(base_url=base_url, timeout=30.0)
    user = client.post("/auth/register", json={"name": "MVP Photo"}).json()
    headers = {"X-User-Token": user["token"]}
    content = image_path.read_bytes()
    capture = client.post(
        "/captures/upload",
        headers=headers,
        files={"file": (image_path.name, content, "image/jpeg")},
    ).json()
    detect = client.post(f"/captures/{capture['id']}/detect").json()
    bbox = detect["candidates"][0]["bbox"]
    segment = client.post(
        f"/captures/{capture['id']}/segment",
        json={"label": "object", "bbox": bbox},
    ).json()
    mech = client.post(
        "/mechs",
        json={"object_id": segment["id"], "form": "beast", "name": image_path.stem},
        headers=headers,
    ).json()
    return {"user": user, "capture": capture, "segment": segment, "mech": mech}


def _demo_image(path: Path) -> None:
    image = Image.new("RGB", (320, 320), (235, 235, 235))
    draw = ImageDraw.Draw(image)
    draw.rectangle((90, 90, 230, 230), fill=(190, 70, 70))
    image.save(path, format="JPEG")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MVP vertical slice against API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--image", type=Path, help="optional photo for upload pipeline")
    args = parser.parse_args()

    if args.image is None:
        result = _stub_flow(args.base_url)
    else:
        if not args.image.exists():
            _demo_image(args.image)
        result = _image_flow(args.base_url, args.image)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
