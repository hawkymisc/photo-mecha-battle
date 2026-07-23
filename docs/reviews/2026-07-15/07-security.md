# セキュリティ設計・設定 静的レビュー

- 実施日: 2026-07-15
- 対象: 認証認可、所有権、課金境界、画像アップロード、CORS、秘密情報、ログ、CI、Android/iOS 設定
- 方法: コード・設定・既存レビュー文書の静的確認のみ（コード変更・実行検証なし）
- 正本: `docs/07_platform_and_system.md`、`docs/09_lightweight_server_architecture.md`、`docs/12_environments.md`、`AGENTS.md`
- 関連レビュー: `02-backend-api.md`、`04-capture-ml.md`、`06-tests-ci.md`、`08-billing-fairness.md`、`10-security-diff.md`

## 総括

**32 件**の finding を確認した（Critical 1 / High 12 / Medium 13 / Low 6）。

| 重大度 | 件数 |
|---|---:|
| Critical | 1 |
| High | 12 |
| Medium | 13 |
| Low | 6 |

最優先は、認証済みクライアントが `POST /billing/sync` で有料 Entitlement を自己付与できる点（BF-001）、他ユーザー資産をランク戦チームへ混入できる点（BE-002 / BF-002）、ユーザー画像が `/media` 経由で無認証公開される点（CAP-ML-001）である。環境分離として `PMB_ENV=production` 起動ガードが未実装のため、デモ用エンドポイントと Web クライアントが本番でも有効なまま残る（SEC-001 / SEC-010）。

## 監査カバレッジ

| 領域 | 確認対象 | 状態 |
|---|---|---|
| 認証認可 | `app.py` `require_user` / `require_admin` / `require_revenuecat_webhook_auth`、`database.py` | 部分的 |
| 所有権 | チーム・バトル・メカ・戦術・capture 経路 | 部分的 |
| 課金境界 | `/billing/*`、Webhook、Entitlement、クォータ | 要修正 |
| 画像アップロード | upload、direct `/mechs`、安全性フィルタ、静的配信 | 要修正 |
| CORS | FastAPI ミドルウェア、Web デモ `fetch` | 方針未定義 |
| 秘密情報 | 環境変数、テスト固定値、クライアント保存 | 概ね良好 |
| ログ | API・クライアントのセキュリティイベント記録 | 不足 |
| CI | `.github/workflows/*`、`pyproject.toml` | Python ゲートなし |
| Android/iOS | Manifest、Info.plist、TokenStore、ビルド設定 | 開発向け設定は適切 |

---

## 1. 認証・認可

### BF-001 — クライアント自己申告だけで Entitlement を付与できる

- **重大度:** Critical
- **統合参照:** `08-billing-fairness.md` BF-001、`02-backend-api.md` BE-001
- **file:line:** `src/photo_mecha_battle/api/app.py:702-708`; `src/photo_mecha_battle/api/game_store.py:517-527`; `tests/test_phase2.py:484-521`
- **影響:** 無課金ユーザーが既知 Entitlement キーを自己申告するだけで `generation_boost` 等を有効化でき、日次クォータ上限が拡大する。Webhook 認証を強化しても別経路から迂回される。空リスト送信で Webhook 付与済み権利を失効させることも可能。
- **推奨:** クライアント申告をサーバー権限に反映しない。RevenueCat サーバー API 照合または Webhook 保存状態の再読込のみとし、自己申告による付与・失効を拒否する回帰テストを追加する。

### BE-003 — メカ・戦術詳細と戦術シミュレーションに認証・所有権検査がない

- **重大度:** High
- **統合参照:** `02-backend-api.md` BE-003、`08-billing-fairness.md` BF-002
- **file:line:** `src/photo_mecha_battle/api/app.py:403-418,445-450,474-491`; `tests/test_api_errors.py:94-104`
- **影響:** 未認証で他ユーザーのメカ stats・戦術全文を取得でき、simulate で非公開戦術を試行できる。UUID の推測困難性は認可の代替にならない。
- **推奨:** 3 エンドポイントすべてに `require_user` と `user_id` 一致検査を追加する。未認証 401、第三者 403、所有者 200 の契約テストを資源ごとに追加する。

### SEC-002 — 認証トークンの失効・ローテーション機構がない

