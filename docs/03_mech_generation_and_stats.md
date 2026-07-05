# 03. メカ生成・型・ステータス仕様

[← 仕様書一覧](00_root_overview.md)

## 目的

本ドキュメントは、抽出オブジェクトからのメカ生成、メカ型、情報量スコア、ステータス決定に関する仕様を定義する。

> **確定状態（2026-07-02 更新）**: 特徴量ベクトルの定義、情報量スコアの重み、ステータス算出式は
> [`src/photo_mecha_battle/features.py`](../src/photo_mecha_battle/features.py) / `mech_stats.py` の実装値を正として確定した。
> レアリティ・スキル・属性等の未実装概念は「将来拡張」節に隔離した。
>
> **型推定（2026-07-05 確定）**: メカ型はプレイヤー選択ではなく、特徴量から**決定的に推定**する（下記「型推定ルール」）。
> 設計意図はバーコードバトラー／モンスターファーム型の「与件 → 戦略」構造（[`docs/01`](01_game_concept_and_loop.md) 参照）。

## メカ生成の入力

- 抽出オブジェクト画像（crop）
- セグメンテーションマスク
- 特徴量ベクトル（下記 11 次元）

メカ型（`form`）は上記特徴量からサーバー側で推定し、クライアント入力として受け付けない（[`docs/09`](09_lightweight_server_architecture.md) 参照）。

元画像・輪郭画像・エッジ画像は特徴量算出の中間物であり、メカ生成 API の直接入力ではない（[`docs/09`](09_lightweight_server_architecture.md) の主経路参照）。

## メカ型

メカは以下の 3 型とする。**被写体の特徴量から自動推定**され、プレイヤーは結果を受け取る（選択しない）。

設計意図はバーコードバトラー／モンスターファーム型の「与件 → 戦略」構造である。型は発見フェーズの制約であり、戦術・編成フェーズでプレイヤーが工夫する。

| 型 | ID | 役割 |
|---|---|---|
| 鳥形 | `bird` | 高速、回避、先制 |
| 人型 | `human` | バランス、武装切替、戦術適性 |
| 獣型 | `beast` | 装甲、近接、耐久 |

## 鳥形メカ

| 項目 | 内容 |
|---|---|
| 得意 | 回避、先制、空中攻撃 |
| 苦手 | 高装甲、長期戦 |
| 向く素材 | 細長い物、軽そうな物、枝、葉、傘、工具 |
| ステータス傾向 | SPD 高、EVA 高、HP 低め |

## 人型メカ

| 項目 | 内容 |
|---|---|
| 得意 | 汎用性、スキル連携、命中 |
| 苦手 | 極端な特化型との相性差 |
| 向く素材 | 道具、家電、文房具、機械部品、人工物 |
| ステータス傾向 | 平均的、TEC 高め |

## 獣型メカ

| 項目 | 内容 |
|---|---|
| 得意 | HP、DEF、近接火力 |
| 苦手 | 高速回避、空中戦、妨害 |
| 向く素材 | 靴、バッグ、石、ぬいぐるみ、動物、塊感のある物 |
| ステータス傾向 | HP 高、DEF 高、SPD 低め |

## 型推定ルール（`form_inference/1.0`）

### 目的

- 同一 `FeatureVector` に対し、常に同一の `form` を返す（決定的）。
- 推定は**型の基礎ステータスを決める**のみ。個体差（加算ステータス）は既存の特徴量→ステータス式が担当する。
- クライアント・サーバーで同一関数を共有し、サーバーが最終確定する（[`docs/09`](09_lightweight_server_architecture.md) 信頼モデル）。

### 入力・出力

| 項目 | 内容 |
|---|---|
| 入力 | `FeatureVector`（11 次元、各 0.0〜1.0） |
| 出力 | `bird` / `human` / `beast` のいずれか |
| バージョン | `form_inference/1.0`（特徴量の `algo_version` とは独立） |

### 設計方針（向く素材との対応）

| 型 | 推定に効かせる形状・質感の proxy |
|---|---|
| 鳥形 | 細長さ（`elongation`）が高い、塊感（`roundness`）が低い |
| 獣型 | 丸さ・塊感（`roundness`）と面積比（`area`）が高い |
| 人型 | 左右対称（`symmetry`）とエッジ密度（`edge_complexity`）が高く、極端な細長さ・塊感に偏らない |

