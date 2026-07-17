# モバイルクライアント・開発環境・CI 静的レビュー

- 実施日: 2026-07-15
- 対象: `clients/**`、`scripts/android_dev.sh`、`.github/workflows/android.yml`、`.github/workflows/ios.yml`
- 正本: `docs/11_mobile_client_design.md`、`docs/12_environments.md`
- 補助参照: `docs/09_lightweight_server_architecture.md`、`AGENTS.md`
- 方法: 静的レビューのみ。コード・テストの変更およびビルド実行は行っていない。

## 総括

17 件の finding を確認した。

| 重大度 | 件数 |
|---|---:|
| Critical | 0 |
| High | 3 |
| Medium | 9 |
| Low | 5 |

Phase 1 縦切りのコア（features/1.0 ゴールデン一致、API 契約テスト、トークン永続化、401 導線、バトルログ再生のサーバー権威）は概ね仕様どおり実装されている。一方、**環境分離・リリース向け API URL 注入・CI の再現性**は `docs/12` が想定する staging / production 移行に未対応のまま残っており、ストア配布前のブロッカーになりうる。

## Findings

### ME-001 — Android release ビルドにも開発用 API URL が埋め込まれる

- 重大度: **High**
- file:line: `clients/android/app/build.gradle.kts:19-21`
- 対応仕様: `docs/12_environments.md:122-125` — release ビルドに local IP / cleartext URL を埋め込まない
- 影響:
  - `PMB_API_BASE_URL` が `defaultConfig` に定義されており、`-PpmbApiBaseUrl` 未指定の `assembleRelease` でも `http://10.0.2.2:8000` が BuildConfig に焼き込まれる。
  - 内部配布・ストア提出用 APK/AAB を誤ってビルドすると、本番相当 API に接続できない。運用上「release ビルド＝本番相当」と誤認しやすい。
- 推奨:
  - `buildTypes { debug { … } release { … } }` で URL を分離し、release では `-PpmbApiBaseUrl` 未指定時にビルド失敗させる。
  - CI に `assembleRelease -PpmbApiBaseUrl=https://…` の smoke を追加し、開発 URL が release に混入しないことをゲート化する。

### ME-002 — iOS の API URL が実行時デフォルト localhost に固定され、ビルド時注入がない

- 重大度: **High**
- file:line:
  - `clients/ios/PhotoMechaBattle/PhotoMechaBattleApp.swift:26-31`
  - `clients/ios/project.yml:18-24`
- 対応仕様: `docs/12_environments.md:122-125` — staging / production はビルド時または scheme / xcconfig で URL を固定
- 影響:
  - `PMB_API_BASE_URL` 環境変数が未設定の App Store / TestFlight ビルドは `http://127.0.0.1:8000` を向く。実機ではホスト側 API に到達できない。
  - `project.yml` に xcconfig / build setting がなく、CI の `xcodebuild` も URL を渡していない。再現可能な staging ビルド手順が文書化されていない。
- 推奨:
  - XcodeGen で `Debug.xcconfig` / `Release.xcconfig`（または scheme ごとの `PMB_API_BASE_URL`）を生成し、staging / production URL をビルド引数で差し替える。
  - CI の app-build ジョブで release 相当設定と URL を明示し、localhost デフォルトが残らないことを検証する。

### ME-003 — release ビルド検証が CI に存在しない

- 重大度: **High**
- file:line:
  - `.github/workflows/android.yml:28-30`
  - `.github/workflows/ios.yml:33-40`
- 対応仕様:
  - `docs/12_environments.md:63-76` — staging / production は release ビルドと HTTPS 固定
  - `docs/11_mobile_client_design.md:149` — UI / カメラは merge 前手動だが、ビルド型の回帰は CI で検知すべき
- 影響:
  - Android CI は `assembleDebug` のみ。release 固有の manifest 合成（cleartext 無効）、ProGuard、署名設定の破損が merge 後まで気づかれない。
  - iOS CI は `CODE_SIGNING_ALLOWED=NO` の Simulator ビルドのみ。Archive / release 設定・ATS・Info.plist 差分の検証がない。
- 推奨:
  - Android: `assembleRelease`（URL 必須引数付き）を CI に追加。
  - iOS: `xcodebuild archive` 相当、または release configuration の compile-only ビルドを追加。
  - いずれも URL 未設定時 fail を CI で固定する。