- **重大度:** Medium
- **file:line:** `src/photo_mecha_battle/api/database.py:150-165`; `docs/07_platform_and_system.md:49-57`
- **影響:** トークン漏えい後も無期限に有効なまま。端末紛失・ログ共有・バックアップ流出時にアカウント乗っ取りを止められない。仕様上も「暫定実装」と明記されているが、本番公開前のブロッカー候補である。
- **推奨:** トークン失効 API、再発行、端末バインド、または β 版までの正式 IdP（Firebase Auth 等）移行計画を `docs/07` に確定する。最低限、ユーザー自身によるトークン無効化を追加する。

### SEC-003 — ユーザー登録にレート制限・濫用防止がない

- **重大度:** Medium
- **file:line:** `src/photo_mecha_battle/api/app.py:227-230`; `src/photo_mecha_battle/api/database.py:150-159`
- **影響:** 認証不要の `POST /auth/register` を反復すると、UUID ユーザーとトークンを無制限に生成できる。DB 肥大化、ランキング汚染、クォータ消費の起点アカウント量産が可能になる。
- **推奨:** IP / デバイス単位のレート制限、同一表示名の連続登録制限、CAPTCHA または招待制を staging/production で検討する。少なくともリバースプロキシ層で `/auth/register` の QPS 上限を設ける。

### SEC-004 — 管理者・Webhook シークレット比較が定数時間でない

- **重大度:** Low
- **file:line:** `src/photo_mecha_battle/api/app.py:69-72,82-85`
- **影響:** `require_admin` と `require_revenuecat_webhook_auth` はプレーン文字列の `==` 比較である。ネットワーク上のタイミング差分から推測される理論リスクは低いが、認証比較のベストプラクティスから外れる。
- **推奨:** `secrets.compare_digest` で比較する。長さ不一致時も一定時間で拒否する実装に統一する。

---

## 2. 所有権

### BE-002 — チームが他ユーザーのメカ・戦術を参照できる

- **重大度:** High
- **統合参照:** `02-backend-api.md` BE-002、`08-billing-fairness.md` BF-002
- **file:line:** `src/photo_mecha_battle/api/app.py:211-224,494-530`; `src/photo_mecha_battle/api/game_store.py:375-441`
- **影響:** 攻撃者が漏えいした `mech_id` / `tactic_id` を自分のチームに設定し、ランク戦で他人の性能・戦術を利用できる。存在しない ID も作成時に受理され、出撃時に 500 になり得る。
- **推奨:** チーム作成・更新で 6 参照すべてについて存在・所有権を保存前に検証する。違反は 403、不存在は 404/422 とする。

### BE-004 — 互換 capture/object API が実ユーザー画像を無認証で処理できる

- **重大度:** High
- **統合参照:** `02-backend-api.md` BE-004、`04-capture-ml.md` CAP-ML-003
- **file:line:** `src/photo_mecha_battle/api/app.py:238-241,270-295`; `tests/test_mvp_capture.py:29-55`
- **影響:** 他ユーザーの `capture_id` を知る第三者が detect / segment / analyze を無認証で実行し、原画像・特徴量を反復取得できる。production 無効化ガードがない。
- **推奨:** persisted capture/object 経路に認証と所有者検査を必須化する。`PMB_ENV=production` では互換ルーターをマウントしない。

### BE-011 — SQLite の参照整合性が実際には有効でない

- **重大度:** Medium
- **統合参照:** `02-backend-api.md` BE-011
- **file:line:** `src/photo_mecha_battle/api/database.py:32-37,42-136,252-298`
- **影響:** `PRAGMA foreign_keys=ON` が未設定のため、宣言済み FK も強制されない。不正参照の孤児行が DB に残り、所有権バイパスや障害調査を困難にする。
- **推奨:** 接続直後に FK を有効化し、teams の mech/tactic 参照列にも FK と index を追加する。

---

## 3. 課金境界

### BF-004 — `CANCELLATION` 受信時に権限を早期失効する

- **重大度:** High
- **統合参照:** `08-billing-fairness.md` BF-004
- **file:line:** `src/photo_mecha_battle/api/game_store.py:511-515,562-565`; `tests/test_revenuecat_webhook.py:55-77`
- **影響:** 自動更新停止した正規購入者が支払済み期間を残して機能を失う。RevenueCat 公式ライフサイクル（`EXPIRATION` で失効）と不一致。
- **推奨:** 通常の `CANCELLATION` では権限を維持し、更新予定状態のみ記録する。`EXPIRATION` で失効する。

