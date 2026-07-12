# Photo Mecha Battle — iOS クライアント（Phase 1 縦切り）

Swift / SwiftUI 製のネイティブクライアント。設計は [docs/11](../../docs/11_mobile_client_design.md) を正本とし、Android 版（`clients/android/`）と同一の画面構成・API 経路を実装する。

## 構成

| パス | 内容 |
|---|---|
| `PhotoMechaCore/` | Swift Package。features/1.0 の PIL 互換移植・簡易セグメンテーション・API クライアント（UI 非依存、macOS でもテスト可能） |
| `PhotoMechaBattle/` | SwiftUI アプリ本体（S00〜S08 の画面、AVFoundation 撮影、Keychain トークン保存） |
| `project.yml` | XcodeGen 定義。`xcodegen generate` で `.xcodeproj` を生成する |

## ビルド・テスト

Linux 開発環境では Xcode ビルドできないため、**GitHub Actions の macOS ランナー**（`.github/workflows/ios.yml`）が merge ゲート。

ローカル（Mac）での手順:

```bash
# core のユニットテスト（ゴールデンフィクスチャ一致 + API クライアント契約）
cd clients/ios/PhotoMechaCore
swift test

# アプリのシミュレータビルド
cd clients/ios
brew install xcodegen   # 未導入の場合
xcodegen generate
xcodebuild -project PhotoMechaBattle.xcodeproj -scheme PhotoMechaBattle \
  -destination 'platform=iOS Simulator,name=iPhone 15' build
```

## API 接続先

デフォルトは `http://127.0.0.1:8000`。環境変数 `PMB_API_BASE_URL`（Xcode の scheme 環境変数）で上書きできる。シミュレータからホストの uvicorn へは `http://127.0.0.1:8000` がそのまま届く。

## ゴールデンフィクスチャ

`tests/golden/` を Android / iOS / サーバーで共用する。`GoldenFeaturesTests` は `#filePath` からリポジトリルートを解決する（`PMB_GOLDEN_DIR` 環境変数で上書き可）。特徴量の許容差は manifest の `tolerance`（ε=0.05）。

## 実機確認（PO レビュー）

カメラ撮影は実機のみ（シミュレータはカメラ非対応）。Mac + iPhone で:

1. `xcodegen generate` → Xcode でプロジェクトを開き、Signing を自分の Apple ID に設定
2. バックエンドを LAN で起動し、scheme の `PMB_API_BASE_URL` を `http://<MacのIP>:8000` に設定
3. 実機で 登録 → 撮影 → 選択 → 生成 → 編成 → CPU 戦 → ログ を通す
