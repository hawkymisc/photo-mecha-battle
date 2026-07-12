#!/usr/bin/env bash
# Phase 0a: prepare dataset and print/run kohya_ss LoRA training command.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

COUNT="${1:-50}"
OUTPUT="${PMB_LORA_DATASET_DIR:-data/phase0/mecha_bird_lora}"

echo "=== Phase 0a: bird mecha LoRA ==="
echo "repo:    $ROOT"
echo "commit:  $(git rev-parse HEAD 2>/dev/null || echo unknown)"
echo "count:   $COUNT"
echo "output:  $OUTPUT"
echo

python3 scripts/phase0/prepare_bird_lora_dataset.py --output "$OUTPUT" --count "$COUNT"
python3 scripts/phase0/train_bird_lora.py --config config/phase0/mecha_bird_lora.toml

echo
echo "Train (GPU host): export KOHYA_SS_DIR=/path/to/sd-scripts"
echo "                  python3 scripts/phase0/train_bird_lora.py --run"
echo "Inference eval:   use sources/*_crop.png as img2img init image"
echo "                  see config/phase0/mecha_bird_lora.toml [inference_defaults]"