### BF-005 — Webhook の順序・有効期限・原子的反映を管理できない

- **重大度:** High
- **統合参照:** `08-billing-fairness.md` BF-005
- **file:line:** `src/photo_mecha_battle/api/database.py:93-98,130-135,405-438`; `src/photo_mecha_battle/api/game_store.py:529-566`
- **影響:** 遅延到着した古い `RENEWAL` が `EXPIRATION` 後に権限を再付与できる。途中 commit 失敗で Entitlement が部分更新される。
- **推奨:** Entitlement ごとに最終イベント時刻・有効期限を保存し、古いイベントを拒否する。Webhook 処理を単一 DB トランザクションにまとめる。

### BF-008 — 購入復元時のユーザー同一性・alias・transfer が未定義

- **重大度:** Medium
- **統合参照:** `08-billing-fairness.md` BF-008
- **file:line:** `src/photo_mecha_battle/api/app.py:717-730`; `src/photo_mecha_battle/api/game_store.py:545-560`
- **影響:** RevenueCat `app_user_id` と内部 UUID が一致しない場合、購入・復元・端末変更で Entitlement が同期されない。`TRANSFER` は無視される。
- **推奨:** 購入前に内部 user ID を RevenueCat App User ID として bind する契約を明文化する。alias / `TRANSFER` 処理または復元時のサーバー再照会を実装する。

### BF-010 — Webhook payload の sandbox/production 環境を検証しない

- **重大度:** Medium
- **統合参照:** `08-billing-fairness.md` BF-010
- **file:line:** `src/photo_mecha_battle/api/app.py:711-730`; `config/revenuecat_pending_setup.json:43-50`
- **影響:** sandbox イベントが production API に届いた場合、テスト購入で本番 Entitlement が付与される。DB 分離だけでは受信時の誤配送を防げない。
- **推奨:** `PMB_ENV` から期待する RevenueCat `environment` を決定し、不一致イベントを拒否する。環境別 webhook URL・secret を分離する。

### TCI-002 — Entitlement 有無による戦闘能力不変の比較テストがない

- **重大度:** High（課金境界の回帰検出）
- **統合参照:** `06-tests-ci.md` TCI-002
- **file:line:** `AGENTS.md:18-22`; `tests/test_phase2.py:416-521`; `src/photo_mecha_battle/api/limits.py:5-31`
- **影響:** 将来 `premium_tactics` 等が戦闘経路へ混入しても CI で Pay to Win 回帰を検出できない。
- **推奨:** 無課金と各 Entitlement 有効状態で同一 seed の BattleResult・戦術スロット制約が一致するパラメータ化テストを追加する。

---

## 4. 画像アップロード・メディア配信

### CAP-ML-001 — 画像成果物が匿名公開され、保持期限もない

- **重大度:** High
- **統合参照:** `04-capture-ml.md` CAP-ML-001
- **file:line:** `src/photo_mecha_battle/api/app.py:29-35`; `src/photo_mecha_battle/api/image_storage.py:7-36`; `src/photo_mecha_battle/api/database.py:99-121`
- **影響:** `/media` が認証なしで `captures` / `crops` / `masks` / `art` 全体を配信する。URL 漏えいで顔・室内写真等が無期限に第三者取得可能になる。
- **推奨:** ユーザー画像は所有者認証付き API または短寿命署名 URL に限定する。`art` 公開と保護配信を分離し、保持期限・削除ジョブを仕様化する。

### CAP-ML-002 — サーバーとモバイルの双方に画像サイズ上限がない

- **重大度:** High
- **統合参照:** `04-capture-ml.md` CAP-ML-002、`02-backend-api.md` BE-010
- **file:line:** `src/photo_mecha_battle/api/app.py:244-254,298-329`; `src/photo_mecha_battle/api/game_store.py:226-233`; `clients/android/app/src/main/kotlin/com/photomecha/battle/ui/CaptureScreen.kt:182-192`
- **影響:** 巨大画像で API プロセスのメモリ・CPU を枯渇させ、他 API の可用性を低下させられる。端末側も高解像度写真で OOM し得る。
- **推奨:** バイト上限・総画素上限・デコード時間制限をサーバーとクライアント双方に設ける。Pillow decompression bomb を明示的エラー化する。

