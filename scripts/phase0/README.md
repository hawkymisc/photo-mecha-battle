# Phase 0a — SD 1.5 + bird-form mecha LoRA

Phase 0 の第一候補モデル（[`docs/10`](../../docs/10_mobile_image_generation_survey.md)）向けに、
kohya_ss で鳥型メカ LoRA を試作するためのデータセット準備と学習ラッパー。

## 前提

| 項目 | 内容 |
|---|---|
| ベースモデル | `runwayml/stable-diffusion-v1-5` |
| トリガーワード | `pmbbirdmech` |
| Phase 0 規模 | 50 枚（合成プレースホルダー or PO 提供画像） |
| 学習ツール | [kohya_ss / sd-scripts](https://github.com/kohya-ss/sd-scripts)（CI では実行しない） |
| 推論 | img2img（init = 撮影クロップ、`denoise_strength` 0.65–0.80） |

合成データセットは**パイプライン検証用**であり、本番品質のゴールデンにはしない。
PO / アーティスト提供のターゲット画像がある場合は `--ingest` を使う。

## クイックスタート

```bash
# 1) 合成 50 ペアで kohya 形式データセットを生成
python scripts/phase0/prepare_bird_lora_dataset.py

# 2) データセット検証 + 学習コマンド JSON 出力
bash scripts/diag/diag_mecha_lora_phase0a.sh 50

# 3) GPU ホストで学習（kohya_ss を別途 clone）
export KOHYA_SS_DIR=/path/to/sd-scripts
python scripts/phase0/train_bird_lora.py --run
```

## ディレクトリ構成（生成後）

```text
data/phase0/mecha_bird_lora/
  manifest.json          # seed・パス・キャプション一覧
  sources/               # img2img 評価用クロップ（合成時のみ）
    bird_000_crop.png
  train/
    10_pmbbirdmech/      # kohya subset（repeats_trigger）
      bird_000.png
      bird_000.txt
```

学習成果物（ローカル）:

```text
artifacts/phase0/mecha_bird_lora/
  pmb_bird_mecha_lora.safetensors
```

## PO 提供画像の取り込み

ターゲットメカ画像のみを渡す場合（クロップは別途 `sources/` に手動配置）:

```bash
python scripts/phase0/prepare_bird_lora_dataset.py \
  --ingest /path/to/po_bird_mecha_targets \
  --output data/phase0/mecha_bird_lora_po
```

## 設定

[`config/phase0/mecha_bird_lora.toml`](../../config/phase0/mecha_bird_lora.toml)

- LoRA: `network_dim=16`, `network_alpha=16`
- 解像度: 512
- エポック: 12（過学習時は `max_train_epochs` を下げる）

## 品質チェック（PO レビュー）

[`docs/03`](../../docs/03_mech_generation_and_stats.md) に従い、学習後に img2img で以下を確認する。

1. 元クロップのシルエット・色が残るか
2. 鳥型メカとして識別できるか
3. 既存 IP / 実在兵器に寄りすぎていないか

`sources/` から 10 枚を選び、同一 seed で再生成して比較する。

## 関連

- Phase 0d ベースライン: `scripts/diag/diag_mech_i2i.sh`
- 調査正本: [`docs/10`](../../docs/10_mobile_image_generation_survey.md)
