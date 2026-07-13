# 12. 環境設計（local / staging / production）

[← 仕様書一覧](00_root_overview.md)

## 目的

本ドキュメントは、Photo Mecha Battle の **API サーバー・モバイルクライアント・外部サービス** を、どの環境でどう分離するかを定義する。

[`docs/09`](09_lightweight_server_architecture.md) の「薄いサーバー」方針を前提に、**MVP〜β までは環境を増やしすぎない**。本番相当の分離が必要なときだけ段階的に厚くする。

## 前提の棚卸し（この設計で意図的に捨てた案）

| 検討案 | 採用しない理由 |
|---|---|
| `dev` / `qa` / `staging` / `prod` の 4 系統 | 運用コストに対し現フェーズの利用者が少ない。QA は staging を共用する |
| 本番前からマネージド DB・CDN・K8s を必須化 | docs/09 の軽量サーバーと矛盾。単一プロセス + 永続ボリュームで足りる範囲を先に固める |
| クライアントのみで完結するオフライン本番 | バトル・ランキング・課金・不正対策はサーバー権威（[`docs/00`](00_root_overview.md) 原則5・AGENTS.md） |
| 環境ごとに別リポジトリ / 別ブランチ運用 | `develop` → `main` の既存 Git 運用に乗せる（[`AGENTS.md`](../AGENTS.md)） |

## 環境一覧（正本）

| 環境 ID | 用途 | 誰が使うか | データ寿命 |
|---|---|---|---|
| `local` | 開発者の手元。機能実装・単体/結合・エミュレータ確認 | 開発者 | 捨ててよい（`data/` 削除可） |
| `staging` | 共有検証・PO レビュー・ストア sandbox 課金・リリース候補の受け入れ | 開発者 + PO + QA 相当 | リセット可能（告知のうえ全消し可） |
| `production` | 実ユーザ向け。課金・ランキング・対戦記録の正 | エンドユーザ | 不可逆。削除は AGENTS.md チェックポイント対象 |

**QA 環境は独立させない。** 受け入れ・回帰・課金 sandbox はすべて `staging` で行う。利用者が増え、staging の破壊的リセットが PO レビューと衝突するようになった時点で `qa` 分離を検討する（下記「将来拡張」）。

```text
[開発者端末]
  local API (uvicorn) ←→ エミュレータ / シミュレータ / 実機(LAN)
         │
         │  PR → CI → develop
         ▼
[staging] 共有 API + staging 用モバイルビルド
         │  受け入れ OK → develop → main の計画リリース
         ▼
[production] 本番 API + ストア配布ビルド
```

## 環境ごとの責務

### `local`

| 項目 | 方針 |
|---|---|
| API | 開発者端末で `uvicorn` 起動（[`/.claude/skills/run/SKILL.md`](../.claude/skills/run/SKILL.md)） |
| DB / メディア | リポジトリの `data/`（gitignore）。SQLite は `{PMB_DATA_DIR}/pmb.sqlite3`（`PMB_DB_PATH` で上書き可） |
| クライアント API URL | Android エミュレータ: `http://10.0.2.2:<port>` / iOS シミュレータ: `http://127.0.0.1:<port>` / 実機: `http://<LAN IP>:<port>` |
| TLS | 不要（cleartext は **debug ビルドのみ**） |
| 課金 | RevenueCat **sandbox**。`PMB_ADMIN_TOKEN` はデモ付与用に設定可 |
| Web デモ | `GET /app/` をローカルで配信してよい（本番モバイルの代替ではない） |

補助スクリプト例: リポジトリの `scripts/android_dev.sh`（JDK/SDK・API ポート検出・ビルド/インストール）。

### `staging`（QA 共用）

| 項目 | 方針 |
|---|---|
| API | 常時またはオンデマンドの **1 インスタンス**。公開 URL は HTTPS |
| DB / メディア | local と **完全分離**。定期リセット手順を文書化（リセット前に PO へ告知） |
| クライアント | 内部配布（TestFlight / 内部トラック）または debug/staging フレーバー。API ベース URL をビルド時またはリモート設定で staging に固定 |
| TLS | 必須 |
| 課金 | RevenueCat **sandbox** + Webhook を staging API へ向ける |
| 管理者 API | `PMB_ADMIN_TOKEN` を設定してよい（デモ Entitlement）。トークンは本番と共用しない |
| 用途 | Phase 1 縦切りの PO レビュー、ストア sandbox 購入、リリース前スモーク |

