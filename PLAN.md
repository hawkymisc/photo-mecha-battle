# Development Plan

## Phase 1 — Vertical Slice Prototype

| Status | ID | Task | Notes |
|---|---|---|---|
| ✅ | P1-001 | Battle engine (deterministic, seed-based) | [`src/photo_mecha_battle/battle.py`](src/photo_mecha_battle/battle.py) |
| ✅ | P1-002 | Tactics DSL + 5 presets | [`src/photo_mecha_battle/tactics.py`](src/photo_mecha_battle/tactics.py) |
| ✅ | P1-003 | Reproducibility tests | [`tests/test_battle.py`](tests/test_battle.py) |
| ✅ | P1-004 | Mech stats from feature vector | [`src/photo_mecha_battle/mech_stats.py`](src/photo_mecha_battle/mech_stats.py) |
| ✅ | P1-005 | FastAPI stub endpoints | [`src/photo_mecha_battle/api/app.py`](src/photo_mecha_battle/api/app.py) |
| ✅ | P1-006 | CLI vertical slice demo | [`scripts/vertical_slice.py`](scripts/vertical_slice.py) |

## Phase 2 — MVP

| Status | ID | Task | Notes |
|---|---|---|---|
| ✅ | P2-001 | User auth | `POST /auth/register`, `X-User-Token` |
| ✅ | P2-002 | Mech persistence | SQLite via [`api/database.py`](src/photo_mecha_battle/api/database.py) |
| ✅ | P2-003 | Tactic slot editor | `POST/PUT /tactics`, catalog |
| ✅ | P2-004 | Async PvP matchmaking | `POST /battles/match`, ranked queue |
| ✅ | P2-005 | Ranking | 固定デルタ方式 (+25/−15 等、[docs/05](docs/05_team_and_battle.md))、`GET /ranking` |
| ⚠️ | P2-006 | RevenueCat integration | `/billing/revenuecat/webhook`（実装詳細は D-005）。外部設定待ちのため実店舗連携は未完了 |

## Phase 2.5 — MVP Capture Pipeline

| Status | ID | Task | Notes |
|---|---|---|---|
| ✅ | P25-001 | Photo upload API | `POST /captures/upload` (multipart) |
| ✅ | P25-002 | PIL feature extraction | [`vision/analysis.py`](src/photo_mecha_battle/vision/analysis.py) |
| ✅ | P25-003 | Detection + segmentation | [`vision/detection.py`](src/photo_mecha_battle/vision/detection.py), [`vision/segmentation.py`](src/photo_mecha_battle/vision/segmentation.py) |
| ✅ | P25-004 | Mech art generation (cosmetic) | [`vision/mech_art.py`](src/photo_mecha_battle/vision/mech_art.py), `art_url` on mechs |
| ✅ | P25-005 | Generation quotas | `GET /users/quotas`, daily limits |
| ✅ | P25-006 | Duplicate capture guard | perceptual hash + hamming distance |
| 🔲 | P25-007 | Mobile client (iOS/Android) | out of scope for backend MVP |
| ✅ | P25-008 | 動作確認用の簡易Webクライアント | [`web/`](web/)（`GET /app/` で配信）。撮影アップロード→検出→抽出→メカ生成→編成→CPU戦バトル→ログ確認→ランキングの一気通貫ループをブラウザで試せる、バックエンドAPIの薄いフロントエンド。**P25-007（本番モバイルクライアント）の代替ではない**。認証・演出・戦闘計算はすべて既存APIに委譲し、クライアント側は何も判定しない（docs/09 信頼モデル） |

## Phase D — 仕様精緻化・実装整合（2026-07-02 監査で発見）

<!-- CODEX_REVIEWED -->

[docs/00](docs/00_root_overview.md)〜09 の精緻化（実装値の還流、07/09 一本化、未実装概念の隔離）に伴い発見した実装乖離。
仕様の正本判断: バトル数値・クォータ = 実装正、プリセット定義・課金境界 = 仕様正。

優先順位: D-004 / D-005 は**課金フローを本番に出す前のリリースブロッカー**。
D-002 はバトルバランス検証の前提。D-003 はクライアントのバトル演出実装の前提。