> MVP では被写体カテゴリ認識は未導入のため、人型の「道具・人工物」は **対称性＋ディテール** で近似する。
> カテゴリ認識導入時は `form_inference/2.0` で人型スコアにカテゴリ項を加える（本節の意味定義は維持）。

### スコア算出

各スコアは 0.0〜1.0 の加重和とする。

```text
bird_score =
  0.50 × elongation
+ 0.30 × (1 − roundness)
+ 0.20 × (1 − |area − 0.35|)    # 画面内サイズが中程度（軽快さの proxy）

beast_score =
  0.45 × roundness
+ 0.35 × area
+ 0.20 × (1 − elongation)

human_score =
  0.35 × symmetry
+ 0.30 × edge_complexity
+ 0.20 × (1 − |elongation − roundness|)   # 細長さと丸さが拮抗＝バランス型シルエット
+ 0.15 × shape_complexity
```

### 型の決定

```text
form = argmax(bird_score, beast_score, human_score)
```

**同点タイブレーク**（最大スコアが複数、差が `1e-9` 未満）:

1. `human`
2. `bird`
3. `beast`

決定性確保のための機械的順序であり、ゲームデザイン上の優先意味は持たせない（[`docs/05`](05_team_and_battle.md) の行動順タイブレークと同趣旨）。

### 代表例（PoC デモ用プリセット特徴量）

| 被写体 | elongation | roundness | area | symmetry | edge_complexity | 推定 form | 主因 |
|---|---:|---:|---:|---:|---:|---|---|
| 傘（umbrella） | 0.82 | 0.30 | 0.45 | 0.55 | 0.42 | **bird** | 高 elongation |
| 石（stone） | 0.20 | 0.85 | 0.70 | 0.50 | 0.30 | **beast** | 高 roundness + area |
| ペン（想定） | 0.45 | 0.55 | 0.40 | 0.75 | 0.65 | **human** | 高 symmetry + edge_complexity |

### API・UI への影響

| レイヤ | 仕様 |
|---|---|
| `POST /mechs` | リクエストに `form` を含めない（含まれてもサーバー推定で上書き）。応答に `form` と `form_inference_version` を含める |
| クライアント | 型選択 UI は持たない。分析後に「判明した型」を表示し、見た目プレビューのみ提供 |
| テスト | 代表例（傘・石・ペン想定）＋同点・境界値を `form_inference/1.0` で固定 |

> **既知の実装乖離**: PoC Web（[`web/index.html`](../web/index.html)）と現行 `POST /mechs` は
> クライアントから `form` を受け取る暫定実装のまま。本節が正であり、実装タスクは PLAN D-013 参照。

### 将来拡張（`form_inference/2.0` 以降）

| 追加入力 | 想定用途 |
|---|---|
| 被写体カテゴリ（物体認識） | 人型スコア加算（道具・家電・文房具） |
| `semantic_rarity` の意味刷新 | カテゴリ希少性と分離した rarity 指標 |

## 特徴量ベクトル（FeatureVector・11 次元）

抽出オブジェクトから以下を計算する。**全次元 0.0〜1.0 に正規化**する（範囲外はエラーで拒否）。
クライアント・サーバーで同一アルゴリズム（同一 `algo_version`）を用いる（[`docs/09`](09_lightweight_server_architecture.md) 信頼モデル）。

| 次元 | 内容 |
|---|---|
| `visual_entropy` | 輝度ヒストグラムのエントロピー（情報量） |
| `edge_complexity` | エッジ密度（質感・ディテール） |
| `color_diversity` | 色数の多様性 |
| `shape_complexity` | シルエット複雑度 |
| `semantic_rarity` | 被写体カテゴリの希少性 |
| `capture_quality` | 撮影品質（明るさ・ブレの複合） |
| `size_balance` | 画面内での対象サイズの適切さ |
| `area` | 対象の面積比 |
| `elongation` | 細長さ |
| `roundness` | 丸さ・塊感 |
| `symmetry` | 左右対称性 |

> **MVP 実装の注記**: 現行のサーバー参照実装（[`vision/analysis.py`](../src/photo_mecha_battle/vision/analysis.py)）は PIL ベースのヒューリスティックであり、
> 特に `semantic_rarity` は色多様性とエッジ密度からの近似値である（カテゴリ認識は未導入）。
> 実装を高度化する際は `algo_version` を上げ、本表の意味定義は維持する。

## 情報量スコア