### `production`

| 項目 | 方針 |
|---|---|
| API | 可用性を意識した常時稼働。バックアップ取得を必須化してから公開 |
| DB / メディア | 専用。staging からのコピーで起動しない（課金・ユーザ ID 混入防止） |
| クライアント | App Store / Google Play の release ビルドのみ。API URL は本番固定 |
| TLS | 必須。証明書ピン留めは MVP では任意（β 以降で検討） |
| 課金 | RevenueCat **production**。`PMB_ADMIN_TOKEN` は **未設定**（デモ付与 API を常時 403） |
| Webhook | `PMB_REVENUECAT_WEBHOOK_SECRET` 必須。未設定なら Webhook を拒否（現行実装どおり） |
| Web デモ `/app/` | **配信しない**（または認証付きの運用ツールに隔離） |

## 構成要素と環境マトリクス

| 構成要素 | local | staging | production |
|---|---|---|---|
| FastAPI (`photo_mecha_battle.api.app`) | ○ | ○ | ○ |
| SQLite（ファイル永続） | ○ | ○（単一ノード想定） | ○ → 負荷でマネージド DB へ移行検討 |
| 画像ストレージ（`PMB_DATA_DIR`） | ローカル disk | 永続ボリューム | 永続ボリューム or オブジェクトストレージ |
| 簡易 Web `/app/` | ○ | △（任意・内部のみ） | × |
| GitHub Actions CI | PR / develop | （同じパイプライン） | main 向けは計画リリース時 |
| RevenueCat | sandbox | sandbox | production |
| ストア配布 | なし（adb / Xcode） | 内部配布 | 本番ストア |

## 設定・シークレット

環境変数の正本はコードと本表。未設定時の fail-closed 挙動を本番デフォルトとする。

| 変数 | 意味 | local | staging | production |
|---|---|---|---|---|
| `PMB_DATA_DIR` | メディア等のルート | `data`（既定） | 環境専用パス | 環境専用パス |
| `PMB_DB_PATH` | SQLite ファイルパス | 未設定時 `{PMB_DATA_DIR}/pmb.sqlite3` | 永続パス | 永続パス |
| `PMB_WEB_DIR` | `/app` 静的配信元 | `web/` | 未設定または内部のみ | **未設定（マウントしない）** |
| `PMB_ADMIN_TOKEN` | デモ Entitlement 付与 | 任意 | 設定可（本番と別値） | **未設定** |
| `PMB_REVENUECAT_WEBHOOK_SECRET` | Webhook 認証 | 任意 | sandbox 用 | **必須** |
| `PMB_ENV` | 環境ラベル（任意・後述） | `local`（推奨） | `staging` | `production` |
| クライアント `PMB_API_BASE_URL` | API オリジン | エミュ向け既定 | staging HTTPS | production HTTPS |

### `PMB_ENV` とは何か

アプリが「今どの環境として動いているか」を自分で知るための**文字列ラベル**である。ホスト名やデプロイ先そのものではない。

想定用途（実装は後回し可）:

- ログやエラー通知に `env=production` と付ける
- `PMB_ENV=production` のときだけ厳しい起動チェックをかける  
  例: `PMB_ADMIN_TOKEN` が設定されていたら起動失敗（デモ API の本番誤開放を防ぐ）  
  例: `/app` Web デモをマウントしない

未設定でも API は動く。**必須ではない。** 本番公開前にガードを入れる段階で本格利用する。

クライアント側:

- Android: `BuildConfig.PMB_API_BASE_URL`（Gradle `-PpmbApiBaseUrl=`）
- iOS: scheme / xcconfig の `PMB_API_BASE_URL`
- **release ビルドに local IP / cleartext を埋め込まない**（Android は debug manifest overlay で cleartext を限定済み）
- staging / production 向け **ビルドフレーバーは後回し**（当面は URL をビルド引数で差し替え）

## データ分離と不可逆操作

| データ | local | staging | production |
|---|---|---|---|
| ユーザ・トークン | 破棄可 | リセット可（告知） | 削除禁止（運用手順 + 承認） |
| `battles` / レーティング | 破棄可 | リセット可 | AGENTS.md チェックポイント |
| ユーザ画像 | 破棄可 | リセット可 | バケット一括削除は不可逆 |
| Entitlement | sandbox のみ | sandbox のみ | production 顧客データ |