| Status | ID | Task | 正本 | 受入基準・テスト |
|---|---|---|---|---|
| ✅ | D-001 | [docs/02](docs/02_photo_object_extraction.md)〜09・README・AGENTS の精緻化 | — | 実装値還流、07 を 09 へ一本化、確定状態注記 |
| ✅ | D-002 | 砲台型プリセットの shadowing 修正 | [docs/04](docs/04_tactics.md) 砲台型 | 「自分HPが70%以下→通常砲撃」スロットを削除し docs/04 の3スロット構成（迎撃・防御・重砲撃 + 基本行動）に統一。`_choose_action` 直接呼び出しで HP≤30% 時に防御が到達することを検証、他4プリセットのスロット数が不変であることもテストで確認（[`tests/test_tactics.py`](tests/test_tactics.py)、[`tests/test_battle_extended.py`](tests/test_battle_extended.py)）。※ Issue #1 |
| ✅ | D-003 | バトルログの構造化 JSON 保存 | [docs/05](docs/05_team_and_battle.md) ログエントリ構造 | 新カラム `battles.log_json` に構造化ログを保存し `GET /battles/{id}` の `log_entries` として返却（[`battle_log_serde.py`](src/photo_mecha_battle/battle_log_serde.py)）。既存 DB は `ALTER TABLE` マイグレーションで追加、`log_json` が無い/NULL の行は `log_entries: null` で `log` にフォールバック。ラウンドトリップ・DB・API 各層でテスト（[`tests/test_battle_log_serde.py`](tests/test_battle_log_serde.py) 等）。※ Issue #2 |
| ✅ | D-004 | `POST /billing/entitlements` の管理者制限 | [docs/06](docs/06_monetization_and_fairness.md) デモ用 API の扱い | `X-Admin-Token`（`PMB_ADMIN_TOKEN` 環境変数と照合）を必須化。未設定環境では常に 403 でエンドポイントを事実上無効化。管理者トークン無し・誤りの双方を認可テストで検証（[`tests/test_phase2.py`](tests/test_phase2.py)）。※ Issue #3 |
| ⚠️ | D-005 | Webhook の Entitlement 個別付与 | [docs/06](docs/06_monetization_and_fairness.md) Webhook イベント処理 | 実装済み: イベントの `entitlement_ids` に基づく個別付与/失効（商品IDのハードコード対応表は廃止）、`event.id` による冪等性チェック、`Authorization` ヘッダーによる Webhook 認証（未設定時は401で無効化）。イベント種別×entitlement_ids のマトリクステスト（[`tests/test_revenuecat_webhook.py`](tests/test_revenuecat_webhook.py)）。**残課題（外部設定・コード対応不可）**: RevenueCat ダッシュボードでの商品定義・Entitlement 紐付け確定、Webhook 共有シークレットの発行。[`config/revenuecat_pending_setup.json`](config/revenuecat_pending_setup.json) に追跡事項を切り出し済み。※ Issue #4 |
| ⛔ | D-006 | `disrupt` の能力低下効果 | [docs/04](docs/04_tactics.md) 行動候補注記 | **blocked**: 先に状態異常システムを [docs/08](docs/08_mvp_and_roadmap.md)→[docs/05](docs/05_team_and_battle.md) で設計してから着手。部分実装しない。受入基準（暫定挙動）: `disrupt` は決定的な低威力攻撃 (威力 0.4) のままであること（[`tests/test_battle_extended.py`](tests/test_battle_extended.py) で回帰固定済み）。設計判断は [`config/po_pending_decisions.json`](config/po_pending_decisions.json) の `disrupt_status_effect_design` で追跡 |
| ✅ | D-007 | ランク戦 seed のサーバー生成 | [docs/09](docs/09_lightweight_server_architecture.md) 信頼モデル | `POST /battles/ranked` はクライアント送信 seed を無視し（後方互換のため 400 にはしない）、`GameStore.generate_battle_seed`（`secrets.randbits`）でサーバーが生成した seed を `battles.seed` に保存する。レスポンスの `seed` は演出再生用に返却。エンジン直呼びの再現性テストは維持（[`tests/test_battle.py`](tests/test_battle.py)）。※ Issue #5 |
| ✅ | D-008 | `GET /battles/{id}` の参照権限 | [docs/07](docs/07_platform_and_system.md) 所有権 | 対戦当事者 (player_a / player_b) のみ参照可、未認証は 401、第三者は 403。CPU 戦は player_a のみ。所有者のないデモ戦（`POST /battles`）は認証済みなら誰でも閲覧可。認可テストをマトリクスで追加（[`tests/test_phase2.py`](tests/test_phase2.py)）。副次修正: `X-User-Token` 欠落時のレスポンスを 422→401 に統一（docs/07 API 共通規約）。※ Issue #6 |
| 🔲 | D-009 | 顔検出ヒューリスティックが風景写真を誤検出 | [docs/02](docs/02_photo_object_extraction.md) 顔・個人情報検出（本来 🔲 将来） | **要トリアージ**: `detect_face_like_region`（[`vision/analysis.py`](src/photo_mecha_battle/vision/analysis.py)）の肌色ヒューリスティックが、暖色系の自然テクスチャ（砂浜・木材・紅葉・夕焼け等）を高頻度で誤検出し撮影を`blocked`にする。決定的判定のため`action:"recapture"`案内も無意味。docs/02では本来MVP範囲外（β公開前必須）の項目が既に有効化されている。短期対応（無効化/warning格下げ）か恒久対応（閾値見直し・実モデル化）かの意思決定が必要。実写風景のfalse positive回帰テストが未整備。※ Issue #21 |

※ ランク戦のレーティング確定は `POST /battles/ranked`（サーバー権威）でのみ行う。デルタ値・引き分け・
ランキング応答形は [docs/05](docs/05_team_and_battle.md) を正とし、クライアントから勝敗・デルタを受け取らない (docs/09 信頼モデル)。

## PO 意思決定待ち事項

コードでは解決できず PO の意思決定・外部設定を要する項目は、下記の2ファイルに一元管理する。
決定が下りた時点で該当ドキュメントと本 PLAN を更新し、実装タスクを起票する。

- [`config/po_pending_decisions.json`](config/po_pending_decisions.json): バトル・画像生成・戦術生成・課金の未決事項（[docs/08](docs/08_mvp_and_roadmap.md#未決事項) 対応）
- [`config/revenuecat_pending_setup.json`](config/revenuecat_pending_setup.json): RevenueCat ダッシュボード側の外部設定（D-005 の残課題）
