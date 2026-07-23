# 13. ビルドと実機確認

[← 仕様書一覧](00_root_overview.md)

## 目的

iOS / Android ネイティブクライアントを **手元でビルドし、エミュレータまたは実機に入れて確認する** 手順をまとめる。

- 画面・API 設計の正本: [`docs/11`](11_mobile_client_design.md)
- 環境（local / staging / production）の正本: [`docs/12`](12_environments.md)
- クライアント別の短い README: [`clients/android/README.md`](../clients/android/README.md) / [`clients/ios/README.md`](../clients/ios/README.md)
- Web プロトタイプでのコアループ確認: [`.claude/skills/run/SKILL.md`](../.claude/skills/run/SKILL.md)

本書は **local 開発**（開発者端末上の API + デバッグビルド）を主対象とする。ストア配布や staging 向け署名は [`docs/12`](12_environments.md) を参照。

## クライアントの場所

| プラットフォーム | パス | 技術 |
|---|---|---|
| Android | `clients/android/` | Kotlin / Jetpack Compose / Gradle |
| iOS | `clients/ios/` | Swift / SwiftUI / XcodeGen |

現状は Phase 1 縦切り（登録 → 撮影 → オブジェクト選択 → メカ生成 → プリセット戦術 → CPU 戦 → ログ）。

## 共通: バックエンド起動

ネイティブアプリはローカル API に接続する。先にサーバーを起動する。

```bash
# リポジトリルート
python -m uvicorn photo_mecha_battle.api.app:app --host 0.0.0.0 --port 8000
```

| 接続元 | API ベース URL の目安 |
|---|---|
| Android エミュレータ | `http://10.0.2.2:8000`（ホストの localhost 相当） |
| iOS シミュレータ | `http://127.0.0.1:8000` |
| 実機（同一 LAN） | `http://<開発機のLAN IP>:8000` |

- ポート 8000 が埋まっている場合は `--port 8001` などへ変更し、クライアント側の URL も合わせる。
- ファイアウォールで着信（例: 8000）を許可する必要がある場合がある。
- ブラウザだけでコアループを見る場合は `http://127.0.0.1:8000/app/`（本番モバイルの代替ではない）。

## Android

### 前提

| 項目 | 内容 |
|---|---|
| OS | Linux / macOS / Windows（本リポジトリの Linux 開発環境でビルド可） |
| JDK | 17 |
| Android SDK | platform 34 + `platform-tools`（adb） |
| 端末 | USB デバッグ ON の実機、または起動済みエミュレータ |

リポジトリの `.tooling/jdk` と `.tooling/android-sdk` がある場合、下記スクリプトが自動で参照する。手動なら `JAVA_HOME` / `ANDROID_HOME` を設定する。

### 推奨: ワンコマンド（ビルド → インストール → 起動）

```bash
# サーバー起動後、リポジトリルートで
bash scripts/android_dev.sh --launch
```

スクリプトは次を行う。

1. JDK / SDK / `local.properties` を解決
2. 稼働中 API（8000 → 8001）を検出（未検出時は 8000）
3. デフォルトで `PMB_API_BASE_URL=http://10.0.2.2:<port>` を埋め込んで debug APK をビルド
4. `adb install -r` → `MainActivity` 起動

#### 実機向け（LAN IP を指定）

エミュレータ用の `10.0.2.2` は実機では使えない。

```bash
bash scripts/android_dev.sh --api-url=http://192.168.x.x:8000 --launch
```

`192.168.x.x` は開発機の LAN IP。端末と同一 Wi-Fi であること。

#### よく使うオプション

```bash
bash scripts/android_dev.sh --test          # :core:test のみ
bash scripts/android_dev.sh --install       # ビルド + インストール（起動なし）
bash scripts/android_dev.sh --port 8001 --launch
```

### 手動 Gradle

```bash
cd clients/android
# 初回: local.properties に sdk.dir=<ANDROID_HOME> が必要（android_dev.sh が自動生成可）

./gradlew :core:test
./gradlew :app:assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk

adb devices   # device が 1 台以上あること
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n com.photomecha.battle/.MainActivity
```

API URL をビルド時に埋め込む場合:

```bash
./gradlew :app:assembleDebug -PpmbApiBaseUrl=http://192.168.x.x:8000
```

未指定時のデフォルトは `http://10.0.2.2:8000`（エミュレータ向け）。

### 注意（Android）

- **debug** ビルドのみ cleartext（HTTP）を許可する想定。release で `http://` のまま接続すると失敗する（[`docs/12`](12_environments.md)）。
- カメラ実機確認は実機推奨。エミュレータは仮想カメラに依存する。

## iOS

### 前提

| 項目 | 内容 |
|---|---|
| OS | **macOS + Xcode 必須**（Linux ではアプリ本体をビルドできない） |
| ツール | XcodeGen（`brew install xcodegen`） |
| 端末 | シミュレータ、または Signing 設定済みの実機 iPhone |
| CI | Linux 開発時のビルド検証は `.github/workflows/ios.yml`（macOS ランナー） |

### プロジェクト生成とビルド

```bash
cd clients/ios
xcodegen generate   # PhotoMechaBattle.xcodeproj を生成

# core のユニットテスト（macOS でも可）
cd PhotoMechaCore && swift test && cd ..

# シミュレータビルド例
xcodebuild -project PhotoMechaBattle.xcodeproj -scheme PhotoMechaBattle \
  -destination 'platform=iOS Simulator,name=iPhone 15' build
```

日常の確認は Xcode で `.xcodeproj` を開き Run するのが簡単。

### API 接続先

- デフォルト: `http://127.0.0.1:8000`
- 上書き: Xcode scheme の環境変数 `PMB_API_BASE_URL`
- シミュレータ → ホストの uvicorn: `http://127.0.0.1:8000` のままでよい
- **実機**: `http://<MacのLAN IP>:8000` に変更

### 実機インストール（PO / カメラ確認）

1. `xcodegen generate` → Xcode でプロジェクトを開く
2. Signing & Capabilities で自分の Apple ID（Personal Team 可）を設定
3. scheme の `PMB_API_BASE_URL` を LAN 上の API に合わせる
4. 接続した iPhone を選択して Run
5. 初回は「開発元を信頼」などの端末側設定が必要な場合あり

**カメラは実機のみ**（シミュレータは非対応）。撮影を含む縦切り確認は実機で行う。

## スモーク確認の順序（コアループ）

ネイティブ UI 上で次を通す。

1. パイロット登録（`POST /auth/register`）
2. 撮影 → オブジェクト選択
3. メカ生成・命名
4. 戦術プリセット選択
5. チーム編成（3 体）
6. CPU 戦 → バトルログ確認

API を直接叩く場合の依存順は [`.claude/skills/run/SKILL.md`](../.claude/skills/run/SKILL.md) を参照。

確認の観点（抜粋）:

- 勝敗・ダメージはサーバー応答のみを信頼する（クライアントで再計算しない）
- 接続失敗時は API URL・サーバー起動・同一 LAN・ファイアウォールを疑う

## トラブルシュート

| 症状 | 確認すること |
|---|---|
| `adb` / デバイスなし | USB デバッグ、`adb devices`、ケーブル、エミュレータ起動 |
| Android が API に繋がらない | エミュレータなら `10.0.2.2`、実機なら LAN IP。サーバーは `--host 0.0.0.0` |
| iOS 実機が API に繋がらない | `PMB_API_BASE_URL`、Mac と iPhone が同一 Wi-Fi、ATS / cleartext（debug 設定） |
| JDK / SDK エラー | `.tooling/` の有無、または `JAVA_HOME` / `ANDROID_HOME` |
| Linux で iOS がビルドできない | 想定どおり。Mac または GitHub Actions の ios workflow を使う |
| release APK で HTTP 失敗 | cleartext は debug のみ。staging/production は HTTPS（docs/12） |

## 関連パス早見

| 用途 | パス |
|---|---|
| Android 自動化スクリプト | `scripts/android_dev.sh` |
| Android アプリ | `clients/android/` |
| iOS アプリ | `clients/ios/` |
| iOS CI | `.github/workflows/ios.yml` |
| ゴールデン特徴量（共用） | `tests/golden/` |