### CAP-ML-004 — RGBA マスク必須仕様に反して RGB crop を受理し、性能入力を操作できる

- **重大度:** High
- **統合参照:** `04-capture-ml.md` CAP-ML-004
- **file:line:** `src/photo_mecha_battle/api/game_store.py:206-310`; `src/photo_mecha_battle/vision/analysis.py`（RGBA 前提の分析）
- **影響:** 背景を含む RGB 画像が受理されると、特徴量・情報量スコアが仕様とずれ、戦闘性能への入力整合が崩れる。意図的な背景混入でスコア操作の余地が生じる。
- **推奨:** crop のアルファチャンネル必須・前景比率下限をサーバーで検証し、RGB のみは 422 で拒否する。

### BE-006 — クォータと phash 重複判定が競合に弱く上限を超過できる

- **重大度:** High
- **統合参照:** `02-backend-api.md` BE-006、`04-capture-ml.md` CAP-ML-006
- **file:line:** `src/photo_mecha_battle/api/game_store.py:221-251,568-576`; `src/photo_mecha_battle/api/capture_pipeline.py:52-72`
- **影響:** 並行リクエストで日次クォータ上限を超過でき、同一画像の重複登録も可能になる。
- **推奨:** 条件付き `UPDATE` またはトランザクション内ロックでクォータ予約する。phash 登録のクリティカルセクションを直列化する。

### CAP-ML-009 — 直登録の永続化が非原子的

- **重大度:** Medium
- **統合参照:** `04-capture-ml.md` CAP-ML-009、`02-backend-api.md` BE-005
- **file:line:** `src/photo_mecha_battle/api/game_store.py:266-310`; `src/photo_mecha_battle/api/image_storage.py:14-31`
- **影響:** 途中失敗で孤児ファイル・孤児 DB 行・クォータ不整合が残り、再試行が重複判定される。
- **推奨:** DB 操作を単一トランザクションにまとめ、ファイルは commit 後に atomic rename する。

### BE-009 — 互換画像 API の不正入力が 4xx ではなく 500 になる

- **重大度:** Medium
- **統合参照:** `02-backend-api.md` BE-009
- **file:line:** `src/photo_mecha_battle/api/app.py:244-267,277-287`; `src/photo_mecha_battle/api/capture_pipeline.py:45-72`
- **影響:** 壊れた画像・不正 bbox が未処理例外となり、エラー詳細の露出や可用性低下につながる。
- **推奨:** 画像 decode 例外を限定捕捉して 400/422 に変換する。bbox validator を direct 経路と共有する。

---

## 5. CORS・Web クライアント

### SEC-005 — CORS 方針が未実装・未文書化

- **重大度:** Low
- **file:line:** `src/photo_mecha_battle/api/app.py:34`（`CORSMiddleware` 未使用）; `web/app.js:37-48`
- **影響:** 現状はミドルウェア未設定のため、ブラウザのクロスオリジン `fetch` は既定で拒否される。`/app` デモは同一オリジン利用のため問題ない。将来別オリジンの管理画面や SPA を載せる際、`allow_origins=["*"]` 等の漫然設定リスクがある。
- **推奨:** `docs/12` に環境別 CORS 許可オリジンを明記する。staging/production では必要最小のオリジンのみ許可し、認証ヘッダー付きリクエストでは `*` を禁止する。

### SEC-007 — Web デモが認証トークンを localStorage に保存する

- **重大度:** Medium
- **file:line:** `web/app.js:24-27,37-39`; `src/photo_mecha_battle/api/app.py:40-42`
- **影響:** `/app` を第三者が閲覧できる環境では、XSS や共有端末から `pmb_token` が読み取られる。モバイルの EncryptedSharedPreferences / Keychain より保護が弱い。
- **推奨:** production では `/app` を配信しない（`docs/12` 方針）。デモ継続時は sessionStorage + CSP、または HttpOnly Cookie ベースのセッションへ移行する。

### SEC-010 — `/app` Web デモが環境ガードなしで常時マウントされる

