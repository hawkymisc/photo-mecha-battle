# Photo Mecha Battle — Android クライアント（Phase 1 縦切り）

設計は [docs/11_mobile_client_design.md](../../docs/11_mobile_client_design.md) を正本とする。

## モジュール構成

| モジュール | 内容 |
|---|---|
| `core` | 純 JVM Kotlin。features/1.0 移植（`FeatureExtractor`）、簡易セグメンテーション、API クライアント・エラーマッピング。Android SDK 不要で単体テスト可能 |
| `app` | Jetpack Compose UI（S00〜S08）、CameraX 撮影、トークン永続化（EncryptedSharedPreferences） |

## ビルド・テスト

JDK 17 と Android SDK (platform 34) が必要。`local.properties` に `sdk.dir` を設定する。

```bash
# 単体テスト（features/1.0 ゴールデン一致・API 契約。Android SDK 不要）
gradle :core:test

# デバッグ APK
gradle :app:assembleDebug
```

`core:test` は `tests/golden/`（リポジトリ共有のゴールデンフィクスチャ）に対して
ε=0.05 での一致を検証する。これが features/1.0 移植の merge ゲート。

## エミュレータでの実地確認

```bash
# バックエンド起動（リポジトリルート）
uvicorn photo_mecha_battle.api.app:app --host 0.0.0.0 --port 8000

# インストールと起動（デフォルトの API 先はエミュレータから見たホスト 10.0.2.2:8000）
adb install app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n com.photomecha.battle/.MainActivity
```

API 接続先は Gradle プロパティで変更できる:

```bash
gradle :app:assembleDebug -PpmbApiBaseUrl=http://192.168.x.x:8000
```

## 設計上の不変条件（AGENTS.md）

- バトルは演出のみ。勝敗・ダメージ・ステータスをクライアントで再計算しない（サーバー権威）
- `POST /mechs` は docs/09 主経路（multipart: `payload` JSON + `crop` RGBA PNG）を使う
- 特徴量はプレビュー表示のみ。確定値は常にサーバー応答
