#!/usr/bin/env bash
# Phase 0d: mech image generation reproducibility diagnostic.
# Baseline: MVP stylize (render_mech_art). Optional: stable-diffusion.cpp img2img probe.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

SEED="${1:-42}"

echo "=== diag_mech_i2i ==="
echo "repo:   $ROOT"
echo "commit: $(git rev-parse HEAD 2>/dev/null || echo unknown)"
echo "seed:   $SEED"
echo "date:   $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

python3 scripts/diag/diag_mech_i2i.py "$SEED"

echo
echo "Re-run:  bash scripts/diag/diag_mech_i2i.sh $SEED"
echo "Outputs: artifacts/diag_mech_i2i/"
echo "External i2i (optional): export SD_CPP_BIN SD_MODEL SD_INIT_IMAGE SD_PROMPT SD_STRENGTH"
