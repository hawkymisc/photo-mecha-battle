# 10. モバイル向け軽量画像生成 AI 調査

[← 仕様書一覧](00_root_overview.md)

## 目的

本ドキュメントは、Photo Mecha Battle が将来導入する**高品質 i2i メカ生成**（撮影クロップ → ロボット/メカ化）について、**iOS / Android 両対応・低 RAM・LoRA カスタマイズ**の観点から調査した結果を記録する。

- 正本の位置づけ: **技術調査・Phase 0 検証計画**。採用モデルの最終決定は PO 判断（[`config/po_pending_decisions.json`](../config/po_pending_decisions.json) の `generation_model_choice`）待ち。
- ゲームルール（見た目と戦闘性能の分離、型推定、生成方針）は引き続き [`docs/03`](03_mech_generation_and_stats.md) を正とする。
- 実行場所・段階導入方針は [`docs/09`](09_lightweight_server_architecture.md) に従う。

**調査日**: 2026-07-05

## 調査結論（要約）

現時点（2026 年上半期）では、**「iOS/Android 同一モデル・低 RAM・LoRA 学習・i2i・商用ライセンス」の 5 条件をすべて満たす単一モデルは存在しない**。

| 方針 | 内容 |
|---|---|
| **Phase 0 第一候補** | **SD 1.5 + LoRA + img2img**（両 OS で実績あり、推論 RAM ~1.8–2.3 GB） |
| **PoC（品質上限確認）** | **DreamLite 0.39B**（i2i に最適だが重み NC ライセンス → 商用不可） |
| **MVP（現仕様）** | クロップへの簡易スタイライズ（[`docs/03`](03_mech_generation_and_stats.md)） |
| **β 以降** | 端末 tier A はオンデバイス i2i、他 tier / 低スペック端末は非同期サーバーワーカー（[`docs/09`](09_lightweight_server_architecture.md)） |

## プロジェクト要件との対応

| 要件 | 仕様上の位置づけ | 調査上の含意 |
|---|---|---|
| クロップ → メカ化（シルエット・色を残す） | [`docs/03`](03_mech_generation_and_stats.md) 画像生成方針 | **img2img または instruction edit** が必要 |
| 鳥形・人型・獣型の識別性 | 同上 | LoRA + プロンプト / 型別 LoRA で制御 |
| 戦闘性能は分析値から決定 | 原則 2（[`docs/00`](00_root_overview.md)） | 生成品質は UX のみ。モデル選定は公平性に影響しない |
| オンデバイス優先 | [`docs/09`](09_lightweight_server_architecture.md) | RAM・発熱・端末差が採用の主制約 |
| LoRA でロボット合成 | Phase 0 検証項目（[`docs/08`](08_mvp_and_roadmap.md)） | 学習パイプライン + 推論時 LoRA 適用が必要 |
| 商用ゲーム（RevenueCat） | ハッカソン前提（[`docs/00`](00_root_overview.md)） | **NC（非商用）ライセンスの重みは本番不可** |

## 候補モデル比較

### Tier A: 実用性・LoRA エコシステム重視（Phase 0 推奨）

#### SD 1.5 + LoRA（stable-diffusion.cpp / Local Dream / Core ML）

