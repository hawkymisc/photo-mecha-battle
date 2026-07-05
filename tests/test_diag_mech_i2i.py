"""Tests for Phase 0 mech i2i diagnostic baseline."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from photo_mecha_battle.vision.mech_i2i_diag import run_mvp_stylize_baseline


def test_mvp_stylize_baseline_is_reproducible_for_fixed_seed(tmp_path: Path) -> None:
    first = run_mvp_stylize_baseline(42, tmp_path / "run1")
    second = run_mvp_stylize_baseline(42, tmp_path / "run2")
    assert first["crop_sha256"] == second["crop_sha256"]
    assert first["forms"] == second["forms"]


def test_diag_mech_i2i_script_exits_zero() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "diag" / "diag_mech_i2i.py"), "7"],
        check=False,
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["seed"] == 7
    assert payload["pipeline"] == "mvp_stylize (render_mech_art)"
    assert set(payload["baseline"]["forms"]) == {"bird", "human", "beast"}
