# 07. プラットフォーム・データモデル仕様

[← 仕様書一覧](00_root_overview.md)

## 目的

本ドキュメントは、iOS/Android 対応方針、認証、データモデル、API 共通規約を定義する。

> **確定状態（2026-07-02 更新）**: システム構成図と API 一覧は [`docs/09_lightweight_server_architecture.md`](09_lightweight_server_architecture.md)
> に一本化した（本書の旧「サーバー集中型 ML パイプライン」構成は廃止）。
> データモデルは現行実装（[`api/database.py`](../src/photo_mecha_battle/api/database.py) の SQLite スキーマ）と同期済み。
> PostgreSQL 等への移行時もカラム構成の意味は本書を正とする。

## 対象プラットフォーム

- iOS
- Android

## スマートフォン向け基本方針

- 片手操作しやすい UI
- 短時間で完結するゲームループ
- 戦術編集は 4 スロット + 基本行動に抑える（[`docs/04`](04_tactics.md)）
- 複雑なノーコードエディタを避ける
- バトルはオートで進行する
- 非同期処理を活用する

## クライアント候補

| 候補 | 特徴 |
|---|---|
| Flutter | UI・カメラ・単一コードベース。オンデバイス推論バインディングも容易 |
| ネイティブ (Swift / Kotlin) | カメラ・Core ML / ML Kit の最適化に強い |
| Unity | バトル演出を厚くする場合に有力 |
| React Native | 一般的なアプリ UI に向く |

軽量サーバー・クライアント厚め構成（[`docs/09`](09_lightweight_server_architecture.md)）では Flutter またはネイティブが第一候補。
バックエンド言語（Python）はサーバー専用であり、アプリ本体を Python にする必要はない。

## システム構成・API

**[`docs/09_lightweight_server_architecture.md`](09_lightweight_server_architecture.md) を正とする。** 本書では重複定義しない。

- 全体構成図・責務分担 → [`docs/09`](09_lightweight_server_architecture.md) 「全体構成」「責務分担」
- API 一覧（主経路・互換用の区別含む）→ [`docs/09`](09_lightweight_server_architecture.md) 「API 設計」
- 信頼モデル（クライアント算出値の検証）→ [`docs/09`](09_lightweight_server_architecture.md) 「信頼モデル」

## 認証（MVP）

| 項目 | 内容 |
|---|---|
| 登録 | `POST /auth/register` で名前のみ登録。サーバーがユーザー ID とトークンを発行 |
| 認証方式 | 発行トークンを `X-User-Token` ヘッダで送信する（ベアラートークン相当の暫定方式） |
| 将来 | ストアアカウント連携・Firebase Auth / Auth0 / Cognito 等への移行を β 版までに判断 |

トークンは再発行・失効の仕組みを持たない暫定実装である。本番公開前に見直す。

## API 共通規約

### エラーレスポンス

FastAPI 標準の `{"detail": "..."}` 形式とする。

| ステータス | 用途 |
|---|---|
| 400 | 入力不正（空ファイル、編成不足など） |
| 401 | `X-User-Token` 欠落・無効 |
| 403 | 他ユーザーのリソースへのアクセス |
| 404 | リソース不存在 |
| 409 | 重複撮影（perceptual hash 判定。[`docs/02`](02_photo_object_extraction.md)） |
| 422 | 検証拒否（`unsafe_capture` / `feature_mismatch` / `unsupported_algo_version`。[`docs/09`](09_lightweight_server_architecture.md)） |
| 429 | 日次クォータ超過（[`docs/06`](06_monetization_and_fairness.md)） |

### 所有権

- 戦術・チームはユーザーに紐づく。他ユーザーのチーム参照・更新・出撃は 403 で拒否する。
- バトル結果・ログは**対戦当事者のみ**参照可能とする（未認証 401・第三者 403。PLAN D-008 対応済み）。
- アップロード写真由来の抽出オブジェクトは**アップロードした本人のみ**メカ生成に使用できる
  （`POST /mechs` で他ユーザーの `object_id` は 403。所有者を持たないデモ経路は対象外。D-013 レビューで追加）。

## データモデル（現行実装と同期）

ストレージは MVP では SQLite（[`api/database.py`](../src/photo_mecha_battle/api/database.py)）。カラムの意味を変えずに PostgreSQL へ移行可能な設計とする。
画像ファイルはローカルディスク（`data/` 配下）に保存し、`/media` で静的配信する。将来は S3/GCS。

### users

| column | 内容 |
|---|---|
| id | UUID |
| name | 表示名 |
| token | 認証トークン（UNIQUE。上記「認証」参照） |
| rating | レーティング（初期 1000、下限 0。更新規則は [`docs/05`](05_team_and_battle.md)） |
| created_at | 作成日時（UTC ISO 8601） |

### captures

