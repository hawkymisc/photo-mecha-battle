# 07. プラットフォーム・システム仕様

## 目的

本ドキュメントは、iOS/Android対応、システム構成、API、データモデルに関する仕様を定義する。

## 対象プラットフォーム

- iOS
- Android

## スマートフォン向け基本方針

- 片手操作しやすいUI
- 短時間で完結するゲームループ
- 戦術編集は3〜5スロットに抑える
- 複雑なノーコードエディタを避ける
- バトルはオートで進行する
- 非同期処理を活用する

## クライアント候補

| 候補 | 特徴 |
|---|---|
| Unity | ゲーム演出、クロスプラットフォームに強い |
| Flutter | UI中心のMVPに向く |
| React Native | 一般的なアプリUIに向く |
| ネイティブ | 端末機能最適化に強いが開発工数が増える |

ゲーム演出を重視する場合はUnityが有力。  
UI中心・軽量なMVPを重視する場合はFlutterやネイティブも検討対象。

## 全体構成

```text
iOS / Android Client
  ├─ Camera
  ├─ Object Selection UI
  ├─ Mech Viewer
  ├─ Tactic Editor
  ├─ Team Builder
  └─ Battle Viewer

Backend API
  ├─ Auth
  ├─ Capture API
  ├─ Object Analysis API
  ├─ Mech API
  ├─ Tactic API
  ├─ Battle API
  ├─ Ranking API
  └─ Moderation API

ML Pipeline
  ├─ Object Detection
  ├─ Segmentation
  ├─ Feature Extraction
  ├─ Score Calculation
  ├─ Image-to-Image Generation
  ├─ Safety Filter
  └─ Optional Local LLM / Cloud LLM

Storage
  ├─ Original Images
  ├─ Mask Images
  ├─ Cropped Objects
  ├─ Generated Mech Art
  ├─ Feature Vectors
  ├─ Tactic Sets
  └─ Battle Logs
```

## バックエンド候補

| 領域 | 候補 |
|---|---|
| API | FastAPI / Go / Node.js |
| DB | PostgreSQL |
| 画像保存 | S3 / GCS |
| キュー | Cloud Tasks / Pub/Sub / Celery |
| 推論基盤 | GPUサーバー / Vertex AI / SageMaker / RunPod / Modal |
| 認証 | Firebase Auth / Auth0 / Cognito |
| 分析 | BigQuery / ClickHouse |

## 主要API案

### 画像・メカ生成

| API | 内容 |
|---|---|
| POST /captures | 写真アップロード |
| POST /captures/{id}/detect | オブジェクト候補検出 |
| POST /objects/{id}/segment | セグメンテーション |
| POST /objects/{id}/analyze | 特徴量・情報量計算 |
| POST /mechs | メカ生成 |
| GET /mechs/{id} | メカ詳細取得 |

### 戦術

| API | 内容 |
|---|---|
| GET /tactic-presets | プリセット一覧取得 |
| POST /tactics | 戦術セット作成 |
| PUT /tactics/{id} | 戦術セット更新 |
| POST /tactics/compile | 自然言語から戦術生成 |
| POST /mechs/{id}/tactic | 機体へ戦術インストール |
| POST /tactics/{id}/simulate | テストバトル |

### チーム・バトル

| API | 内容 |
|---|---|
| POST /teams | チーム作成 |
| PUT /teams/{id} | チーム更新 |
| GET /teams/{id} | チーム詳細 |
| POST /battles/match | 対戦相手検索 |
| POST /battles | バトル実行 |
| GET /battles/{id} | バトル結果取得 |
| GET /ranking | ランキング取得 |

## データモデル概要

### users

- id
- name
- rating
- created_at

### captures

- id
- user_id
- original_image_url
- perceptual_hash
- safety_status
- created_at

### extracted_objects

- id
- capture_id
- mask_url
- crop_url
- bbox
- detected_label
- confidence
- feature_vector
- info_score

### mechs

- id
- user_id
- extracted_object_id
- form_type
- art_url
- rarity
- hp
- atk
- def
- spd
- tec
- en
- luck
- skills
- created_at

### tactic_sets

- id
- user_id
- name
- base_preset
- slots
- fallback_action
- created_by
- created_at

### teams

- id
- user_id
- name
- front_mech_id
- front_tactic_id
- middle_mech_id
- middle_tactic_id
- back_mech_id
- back_tactic_id
- created_at

### battles

- id
- player_a_id
- player_b_id
- team_a_id
- team_b_id
- seed
- result
- battle_log
- created_at

## RevenueCat 連携仕様

ハッカソン要件により、iOS / Android アプリには RevenueCat SDK を必ず組み込む。

### クライアント側

クライアントは以下を行う。

- RevenueCat SDK 初期化
- App User ID とアプリ内ユーザーIDの紐づけ
- Offerings の取得
- Paywall 表示
- 購入処理
- 購入復元
- CustomerInfo の取得
- Entitlement に応じた機能解放

### バックエンド側

バックエンドは RevenueCat Webhook を受け取る。

```text
RevenueCat
  ↓ Webhook
Backend API
  ↓
users / subscriptions / entitlements
```

### 追加API案

| API | 内容 |
|---|---|
| GET /billing/status | サーバー側の課金状態取得 |
| POST /billing/revenuecat/webhook | RevenueCat Webhook 受信 |
| POST /billing/sync | クライアントの CustomerInfo とサーバー状態の同期 |
| GET /billing/entitlements | 利用可能機能一覧取得 |

### データモデル追加案

#### user_entitlements

| column | type |
|---|---|
| id | uuid |
| user_id | uuid |
| revenuecat_app_user_id | text |
| entitlement_key | text |
| is_active | boolean |
| store | text |
| product_id | text |
| latest_purchase_at | timestamp |
| expiration_at | timestamp |
| updated_at | timestamp |

### 注意事項

- クライアントだけで課金状態を確定しない。
- ランク戦での戦術条件・行動・スロット数は Entitlement に依存させない。
- Entitlement は利便性機能、保存枠、見た目、要約機能に限定する。