### ME-004 — iOS XcodeGen 定義に環境別 URL 設定がない

- 重大度: **Medium**
- file:line: `clients/ios/project.yml:1-25`
- 対応仕様: `docs/12_environments.md:120-125` — iOS は scheme / xcconfig の `PMB_API_BASE_URL`
- 影響:
  - `.xcodeproj` は gitignore され、`project.yml` が唯一の正本だが、環境 URL の定義がない。開発者ごとに Xcode scheme を手動設定する運用になり、staging ビルドの再現性が低い。
  - `docs/12` の「フレーバー後回し」方針と整合は取れるが、**暫定の URL 差し替え手順**がコード上に存在しない。
- 推奨:
  - `project.yml` に `configs`（Debug / Staging / Release）と `PMB_API_BASE_URL` のプレースホルダを追加する。
  - `clients/ios/README.md` の手動 scheme 設定を、生成物ベースの手順へ更新する。

### ME-005 — docs/11 必須の「ログ演出・表示モデル」テストが ApiClient パースのみ

- 重大度: **Medium**
- file:line:
  - `docs/11_mobile_client_design.md:148-149`
  - `clients/android/core/src/test/kotlin/com/photomecha/core/api/ApiClientTest.kt:64-86`
  - `clients/ios/PhotoMechaCore/Tests/PhotoMechaCoreTests/ApiClientTests.swift:97-120`
- 対応仕様: `docs/11_mobile_client_design.md:148-149` — `log_entries` サンプル JSON のパースと**表示モデル変換**を必須ゲートとする
- 影響:
  - JSON デシリアライズは検証されているが、`BattleScreen` / `BattleView` が利用する表示ラベル（`positionLabel`、条件成立理由、`damage_events` 展開）の回帰テストがない。
  - ログ UI 変更や `ApiModels` の optional フィールド変更が CI で検知されず、PO レビューまで演出欠落に気づかない可能性がある。
- 推奨:
  - 固定 JSON フィクスチャから表示用 DTO / 文言生成関数をテストする pure 関数テストを core に追加する（UI テスト不要）。
  - Android / iOS で同一フィクスチャを共用し、docs/11 の 3 層目ゲートを満たす。

### ME-006 — iOS CI の XcodeGen インストールがバージョン固定されていない

- 重大度: **Medium**
- file:line: `.github/workflows/ios.yml:28-29`
- 対応仕様: `docs/11_mobile_client_design.md:22` — `project.yml` を正本とし CI で生成（再現性が前提）
- 影響:
  - `brew install xcodegen` は Homebrew 更新に追随し、CI 実行日によって生成される `.xcodeproj` の差分が変わりうる。
  - ローカルと CI で XcodeGen バージョン不一致により「CI のみ green / ローカルのみ失敗」が発生しやすい。
- 推奨:
  - XcodeGen バージョンを pin（`brew install xcodegen@X.Y`、mise/asdf、または GitHub Release バイナリの checksum 固定）。
  - `project.yml` 変更時に生成物 diff を確認する手順を README に追記する。

### ME-007 — Android CI の SDK / Build-Tools バージョンが明示されていない

- 重大度: **Medium**
- file:line:
  - `.github/workflows/android.yml:24-25`
  - `clients/android/app/build.gradle.kts:10-11,14-15`
- 対応仕様: `docs/11_mobile_client_design.md:14-15` — compileSdk / platform 34（ビルド再現性）
- 影響:
  - `android-actions/setup-android@v3` はデフォルトパッケージセットに依存し、時期によりインストールされる build-tools / platform の組み合わせが変わる。
  - 将来の SDK 更新で CI のみ compile 警告・エラーが出るなど、ビルド再現性が損なわれる。
- 推奨:
  - workflow に `packages: platform-tools platforms;android-34 build-tools;34.0.0` 等を明示する。
  - `compileSdk` / NDK 要件を README と workflow の両方に記載する。

### ME-008 — android_dev.sh が API 未起動時も 8000 を黙って採用する