- **重大度:** Medium
- **file:line:** `src/photo_mecha_battle/api/app.py:40-42`; `docs/12_environments.md:79,101,114-116`
- **影響:** `PMB_WEB_DIR` が存在すれば production でも簡易 Web クライアントと OpenAPI ブラウザが公開される。意図しないデモ UI 露出と localStorage トークン保存が本番に残る。
- **推奨:** `PMB_ENV=production` では `/app` をマウントしない起動ガードを実装する（SEC-001 と一体）。

---

## 6. 秘密情報・環境分離

### SEC-001 — `PMB_ENV=production` 起動ガードが未実装

- **重大度:** Medium
- **統合参照:** `10-security-diff.md` 防御的改善 1、`docs/12_environments.md:107-118,178-179`
- **file:line:** `src/photo_mecha_battle/api/app.py:29-42,62-85`; `docs/12_environments.md:114-116`
- **影響:** 本番で `PMB_ADMIN_TOKEN` が誤設定されても起動時に検出されない。デモ Entitlement API・Web デモ・互換 capture API が有効なまま公開されうる。
- **推奨:** `PMB_ENV=production` 時に (1) `PMB_ADMIN_TOKEN` 設定を起動失敗、(2) `/app` 非マウント、(3) 互換デモルーター無効化、(4) OpenAPI 無効化を強制する。

### SEC-013 — SQLite ファイルのパーミッション硬化が未指定

- **重大度:** Low
- **統合参照:** `10-security-diff.md` 防御的改善 2
- **file:line:** `src/photo_mecha_battle/api/db_path.py`; `src/photo_mecha_battle/api/database.py:33-37`
- **影響:** 共有 Unix ホストでは umask 次第で DB と画像ディレクトリが他ユーザーから読める可能性がある。トークン・課金状態・画像パスが漏える。
- **推奨:** 本番では SQLite と `PMB_DATA_DIR` を `0600` / `0700` 相当に設定する。デプロイ手順を `docs/12` に追記する。

### SEC-014 — Android 開発スクリプトの `--api-url` に検証がない

- **重大度:** Low
- **統合参照:** `10-security-diff.md` 防御的改善 3
- **file:line:** `scripts/android_dev.sh:115-117,148-155`; `clients/android/app/build.gradle.kts:20`
- **影響:** 現状は開発者ローカル用途のためリスクは低い。将来 CI や自動化から信頼できない入力を渡すと、意図しない API エンドポイントへトークンを送信するビルドが生成されうる。
- **推奨:** `--api-url` を `http`/`https` スキームと許可ホストリストで検証する。release ビルドでは CLI 上書きを禁止する。

---

## 7. ログ・監査

### SEC-006 — セキュリティイベントの構造化監査ログがない

- **重大度:** Medium
- **file:line:** `src/photo_mecha_battle/api/app.py`（全体）; `clients/ios/PhotoMechaBattle/Data/TokenStore.swift:55`（Keychain 失敗のみ `NSLog`）
- **影響:** 認証失敗、所有権拒否、Entitlement 変更、Webhook 処理、管理者 API 呼び出し、unsafe_capture 拒否がアプリログに残らない。不正調査・インシデント対応で「いつ・誰が・何を」追跡できない。
- **推奨:** 構造化ログ（JSON）で `event_type`・`user_id`・`request_id`・`result` を記録する。トークン・Authorization ヘッダー本体はマスクする。`PMB_ENV` を全ログに付与する（`docs/12` 想定用途）。

### BE-012 — migration が任意の OperationalError を握り潰す

- **重大度:** Medium
- **統合参照:** `02-backend-api.md` BE-012
- **file:line:** `src/photo_mecha_battle/api/database.py:138-147`
- **影響:** スキーマ不整合が起動時に隠蔽され、本番障害の根本原因が後続リクエストまで遅延する。Error Surfacing 規約にも反する。
- **推奨:** 列存在を事前確認し、必要な ALTER 失敗は cause 付きで起動失敗にする。

---

## 8. CI・品質ゲート

### TCI-001 — Python テストと C0/C1 が CI merge gate になっていない

