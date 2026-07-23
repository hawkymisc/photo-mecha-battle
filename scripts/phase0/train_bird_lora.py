#!/usr/bin/env python3
"""Emit or run kohya_ss LoRA training for Phase 0a bird mecha."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from photo_mecha_battle.vision.lora_dataset import validate_kohya_train_dir


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_config(config_path: Path) -> dict:
    with config_path.open("rb") as handle:
        return tomllib.load(handle)


def find_train_subset(train_data_dir: Path) -> Path:
    subsets = sorted(path for path in train_data_dir.iterdir() if path.is_dir())
    if len(subsets) != 1:
        raise ValueError(f"expected exactly one kohya subset under {train_data_dir}, found {len(subsets)}")
    return subsets[0]


def build_train_command(config_path: Path, kohya_dir: Path) -> list[str]:
    cfg = load_config(config_path)
    model = cfg["model"]
    dataset = cfg["dataset"]
    lora = cfg["lora"]
    training = cfg["training"]

    train_subset = find_train_subset(repo_root() / dataset["train_data_dir"])
    validation = validate_kohya_train_dir(train_subset, min_images=1)
    if not validation["ok"]:
        raise RuntimeError(json.dumps(validation, ensure_ascii=False))

    output_dir = repo_root() / training["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    script = kohya_dir / "train_network.py"
    if not script.is_file():
        raise FileNotFoundError(f"kohya train_network.py not found: {script}")

    return [
        "accelerate",
        "launch",
        "--num_cpu_threads_per_process",
        "1",
        str(script),
        f"--pretrained_model_name_or_path={model['pretrained_model_name_or_path']}",
        f"--train_data_dir={repo_root() / dataset['train_data_dir']}",
        f"--resolution={dataset['resolution']}",
        f"--output_dir={output_dir}",
        f"--output_name={training['output_name']}",
        f"--save_model_as={training['save_model_as']}",
        f"--network_module={lora['network_module']}",
        f"--network_dim={lora['network_dim']}",
        f"--network_alpha={lora['network_alpha']}",
        f"--max_train_epochs={training['max_train_epochs']}",
        f"--train_batch_size={training['train_batch_size']}",
        f"--gradient_accumulation_steps={training['gradient_accumulation_steps']}",
        f"--learning_rate={training['learning_rate']}",
        f"--lr_scheduler={training['lr_scheduler']}",
        f"--lr_warmup_steps={training['lr_warmup_steps']}",
        f"--optimizer_type={training['optimizer_type']}",
        f"--mixed_precision={training['mixed_precision']}",
        f"--seed={training['seed']}",
        f"--max_data_loader_n_workers={training['max_data_loader_n_workers']}",
        f"--save_every_n_epochs={training['save_every_n_epochs']}",
        f"--caption_extension=.txt",
        f"--clip_skip={training['clip_skip']}",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=repo_root() / "config/phase0/mecha_bird_lora.toml",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute training when KOHYA_SS_DIR is set",
    )
    args = parser.parse_args()

    kohya_dir_raw = os.environ.get("KOHYA_SS_DIR", "")
    report: dict[str, object] = {
        "config": str(args.config),
        "kohya_ss_dir": kohya_dir_raw or None,
        "status": "command_only",
    }

    if not kohya_dir_raw:
        report["hint"] = "Export KOHYA_SS_DIR to the sd-scripts repository root, then re-run with --run"
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    command = build_train_command(args.config, Path(kohya_dir_raw))
    report["command"] = command

    if args.run:
        result = subprocess.run(command, check=False, cwd=repo_root())
        report["status"] = "executed"
        report["exit_code"] = result.returncode
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return result.returncode

    report["status"] = "ready"
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