- 重大度: **Medium**
- file:line: `scripts/android_dev.sh:68-86,144-149`
- 対応仕様: `docs/12_environments.md:55` — ポート検出付き開発補助（`scripts/android_dev.sh`）
- 影響:
  - 8000 / 8001 いずれも `/docs` に応答しない場合、警告なしで `http://10.0.2.2:8000` を BuildConfig に焼き込む。
  - 開発者はビルド成功・起動成功と誤認し、実機確認で通信エラーに遭遇する。トラブルシュート時間が増える。
- 推奨:
  - 検出失敗時は非ゼロ終了、または `--port` / `--api-url` 明示を促す警告＋確認プロンプト（非対話 CI 向けは fail-fast）。
  - 採用 URL を `--launch` 前に必ず表示（現状は echo あり。失敗時の exit 1 が不足）。

### ME-009 — トークン永続化に alpha 版 security-crypto を使用

- 重大度: **Medium**
- file:line: `clients/android/app/build.gradle.kts:62`
- 対応仕様:
  - `docs/11_mobile_client_design.md:19` — EncryptedSharedPreferences
  - `AGENTS.md` 不変条件 5 — ユーザー画像・認証情報の安全な扱い
- 影響:
  - `androidx.security:security-crypto:1.1.0-alpha06` は安定版ではなく、将来の API 変更・不具合修正で EncryptedSharedPreferences の挙動が変わるリスクがある。
  - 端末 OS / Google Play サービス差異で初期化失敗した場合、アプリ起動時に例外で落ちる可能性がある（Register 画面まで到達しない）。
- 推奨:
  - 安定版リリース後にバージョンを引き上げ、EncryptedSharedPreferences 初期化失敗時のユーザー向けエラー導線を Register 以前に設計する。
  - iOS 側 `KeychainWriteError` と同等の error-surfacing を Android でも揃える（ME-012 参照）。

### ME-010 — 無効な PMB_API_BASE_URL で iOS アプリが起動時クラッシュする

- 重大度: **Medium**
- file:line: `clients/ios/PhotoMechaBattle/PhotoMechaBattleApp.swift:26-31`
- 対応仕様: `AGENTS.md` error-surfacing — 設定ミスを握り潰さずユーザーに伝える
- 影響:
  - `URL(string: baseURLString)!` により、typo や空文字の scheme 環境変数でアプリ起動直後に trap する。
  - PO レビュー前の scheme 設定ミスが「起動不能」に直結し、原因特定が難しい。
- 推奨:
  - `URL(string:)` の optional をハンドリングし、起動時に設定エラー画面を表示する。
  - Debug ビルドでは invalid URL を assert / log 出力する。

### ME-011 — HTTP クライアントにタイムアウトが未設定

- 重大度: **Medium**
- file:line:
  - `clients/android/core/src/main/kotlin/com/photomecha/core/api/ApiClient.kt:28`
  - `clients/ios/PhotoMechaCore/Sources/PhotoMechaCore/ApiClient.swift:18`
- 対応仕様: `docs/11_mobile_client_design.md:75` — タイムアウト / オフライン時はリトライ導線
- 影響:
  - OkHttp / URLSession デフォルトタイムアウトに依存し、サーバー無応答・Captive Portal 環境で長時間ハングする。
  - UI は `busy` 状態のまま固まり、docs/11 の「リトライボタン付きエラー」に到達しにくい。
- 推奨:
  - connect / read タイムアウト（例: 15s / 30s）を両プラットフォームで統一設定する。
  - タイムアウトを `NETWORK` 種別にマップし、既存 `userMessage` 導線へ接続する。

### ME-012 — Android はトークン永続化失敗を Register 画面で扱わない

- 重大度: **Medium**
- file:line:
  - `clients/android/app/src/main/kotlin/com/photomecha/battle/ui/RegisterScreen.kt:58-61`
  - `clients/android/app/src/main/kotlin/com/photomecha/battle/data/TokenStore.kt:18-24`
  - `clients/ios/PhotoMechaBattle/Views/RegisterView.swift:47-53`（対照）
- 対応仕様: `docs/11_mobile_client_design.md:69-70` — 401 時トークン破棄；error-surfacing 方針
- 影響:
  - iOS は Keychain 書込失敗を `KeychainWriteError` としてユーザーに通知するが、Android は `EncryptedSharedPreferences` 書込失敗時の扱いが未定義（例外送出または silent fail のいずれも UX 未設計）。
  - 登録 API 成功後にローカル保存だけ失敗すると、再起動で再登録を強いられるなどセッション不整合が起きうる。