```text
ObjectInfoScore =
  0.25 * visual_entropy
+ 0.20 * edge_complexity
+ 0.15 * color_diversity
+ 0.15 * shape_complexity
+ 0.10 * semantic_rarity
+ 0.10 * capture_quality
+ 0.05 * size_balance
```

情報量スコアは強さの一部として扱い、単純に総合戦闘力へ直結させない
（反映先は EN と LUCK のみ。下記算出式参照）。

## 基本ステータス

| ステータス | 内容 |
|---|---|
| HP | 耐久力 |
| ATK | 攻撃力 |
| DEF | 防御力 |
| SPD | 行動順、回避、先制 |
| TEC | 命中、スキル発動、戦術安定性 |
| EN | 特殊行動リソース（[`docs/05`](05_team_and_battle.md) EN 経済参照） |
| LUCK | クリティカル率補正（[`docs/05`](05_team_and_battle.md): クリティカル率 = LUCK/500） |

## ステータス算出式（確定）

### 型別基礎値

| 型 | HP | ATK | DEF | SPD | TEC | EN | LUCK |
|---|---:|---:|---:|---:|---:|---:|---:|
| 鳥形 | 75 | 58 | 32 | 88 | 72 | 70 | 5 |
| 人型 | 95 | 62 | 48 | 55 | 78 | 85 | 5 |
| 獣型 | 125 | 72 | 68 | 38 | 48 | 75 | 5 |

### 特徴量による加算

`int()` は小数切り捨て。`info_score` は上記情報量スコア。

```text
HP   = base.HP   + int(area × 35)
DEF  = base.DEF  + int(roundness × 22)
SPD  = base.SPD  + int(elongation × 28)
TEC  = base.TEC  + int(symmetry × 18) + int(edge_complexity × 8)
EN   = base.EN   + int(visual_entropy × 25) + int(info_score × 12)
ATK  = base.ATK  + int(edge_complexity × 18)
LUCK = base.LUCK + int(semantic_rarity × 12) + int(info_score × 8)
```

### 品質ペナルティ

撮影品質が低い（`capture_quality < 0.5`）場合、以下を減算する。

```text
penalty = int((0.5 − capture_quality) × 30)
HP  −= penalty
ATK −= penalty ÷ 2（切り捨て）
```

### キャップ

全ステータスを **10〜200** にクランプする（極端入力への上限。[`docs/08`](08_mvp_and_roadmap.md) リスク対策）。

### MVP 確定の特徴量 → ステータス対応（要約）

| 画像特徴 | 反映先 |
|---|---|
| 高エントロピー | EN |
| エッジ密度が高い | ATK、TEC |
| 面積が大きい | HP |
| 細長い形 | SPD |
| 丸い・塊感がある | DEF |
| 左右対称 | TEC |
| 希少カテゴリ | LUCK |
| 情報量スコア | EN、LUCK |
| 撮影品質が低い | HP・ATK 減算 |

## 画像生成方針（見た目）

- 元オブジェクトの色やシルエットをある程度残す
- 鳥形・人型・獣型の識別性を高める
- 既存 IP 風の出力を避ける
- 実在兵器に過度に寄せない
- 過度な暴力表現を避ける

MVP ではクロップ画像への簡易スタイライズ（型別のティントとシルエット合成）とし、
高品質 i2i 生成は将来の非同期ワーカーで行う（[`docs/09`](09_lightweight_server_architecture.md)）。

高品質 i2i 導入時のモデル候補・LoRA 方針・Phase 0 検証計画は
[`docs/10`](10_mobile_image_generation_survey.md) を参照（採用モデルは PO 決定待ち）。

## 重要原則

生成画像は見た目を表す。
戦闘性能は、生成画像ではなく、撮影画像と抽出オブジェクトの分析値から決定する。

## 将来拡張（MVP では実装しない）

初期仕様案にあった以下の概念は、対応システムの導入時に仕様へ昇格させる。

| 概念 | 依存するシステム |
|---|---|
| 色数 → 属性スロット、状態異常耐性 | 属性・状態異常システム |
| 細長い形 → 射程 | 射程・距離システム |
| エッジ密度 → 武装数、クリティカル | 武装スロットシステム |
| 希少カテゴリ → 固有スキル、称号、特殊適性 | スキル・称号システム |
| レアリティ | レアリティシステム（`mechs.rarity` は現行スキーマ未実装） |
| 丸さ → 突進 | 突進行動の追加 |
