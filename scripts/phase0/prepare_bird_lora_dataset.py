#!/usr/bin/env python3
"""Prepare Phase 0a bird-form mecha LoRA dataset for kohya_ss."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from photo_mecha_battle.models import MechForm
from photo_mecha_battle.vision.lora_dataset import (
    PHASE0_BIRD_PAIR_COUNT,
    build_synthetic_bird_dataset,
    ingest_target_images,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/phase0/mecha_bird_lora"),
        help="Dataset output directory",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=PHASE0_BIRD_PAIR_COUNT,
        help="Synthetic pair count (default: 50)",
    )
    parser.add_argument(
        "--seed-start",
        type=int,
        default=1000,
        help="First RNG seed for synthetic crops",
    )
    parser.add_argument(
        "--ingest",
        type=Path,
        default=None,
        help="Directory of PO-provided target mecha images (skips synthetic generation)",
    )
    args = parser.parse_args()

    if args.ingest:
        report = ingest_target_images(args.ingest, args.output, form=MechForm.BIRD)
    else:
        report = build_synthetic_bird_dataset(
            args.output,
            count=args.count,
            seed_start=args.seed_start,
        )

    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["validation"]["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
