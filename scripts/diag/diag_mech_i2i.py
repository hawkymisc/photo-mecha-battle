#!/usr/bin/env python3
"""Phase 0 baseline: reproducible MVP mech art (stylize) generation diagnostics."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from photo_mecha_battle.vision.mech_i2i_diag import run_mvp_stylize_baseline

DEFAULT_SEED = 42


def git_commit_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def main() -> int:
    seed = DEFAULT_SEED
    if len(sys.argv) > 1:
        seed = int(sys.argv[1])

    repo_root = Path(__file__).resolve().parents[2]
    output_dir = repo_root / "artifacts" / "diag_mech_i2i"

    baseline = run_mvp_stylize_baseline(seed, output_dir)
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "commit": git_commit_hash(),
        "seed": seed,
        "pipeline": "mvp_stylize (render_mech_art)",
        "algo_version": "mech_art/1.0",
        "output_dir": str(output_dir),
        "baseline": baseline,
        "external_i2i": {
            "status": "not_run",
            "hint": (
                "Set SD_CPP_BIN, SD_MODEL, SD_INIT_IMAGE, SD_PROMPT to probe "
                "stable-diffusion.cpp img2img (Phase 0b)."
            ),
        },
    }

    sd_bin_raw = os.environ.get("SD_CPP_BIN", "")
    sd_bin = Path(sd_bin_raw) if sd_bin_raw else None
    if sd_bin and sd_bin.is_file():
        report["external_i2i"]["status"] = "skipped_missing_env"
        required = ("SD_MODEL", "SD_INIT_IMAGE", "SD_PROMPT")
        missing = [name for name in required if not os.environ.get(name)]
        if not missing:
            strength = os.environ.get("SD_STRENGTH", "0.75")
            report["external_i2i"]["status"] = "manual_required"
            report["external_i2i"]["command_hint"] = (
                f"{sd_bin} --mode img2img -m $SD_MODEL -i $SD_INIT_IMAGE "
                f"-p $SD_PROMPT --strength {strength} -s {seed}"
            )

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