- 推奨:
  - `TokenStore` の setter を `Result` / throw に統一し、Register 画面で iOS と同等の文言を表示する。
  - 保存失敗時は API トークンを破棄するか、再試行導線を明示する。

### ME-013 — android_dev.sh 変更が Android CI の path filter に含まれない

- 重大度: **Low**
- file:line: `.github/workflows/android.yml:5-13`
- 対応仕様: `docs/12_environments.md:55` — android_dev.sh を local 開発の補助正本と位置づけ
- 影響:
  - `scripts/android_dev.sh` のみの変更では CI が走らず、Gradle 引数 `-PpmbApiBaseUrl` との不整合や bash スクリプトの regression が merge される。
- 推奨:
  - path filter に `scripts/android_dev.sh` を追加する。
  - 可能なら `--test` 相当を CI の optional job として実行する。

### ME-014 — local.properties が初回作成後に更新されない

- 重大度: **Low**
- file:line: `scripts/android_dev.sh:60-66`
- 対応仕様: `docs/12_environments.md:55` — JDK/SDK 自動解決
- 影響:
  - 一度生成された `local.properties` の `sdk.dir` が古い `ANDROID_HOME` を指したまま残り、SDK 移行後に Gradle が誤パスを参照する。
  - `.gitignore` 対象のため、チーム内で再現しにくい「ローカルのみビルド失敗」が起きる。
- 推奨:
  - 現在の `ANDROID_HOME` と `sdk.dir` が不一致なら上書き更新する。
  - README に `local.properties` 削除手順を追記する。

### ME-015 — docs/11 の JUnit 5 記載と Android 実装（JUnit 4）が不一致

- 重大度: **Low**
- file:line:
  - `docs/11_mobile_client_design.md:21`
  - `clients/android/core/build.gradle.kts:18`
- 対応仕様: `docs/11_mobile_client_design.md:21`
- 影響:
  - ドキュメント上は JUnit 5 だが、core テストは JUnit 4 アノテーション。新規 contributor が JUnit 5 API（`@ExtendWith` 等）でテストを書き、ビルド失敗する。
- 推奨:
  - docs/11 を JUnit 4（現状）に合わせるか、Gradle を JUnit 5 に移行する。どちらか一方に統一する。

### ME-016 — iOS Info.plist の ATS 緩和が全ビルドに適用される

- 重大度: **Low**
- file:line: `clients/ios/PhotoMechaBattle/Info.plist:19-23`
- 対応仕様: `docs/12_environments.md:76` — production は TLS 必須；MVP ではピン留め任意
- 影響:
  - `NSAllowsLocalNetworking` は release ビルドにも残る。本番 API が HTTPS なら通常は問題にならないが、誤って HTTP staging URL を実機 release に設定した場合、ローカルネットワーク向け HTTP が通りうる。
  - 環境分離の「設定ミス検知」が弱い。
- 推奨:
  - Release configuration 用 Info.plist（または build setting）で ATS 例外を外す。
  - staging は HTTPS を正とし、HTTP は Debug のみに限定する。

### ME-017 — iOS ゴールデンテストの特徴量一致が macOS / CoreGraphics 環境に限定

- 重大度: **Low**
- file:line: `clients/ios/PhotoMechaCore/Tests/PhotoMechaCoreTests/GoldenFeaturesTests.swift:59-135`
- 対応仕様: `docs/11_mobile_client_design.md:127-128` — ゴールデン一致は merge 必須ゲート
- 影響:
  - `#if canImport(CoreGraphics)` 外では `testGoldenFeatureParity` がコンパイルされず、Linux 上の `swift test` では manifest バージョン確認のみ実行される。
  - CI（macOS）は問題ないが、Linux 開発者が「swift test green」を merge 条件と誤解する余地がある。
- 推奨:
  - README に「特徴量 parity は macOS CI 必須」と明記する。
  - または Linux CI job を設けず、PhotoMechaCore の CI 正本を macOS workflow に一本化する旨を docs/11 に追記する。

## 問題なしと確認した点