| 項目 | 内容 |
|---|---|
| パラメータ | ~860M（UNet） |
| 推論 RAM | **~1.8–2.3 GB**（512×512, fp16 + Flash Attention） |
| i2i | ✅ img2img / inpaint |
| LoRA | ✅ 学習・推論とも成熟（kohya_ss、A1111 互換） |
| iOS | Core ML 変換済みモデル（Hugging Face `apple/coreml-*`）、SDAI / Silicon Diffusion |
| Android | [Local Dream](https://github.com/xororz/local-dream)（Snapdragon NPU、CPU ~2GB）、[stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) |
| ライセンス | SD 1.5 本体: CreativeML Open RAIL-M（商用可、利用制限条項あり） |
| 速度目安 | NPU: 5–15 秒/枚、CPU: 数分/枚 |

**参照実装・ツール**

- Android: [Local Dream](https://github.com/xororz/local-dream) — img2img、LoRA、Snapdragon NPU（8 Gen 1 以降）
- クロスプラットフォーム C++: [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) — LoRA、img2img、~1.8 GB（Flash Attention 有効時）
- iOS: [Hugging Face Core ML SD](https://huggingface.co/docs/diffusers/main/optimization/coreml)、[SDAI / Stable-Diffusion-KMP](https://github.com/ShiftHackZ/Stable-Diffusion-KMP)
- Qualcomm 公式エクスポート: [AI Hub Stable Diffusion v1.5](https://aihub.qualcomm.com/models/stable_diffusion_v1_5)

---

### Tier B: 次世代軽量モデル（i2i 向きだが制約あり）

#### DreamLite（0.39B）

| 項目 | 内容 |
|---|---|
| 推論 RAM | 極小（0.39B UNet） |
| i2i | ✅ T2I + instruction edit を単一モデルで統合（In-Context Spatial Concat） |
| LoRA | ✅ 公式 [LoRA Fine-Tuning Guide](https://github.com/ByteVisionLab/DreamLite/tree/main/lora) |
| 速度 | iPhone 17 Pro: 1024² を ~3 秒、Xiaomi 14: <1 秒（論文値） |
| ライセンス | コード Apache 2.0、**重み CC BY-NC 4.0 → 商用不可** |
| 参照 | [GitHub](https://github.com/ByteVisionLab/DreamLite)、[arXiv:2603.28713](https://arxiv.org/abs/2603.28713) |

アーキテクチャ的には「撮影物 → メカ化」に最も合うが、**本番採用には商用許諾または自社蒸留が必要**。

#### Mobile-O（0.5B unified）

| 項目 | 内容 |
|---|---|
| 推論 RAM | **< 2 GB** |
| i2i | ✅ Text + Image → Image（instruction edit） |
| LoRA | 学習コードあり（主に LLM 部分）。DiT 向け LoRA は要追加検証 |
| クロスプラットフォーム | **iOS のみ**（MLX / CoreML） |
| ライセンス | **CC BY-NC-SA 4.0** |
| 参照 | [GitHub](https://github.com/Amshaker/Mobile-O) |

#### Bonsai Image 4B（PrismML）

| 項目 | 内容 |
|---|---|
| 推論 RAM | **1.5–2.4 GB**（512–1024²、アクティブ時） |
| ベース | FLUX.2 Klein 4B（1-bit / ternary 量子化） |
| i2i | ❌ 主に T2I。img2img は未確認 |
| LoRA | 推論は可能、**1-bit モデルへの fine-tune は困難** |
| クロスプラットフォーム | **MLX = Apple のみ** |
| ライセンス | **Apache 2.0**（商用可） |
| 参照 | [Hugging Face 1-bit](https://huggingface.co/prism-ml/bonsai-image-binary-4B-mlx-1bit)、[PrismML 発表](https://prismml.com/news/bonsai-image-4b) |

画質・RAM 効率は優秀だが、クロップ保持型 i2i には向かない。

#### SnapGen++（0.4B DiT）

| 項目 | 内容 |
|---|---|
| 速度 | iPhone 16 Pro Max: 1024² を **1.8 秒** |
| Android | 0.3B Tiny 版を低スペック向けに設計（論文） |
| 公開 | **論文・デモのみ。重み・コード未公開** |
| i2i | T2I のみ |
| 参照 | [Project page](https://snap-research.github.io/snapgenplusplus/)、[arXiv:2601.08303](https://arxiv.org/abs/2601.08303) |

---

### Tier C: 不採用（参考）

#### Apple Image Playground

- iOS 18+ / Apple Intelligence 端末
- 高品質生成は **Private Cloud Compute 依存**（完全オンデバイスではない）
- カスタム LoRA・img2img パラメータ制御不可
- Android 非対応

**→ 本作には不向き**（クロスプラットフォーム・LoRA・i2i 制御の要件を満たさない）。

## 採用判断マトリクス

| 候補 | RAM | i2i | LoRA 学習 | iOS | Android | 商用 | Phase 0 |
|---|---|---|---|---|---|---|---|
| **SD 1.5 + LoRA** | ~2 GB | ✅ | ✅ | ✅ | ✅ | ✅ | **第一候補** |
| DreamLite | 極小 | ✅ | ✅ | ✅ | △ | ❌ NC | PoC 最優先 |
| Local Dream | ~2 GB | ✅ | ✅ | — | ✅ | △ NC（アプリ） | Android 検証 |
| Bonsai Image 4B | 1.5–2.4 GB | ❌ | △ | ✅ | ❌ | ✅ | T2I のみ |
| Mobile-O | <2 GB | ✅ edit | △ | ✅ | ❌ | ❌ NC | iOS PoC |
| SnapGen++ | 小 | ❌ | ❌ | △ | △ | ❌ | 将来監視 |
| Image Playground | — | △ | ❌ | △ | ❌ | △ | 不採用 |

## クロスプラットフォーム構成案

同一モデルファイルで両 OS を走らせる現実解は **SD 1.5 + LoRA** である。次世代モデル（DreamLite 等）は OS ごとに別実装になりやすい。

```text
┌─────────────────────────────────────────────────────────┐
│  共通: サーバー側 LoRA 学習（kohya_ss / diffusers）       │
└───────────────────────────┬─────────────────────────────┘
                            │
          ┌─────────────────┴─────────────────┐
          ▼                                   ▼
┌─────────────────────┐           ┌─────────────────────┐
│  iOS クライアント    │           │  Android クライアント │
│  Core ML SD1.5      │           │  Local Dream /       │
│  + LoRA + img2img   │           │  sd.cpp + LoRA       │
└──────────┬──────────┘           └──────────┬──────────┘
           │                                  │
           └──────────┬───────────────────────┘
                      ▼
              撮影クロップ → メカ art
```

## 端末 tier とフォールバック

| Tier | 端末例 | オンデバイス i2i | 推奨解像度 | フォールバック |
|---|---|---|---|---|
| A | iPhone 15 Pro+、Snapdragon 8 Gen 2+ | SD1.5 LoRA img2img 可能 | 512 → アップスケール | — |
| B | 6 GB RAM 中級機 | 512 のみ、15–60 秒 | 512 プレビュー | tier A 端末相当の待ち時間 UX |
| C | 4 GB 以下・旧端末 | 実質不可 | — | MVP の簡易スタイライズ（[`docs/03`](03_mech_generation_and_stats.md)） |

β 以降は tier A のみオンデバイス i2i、他は非同期サーバーワーカー（[`docs/09`](09_lightweight_server_architecture.md)）を検討する。

## LoRA によるメカ合成（推奨手順）

### ベースモデル

Phase 0 では **SD 1.5**（`runwayml/stable-diffusion-v1-5` または anime / mecha 系 checkpoint）を第一候補とする。

### データセット

| 項目 | 内容 |
|---|---|
| 入力 | ゲーム内想定の実写クロップ（背景除去済み） |
| 出力 | 鳥形 / 人型 / 獣型メカのターゲット画像 |
| 規模 | Phase 0: 50 ペアで傾向確認 → 本番: 200–500 ペア/型 |

### 学習設定（初期値）

| パラメータ | 値 |
|---|---|
| rank / alpha | 16–32 |
| 解像度 | 512×512 |
| エポック | 10–20（過学習に注意） |
| ツール | kohya_ss または diffusers LoRA |

キャプション例: `mecha robot, bird form, {trigger_word}, preserving silhouette`

### 推論

| パラメータ | 値 |
|---|---|
| モード | img2img |
| denoise strength | **0.65–0.80**（Local Dream 推奨 ~0.8） |
| 型別制御 | 共通 LoRA + プロンプト分岐、または型別 LoRA 3 本 |

### 品質チェック（[`docs/03`](03_mech_generation_and_stats.md) 準拠）

- 元オブジェクトの色・シルエットが残るか
- 鳥形 / 人型 / 獣型の識別性
- 既存 IP 風・実在兵器に寄りすぎないか
- 過度な暴力表現がないか

### DreamLite LoRA（PoC 限定）

[DreamLite lora/](https://github.com/ByteVisionLab/DreamLite/tree/main/lora) で domain-specific fine-tune が可能。i2i がネイティブなため SD 1.5 img2img より「撮影物を残してメカ化」しやすい可能性がある。**重み NC ライセンスのため Phase 0 検証・ゴールデン画像比較に限定**する。

## Phase 0 検証計画

[`docs/08`](08_mvp_and_roadmap.md) の Phase 0「i2i メカ生成の安定性」「端末上での処理性能」に対応する。

| ステップ | 内容 | 成果物 |
|---|---|---|
| **0a** | SD 1.5 + mecha LoRA を kohya_ss で試作（鳥型 50 ペア） | LoRA 重み、サンプル画像 |
| **0b** | Android: Local Dream、iOS: Core ML SD1.5 で img2img ベンチ | RAM / 秒数 / 発熱ログ |
| **0c** | DreamLite で同一データ PoC（NC 限定） | 品質比較レポート |
| **0d** | `scripts/diag/diag_mech_i2i.sh` で seed 固定再現性を記録 | 診断スクリプト出力 |

**受入基準（Phase 0 暫定）**

- 同一 seed + 同一入力で生成結果が再現可能
- tier A 端末で 512² img2img が 60 秒以内（NPU 利用時は 15 秒以内を目標）
- シルエット保持率を PO がサンプル 10 枚で確認可能

## PO 判断待ち項目との関係

以下は調査で**確定していない**。PO 決定後に本書と [`docs/03`](03_mech_generation_and_stats.md) を更新する。

| ID | 質問 | 調査上の示唆 |
|---|---|---|
| `generation_model_choice` | 採用モデル | Phase 0 第一候補: SD 1.5 + LoRA。PoC: DreamLite |
| `generation_resolution` | 解像度 | オンデバイス: 512 生成 → アップスケール。確定時 1024 はサーバー or tier A のみ |
| `generation_cost_per_unit` | 1 体あたりコスト | オンデバイスは端末電力・時間。サーバー i2i は GPU 秒課金 |
| `regeneration_count_policy` | 再生成回数 | オンデバイス生成は [`docs/06`](06_monetization_and_fairness.md) クォータと整合 |

## 関連ドキュメント

| ドキュメント | 関係 |
|---|---|
| [`docs/03`](03_mech_generation_and_stats.md) | 画像生成方針（見た目）、型別識別性 |
| [`docs/08`](08_mvp_and_roadmap.md) | Phase 0 検証項目、未決事項 |
| [`docs/09`](09_lightweight_server_architecture.md) | i2i 段階導入、クライアント厚め方針 |
| [`config/po_pending_decisions.json`](../config/po_pending_decisions.json) | PO 意思決定待ち |

## 変更履歴

| 日付 | 内容 |
|---|---|
| 2026-07-05 | 初版作成（モバイル向け軽量画像生成 AI 調査） |