- **重大度:** High
- **統合参照:** `06-tests-ci.md` TCI-001
- **file:line:** `.github/workflows/android.yml:1-30`; `.github/workflows/ios.yml:1-40`; `pyproject.toml:22-32`
- **影響:** 認可・課金・画像安全性の回帰を含む Python 変更が GitHub Actions 上で検出されない。セキュリティ修正の再発を CI が防げない。
- **推奨:** `python -m pytest` を実行する backend workflow を追加し、PR の required check に設定する。

### TCI-006 — SQLite ResourceWarning が品質ゲートを通過している

- **重大度:** Medium
- **統合参照:** `06-tests-ci.md` TCI-006
- **file:line:** `tests/test_diag_mech_i2i.py:13-33`; `pyproject.toml:22-25`
- **影響:** DB 接続寿命の不備が見逃され、長時間稼働で lock や FD 枯渇につながる。
- **推奨:** 診断テストで connection を明示 close する。CI で `ResourceWarning` を error 化する。

### TCI-007 — モバイル側に静的品質・セキュリティ lint ゲートがない

- **重大度:** Low
- **統合参照:** `06-tests-ci.md` TCI-007
- **file:line:** `clients/android/app/build.gradle.kts:23-27`; `.github/workflows/android.yml:15-30`
- **影響:** Android Lint、依存脆弱性スキャン、ProGuard/R8 警告が CI でブロックされない。
- **推奨:** `./gradlew lint` と依存監査を workflow に追加する。release で `isMinifyEnabled = true` を検討する（SEC-012）。

---

## 9. Android / iOS 設定

### SEC-008 — デモ用バトル作成 API が認証なしで公開される

- **重大度:** High
- **file:line:** `src/photo_mecha_battle/api/app.py:611-639,238-241`; `tests/test_api.py:42-43`
- **影響:** `POST /battles` と `POST /captures`（stub）は誰でも呼べる。production で無効化されないため、CPU 戦ログ生成や in-memory リソース操作の濫用が可能になる（ランキングには直接影響しないが、サーバー負荷とログ汚染）。
- **推奨:** `PMB_ENV=production` ではデモエンドポイントを 404/403 にする。または認証必須に変更する。

### SEC-009 — モバイルクライアントに証明書ピン留めがない

- **重大度:** Low
- **file:line:** `clients/android/core/src/main/kotlin/com/photomecha/core/api/ApiClient.kt:28`; `clients/ios/PhotoMechaCore/Sources/PhotoMechaCore/ApiClient.swift:12-21`; `docs/12_environments.md:76`
- **影響:** 中間者攻撃や悪意ある CA による API 通信改ざんの防御層が TLS のみに依存する。MVP では `docs/12` が任意としているため設計上は許容範囲。
- **推奨:** β 以降で本番 API ホストのピン留めまたは TrustKit / Network Security Config を検討する。staging と production で別ピンを設定する。

### SEC-011 — OpenAPI `/docs` が環境問わず公開される

- **重大度:** Low
- **file:line:** `src/photo_mecha_battle/api/app.py:34`; `scripts/android_dev.sh:76-78`（`/docs` をヘルス確認に使用）
- **影響:** 全エンドポイント一覧・リクエスト形式が公開され、攻撃面の把握が容易になる。認証情報は含まないが、未保護エンドポイントの発見を助ける。
- **推奨:** production では `docs_url=None` / `redoc_url=None` にする。staging も Basic 認証または IP 制限を検討する。

### SEC-012 — Android release ビルドで難読化が無効

- **重大度:** Low
- **file:line:** `clients/android/app/build.gradle.kts:23-27`
- **影響:** APK から API パス・モデル構造の解析が容易になる。秘密情報は EncryptedSharedPreferences にあるため直接露出は限定的。
- **推奨:** ストア提出前に R8/ProGuard を有効化し、release の API URL が HTTPS 本番固定であることをビルド時に検証する。

---

## 10. ランキング・バトル整合性（セキュリティ関連）

### BF-006 — バトル保存・レーティング・キュー更新が非原子的

- **重大度:** High
- **統合参照:** `08-billing-fairness.md` BF-006、`02-backend-api.md` BE-007
- **file:line:** `src/photo_mecha_battle/api/app.py:572-608`; `src/photo_mecha_battle/api/game_store.py:470-499`
- **影響:** 途中障害でレーティング不整合・キュー残留が起き、再送で二重レーティング変動が可能になる。
- **推奨:** バトル結果・双方 rating・dequeue を単一トランザクションで確定する。idempotency key を導入する。