- **環境 URL（local / debug）**: Android エミュレータ向け `10.0.2.2`、iOS シミュレータ向け `127.0.0.1` は `docs/12_environments.md:50` と整合。`android_dev.sh` は `-PpmbApiBaseUrl` で Gradle BuildConfig へ注入する（`scripts/android_dev.sh:155`、`clients/android/app/build.gradle.kts:20`）。
- **Cleartext HTTP の限定**: Android は `src/debug/AndroidManifest.xml` の overlay のみ `usesCleartextTraffic=true`（`clients/android/app/src/debug/AndroidManifest.xml:5-8`）。main manifest には平文許可がなく、release は OS デフォルト（HTTPS 優先）に従う（`clients/android/app/src/main/AndroidManifest.xml:8`）。
- **秘密情報のハードコード**: `clients/**` に API キー・管理者トークン・RevenueCat シークレットの埋め込みは見つからなかった。認証は `X-User-Token` を Keychain / EncryptedSharedPreferences に保存する設計どおり（`docs/11_mobile_client_design.md:19-20`）。
- **トークンストア**: Android `EncryptedSharedPreferences`、iOS Keychain（`kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`）で docs/11 の MVVM 構成と一致。
- **401 導線**: 両 OS で API 画面（Home / Analyze / MechDetail / Formation / Battle）が `UNAUTHORIZED` / `.unauthorized` 時にトークン破棄→ S00 へ遷移（`MainActivity.kt:55-59`、`PhotoMechaBattleApp.swift:36-41`、各 Screen / View）。
- **エラーマッピング CI ゲート**: Android `ApiErrorMapperTest` / iOS `ApiErrorMapperTests` が docs/11 の 401 / 409 / 422 unsafe / feature_mismatch / 429 をカバー（`ApiErrorMapperTest.kt`、`ApiErrorMapperTests.swift`）。
- **features/1.0 ゴールデン一致**: Android `:core:test` は `pmb.golden.dir` で `tests/golden/` を注入（`core/build.gradle.kts:22-27`）。iOS `GoldenFeaturesTests` も同一 manifest を参照（`GoldenFeaturesTests.swift:38-50`）。CI path filter に `tests/golden/**` が含まれる（両 workflow）。
- **API 主経路 multipart**: Android / iOS とも `POST /mechs` が `payload` JSON + `crop` PNG を送信する契約テストあり（`ApiClientTest.kt:31-61`、`ApiClientTests.swift:68-95`）。
- **バトルサーバー権威**: `BattleScreen` / `BattleView` は `GET /battles/{id}` の `log_entries` を演出再生のみ行い、クライアント側ダメージ再計算はない（`BattleScreen.kt:32-35`、`BattleView.swift:5-6`）。
- **Gradle ラッパー pin**: `gradle-8.14.3`（`clients/android/gradle/wrapper/gradle-wrapper.properties:3`）。AGP 8.5.2 / Kotlin 2.0.20 も root `build.gradle.kts` で明示。
- **gitignore**: `local.properties`（Android）、`.xcodeproj`（iOS）が ignore され、開発者固有パスがコミットされない（`clients/android/.gitignore:3`、`clients/ios/.gitignore:3`）。
- **docs/12 との整合（Phase 1 スコープ）**: フレーバー後回し・URL ビルド引数差し替え・`PMB_ENV` ガード後回しは `docs/12_environments.md:178-181, 191-202` の実装ブロッカー表と一致。本レビューはその「意図的な未実装」と「リリース前に解消すべきギャップ」を区別して記載した。

## テスト・CI 上の主な空白

- release ビルド + staging / production URL 注入の CI smoke（ME-001〜003）
- バトルログ UI 表示モデル変換の pure テスト（ME-005）
- `scripts/android_dev.sh` の regression 用 workflow path / スクリプトテスト（ME-013）
- Android TokenStore 永続化失敗・EncryptedSharedPreferences 初期化失敗の負例（ME-009, ME-012）
- HTTP タイムアウト → NETWORK 導線の契約テスト（ME-011）

## 優先対応順（提案）

1. **ME-001 / ME-002 / ME-003** — ストア・内部配布前に release 向け URL 注入と CI ゲートを整備
2. **ME-004 / ME-006 / ME-007** — ビルド再現性（XcodeGen / SDK pin、project.yml 設定）
3. **ME-008 / ME-011 / ME-012** — 開発体験と error-surfacing の改善
4. **ME-005 / ME-009 / ME-010** — 仕様ゲート充足と依存安定化