環境をまたいだ **DB ファイルのコピーは禁止**（特に staging → production）。必要なのはスキーマ移行スクリプトと空の production 初期化のみ。

## デプロイとブランチ対応

既存 Git 運用に合わせる。

| Git | 環境への反映 |
|---|---|
| `feature/*` → PR → `develop` | CI green。local で検証。必要なら staging へ手動/自動デプロイ |
| `develop` → `main`（計画リリース） | production デプロイの候補。ノールックマージ対象外 |
| ホットフィックス | `main` から `fix/*` → `main` と `develop` へ戻しマージ（手順はリリース運用で追記） |

**ホスティング先:** 候補は **Cloudflare**（アカウント未作成・未契約）。選定基準は維持する:

1. HTTPS 終端が容易
2. 永続ボリュームまたはオブジェクトストレージが使える（SQLite ファイル or R2）
3. 環境変数でシークレットを渡せる
4. **単一プロセスで FastAPI（Python）を起動できる**
5. 月額コストがハッカソン〜β 規模に見合う

**Cloudflare 採用時の注意:** Workers 単体では既存の FastAPI をそのまま動かない。現実的な形は次のいずれか。

- **Cloudflare Containers**（コンテナで uvicorn を動かす）+ 永続ディスク / R2
- API は別の安い PaaS、Cloudflare は DNS・TLS・将来の R2/CDN のみ

アカウント作成後に E-001 を確定する。選定結果は本節と [`docs/08`](08_mvp_and_roadmap.md) を更新する。

## フェーズとの対応

| フェーズ | 環境の最低条件 |
|---|---|
| Phase 1 縦切り（現在） | `local` 必須。`staging` は PO が手元以外で触る必要が出た時点で立ち上げ |
| Phase 2 MVP（ストア提出前） | `staging` 必須（sandbox 課金・内部配布）。SQLite ファイル永続・バックアップ手順が production ブロッカー |
| Phase 3 β | `production` を限定公開。監視（最低限の uptime / エラーログ）を追加 |
| Phase 4 正式版 | 負荷に応じて DB・ストレージ・水平スケールを再設計。必要なら `qa` を staging から分離 |

## 実装ブロッカー（現状コードとの差分）

設計変更ではなく実装ギャップ。PO 決定反映済みの項目はステータスを更新する。

| 項目 | 状態 | 内容 |
|---|---|---|
| SQLite ファイル永続化 | **採用・実装** | `PMB_DB_PATH` または `{PMB_DATA_DIR}/pmb.sqlite3`。テストは `:memory:` 差し替えを維持 |
| `PMB_ENV` ガード | 後回し | ラベルの意味は上記。production 向け起動チェックは公開前に入れる |
| ホスティング | 候補 Cloudflare（アカウント未） | Containers 等で FastAPI を動かせるか検証してから契約 |
| クライアント フレーバー | **後回し** | 当面は `-PpmbApiBaseUrl` / scheme 環境変数で URL 差し替え |

## 将来拡張（今はやらない）

- 独立 `qa` 環境（staging 破壊的リセットが日常化したとき）
- 読み取りレプリカ、CDN、オブジェクトストレージ必須化
- Blue/Green・カナリア（ユーザ数が増えてから）
- 証明書ピン留め・デバイス Attestation
- マルチリージョン

## 未決の解消（PO / 運用判断待ち）

| ID | 内容 | 状態 |
|---|---|---|
| E-001 | staging / production のホスティング先 | **候補 Cloudflare**（アカウント未）。Workers 非対応のため Containers 等を要検証 |
| E-002 | staging の常時起動 vs オンデマンド | 未決（PO レビュー頻度次第） |
| E-003 | ドメイン名（例: `api-staging.` / `api.`） | 未決 |
| E-004 | production バックアップ頻度と復旧目標（RPO/RTO） | 未決 |
| E-005 | 内部配布手段（TestFlight / Play 内部テスト等） | 未決 |
| — | DB 永続化方式 | **決定: ファイル SQLite**（`PMB_DB_PATH`） |
| — | クライアント フレーバー | **後回し**（URL 差し替えで暫定） |
| — | `PMB_ENV` 起動ガード | **後回し**（公開前） |