### BF-007 — CPU フォールバックを無制限に繰り返してランキングを増やせる

- **重大度:** High
- **統合参照:** `08-billing-fairness.md` BF-007
- **file:line:** `src/photo_mecha_battle/api/app.py:572-608`; `tests/test_phase2.py:324-333`
- **影響:** CPU 戦の反復でレーティングを人為的に上げ、ランキングの信頼性を損なう。BF-001 のクォータ拡大と組み合わさると優位が増幅する。
- **推奨:** CPU 戦をグローバル PvP レーティング対象外にするか、match ticket・回数制限を導入する。

---

## 正常確認点

1. **`X-User-Token` の欠落・無効は 401 に統一:** `require_user` が保護済み API で一貫して動作する（`app.py:49-59`、`tests/test_phase2.py:319-321`）。
2. **ランク戦 seed はサーバー生成:** クライアント送信 seed は無視され、`secrets.randbits` で生成される（`game_store.py:449-470`、`tests/test_phase2.py:153-181`）。
3. **ランク戦バトルログは当事者のみ:** `GET /battles/{id}` は対人戦で player_a/b のみ、CPU 戦で player_a のみ（`app.py:642-658`、`tests/test_phase2.py:336-385`）。
4. **`POST /mechs` の object 所有権:** アップロード由来 object は所有者のみ使用可（`app.py:386-391`）。
5. **direct `/mechs` の改ざん検知:** feature 再計算・algo_version・bbox・unsafe・phash・最小解像度をサーバーが検証する（`game_store.py:206-310`、`tests/test_mech_direct_registration.py`）。
6. **戦闘性能はクライアント stats に依存しない:** form・stats はサーバー推定（`app.py:101-118,370-395`）。
7. **Entitlement による戦術スロット拡張なし:** ランク戦の条件・行動・スロット数に課金分岐はない（`limits.py:5-31`、`tactics.py:107-122`）。
8. **管理者 API・Webhook は fail-closed:** `PMB_ADMIN_TOKEN` / `PMB_REVENUECAT_WEBHOOK_SECRET` 未設定時は常に拒否（`app.py:62-85`、`tests/test_revenuecat_webhook.py:251-262`）。
9. **既知 Entitlement キーのみ受理:** 未知キーは admin API・Webhook・sync でフィルタされる（`game_store.py:503-509`）。
10. **Android トークンは EncryptedSharedPreferences:** `allowBackup=false`、cleartext は debug manifest のみ（`TokenStore.kt:7-16`、`AndroidManifest.xml:8,12`、`debug/AndroidManifest.xml:5-8`）。
11. **iOS トークンは Keychain（AfterFirstUnlockThisDeviceOnly）:** 書込失敗は `NSLog` + throw（`TokenStore.swift:18-57`）。
12. **iOS ATS はローカルネットワーク許可のみ:** `NSAllowsArbitraryLoads` は未設定（`Info.plist:19-24`）。
13. **リポジトリにハードコードされた本番秘密情報なし:** テスト用固定値は `tests/conftest.py:16-20` に限定。RevenueCat 設定は `config/revenuecat_pending_setup.json` で外部作業として追跡。
14. **差分レビューでリモート悪用可能な新規 Medium+ は未確認:** `10-security-diff.md` のブランチ差分について、HTTP 経由の新規攻撃経路は見つかっていない。

---

## 推奨対応順序

1. **公開前ブロッカー:** BF-001、BE-002、BE-003、BE-004、CAP-ML-001、SEC-001、SEC-008、SEC-010
2. **課金・ランキング整合性:** BF-004、BF-005、BF-006、BF-007、BF-010
3. **可用性・入力防御:** CAP-ML-002、BE-006、BE-009、SEC-003
4. **環境硬化・運用:** SEC-006、SEC-007、SEC-011、TCI-001、SEC-013
5. **β 以降:** SEC-002、SEC-009、BF-008、SEC-012

## 判定サマリー

| 重大度 | 件数 |
|---|---:|
| Critical | 1 |
| High | 12 |
| Medium | 13 |
| Low | 6 |
| **合計** | **32** |