| column | 内容 |
|---|---|
| id | UUID |
| user_id | 所有ユーザー |
| original_path | 原画像の保存パス |
| perceptual_hash | 8×8 平均ハッシュ（64bit hex。[`docs/02`](02_photo_object_extraction.md)） |
| safety_status | `ok` / `warning`（[`docs/02`](02_photo_object_extraction.md) 品質評価） |
| quality_json | 警告理由等の付帯情報 |
| created_at | 作成日時 |

### extracted_objects

| column | 内容 |
|---|---|
| id | UUID |
| capture_id | 元 capture |
| bbox_json | 正規化 bbox `[x1, y1, x2, y2]`（0.0〜1.0） |
| mask_path / crop_path | マスク・クロップ画像の保存パス |
| features_json | 特徴量ベクトル 11 次元（[`docs/03`](03_mech_generation_and_stats.md)） |
| info_score | 情報量スコア（サーバー確定値） |
| detected_label | 検出ラベル |
| confidence | マスク信頼度 |
| quality_json | 品質スコア一式（[`docs/02`](02_photo_object_extraction.md)） |
| safety_status | 安全性判定 |

### mechs

| column | 内容 |
|---|---|
| id | UUID |
| user_id | 所有ユーザー |
| object_id | 生成元 extracted_object |
| form | `bird` / `human` / `beast`。特徴量からサーバーが推定（`form_inference/1.0`。[`docs/03`](03_mech_generation_and_stats.md)）。クライアント入力不可 |
| name | 機体名 |
| stats_json | 確定ステータス（HP/ATK/DEF/SPD/TEC/EN/LUCK。算出は [`docs/03`](03_mech_generation_and_stats.md)） |
| art_url | 生成アート URL（見た目のみ。戦闘性能に影響しない） |

※ `rarity` / `skills` は将来拡張（[`docs/03`](03_mech_generation_and_stats.md) 将来拡張参照）。現行スキーマには存在しない。

### tactic_sets

| column | 内容 |
|---|---|
| id | UUID |
| user_id | 所有ユーザー |
| payload_json | `{name, slots[{condition{kind, threshold}, action}], fallback_action}`（[`docs/04`](04_tactics.md)） |

※ `base_preset`（派生元プリセット）・`created_by`（手動/自然言語生成の別）は Phase 3 で追加予定。

### teams

| column | 内容 |
|---|---|
| id | UUID |
| user_id | 所有ユーザー |
| name | チーム名 |
| front_mech_id / front_tactic_id | 前衛の機体・戦術 |
| middle_mech_id / middle_tactic_id | 中衛の機体・戦術 |
| back_mech_id / back_tactic_id | 後衛の機体・戦術 |
| queued | マッチングキュー登録フラグ（[`docs/05`](05_team_and_battle.md) マッチング参照） |

### battles

| column | 内容 |
|---|---|
| id | UUID |
| player_a_id / player_b_id | 対戦者（CPU 戦は b 側 NULL） |
| team_a_id / team_b_id | 使用チーム（CPU 戦は b 側 NULL） |
| seed | バトル seed（再現用） |
| winner_team_id | 勝者チーム（引き分けは NULL） |
| turns | 経過ターン数 |
| log_text | バトルログ |
| created_at | 実施日時 |

※ ログは構造化 JSON 保存へ移行予定（[`docs/05`](05_team_and_battle.md) バトルログ参照。現行は整形テキスト）。

### user_entitlements

| column | 内容 |
|---|---|
| user_id | 対象ユーザー |
| entitlement_key | Entitlement キー（[`docs/06`](06_monetization_and_fairness.md) の定義表） |
| is_active | 有効フラグ |

※ `store` / `product_id` / `latest_purchase_at` / `expiration_at` 等の購入詳細カラムは、
RevenueCat Webhook の本実装時（Phase 3）に追加する。

### daily_quotas

| column | 内容 |
|---|---|
| user_id | 対象ユーザー |
| quota_date | UTC 日付 |
| captures_used | 当日の撮影アップロード消費数 |
| mechs_used | 当日のメカ生成消費数 |

上限値と premium 拡大は [`docs/06`](06_monetization_and_fairness.md) 「生成クォータ」を正とする。

## RevenueCat 連携

役割分担・Entitlement 定義・Webhook 処理は [`docs/06`](06_monetization_and_fairness.md)、API パスは [`docs/09`](09_lightweight_server_architecture.md) を正とする。

- クライアント: SDK 初期化、App User ID とアプリ内ユーザー ID の紐づけ、Offerings 取得、
  Paywall 表示、購入、購入復元、CustomerInfo 取得、Entitlement に応じた機能解放
- バックエンド: Webhook 受信 → `user_entitlements` 同期。クライアントだけで課金状態を確定しない
- ランク戦での戦術条件・行動・スロット数は Entitlement に依存させない
