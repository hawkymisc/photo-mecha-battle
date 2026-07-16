# Photo Mecha Battle — Android クライアント（Phase 1 縦切り）

設計は [docs/11_mobile_client_design.md](../../docs/11_mobile_client_design.md) を正本とする。

## モジュール構成

| モジュール | 内容 |
|---|---|
| `core` | 純 JVM Kotlin。features/1.0 移植（`FeatureExtractor`）、簡易セグメンテーション、API クライアント・エラーマッピング。Android SDK 不要で単体テスト可能 |
| `app` | Jetpack Compose UI（S00〜S08）、CameraX 撮影、トークン永続化（EncryptedSharedPreferences） |

## ビルド・テスト

JDK 17 と Android SDK (platform 34) が必要。

**推奨（自動）** — リポジトリルートから:

```bash
# テストのみ
bash scripts/android_dev.sh --test

# ビルド + エミュレータへインストール + 起動
# (.tooling/ の JDK/SDK を自動使用、API ポートは 8000/8001 を自動検出)
bash scripts/android_dev.sh --launch
```

手動で Gradle を叩く場合は `clients/android/` で `./gradlew` を使う。初回は `local.properties` に `sdk.dir` が必要（`android_dev.sh` が自動生成する）。

```bash
cd clients/android

# 単体テスト（features/1.0 ゴールデン一致・API 契約）
./gradlew :core:test

# デバッグ APK
./gradlew :app:assembleDebug
```

`core:test` は `tests/golden/`（リポジトリ共有のゴールデンフィクスチャ）に対して
ε=0.05 での一致を検証する。これが features/1.0 移植の merge ゲート。

## エミュレータでの実地確認

```bash
# バックエンド起動（リポジトリルート。8000 が埋まっている場合は --port 8001）
python -m uvicorn photo_mecha_battle.api.app:app --host 0.0.0.0 --port 8000

# ワンコマンド（ビルド → インストール → 起動）
bash scripts/android_dev.sh --launch
```

API 接続先の上書き:

```bash
bash scripts/android_dev.sh --port 8001 --launch
bash scripts/android_dev.sh --api-url=http://192.168.x.x:8000 --launch
```

## 設計上の不変条件（AGENTS.md）

- バトルは演出のみ。勝敗・ダメージ・ステータスをクライアントで再計算しない（サーバー権威）
- `POST /mechs` は docs/09 主経路（multipart: `payload` JSON + `crop` RGBA PNG）を使う
- 特徴量はプレビュー表示のみ。確定値は常にサーバー応答
