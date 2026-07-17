# 仕様横断監査レポート（2026-07-15）

## 監査の目的と範囲

Photo Mecha Battle の仕様体系と現行実装を横断し、文書間矛盾、追記残骸、実装乖離（仕様のどちら側でもない第三形態）、宙吊り要件、検証不能基準、未定義参照、単位・値の不一致、意味の二義性を確認した。

- 対象仕様: `docs/00_root_overview.md`〜`docs/12_environments.md`
- 対象ルート文書: `README.md`、`AGENTS.md`、`CLAUDE.md`
- 裏取り対象: Python バックエンド・バトルエンジン・画像処理、Android/iOS クライアント、テスト、CI、設定ファイル、`PLAN.md`
- 方針: 指摘のみ。既存仕様・実装は変更していない
- 外部サイトに依存する `docs/10` のモデル性能・ライセンス記述は、リポジトリ内の整合性のみを監査し、外部一次情報の再調査は本監査に含めない

## 監査カバレッジ

### 文書セクション読了チェック

- [x] `docs/00_root_overview.md`: 目的、ゲーム概要、コア体験、基本構造、仕様書構成、重要設計原則、対象プラットフォーム、MVP 基本方針、ハッカソン前提
- [x] `docs/01_game_concept_and_loop.md`: 目的、コンセプト、プレイヤー体験、基本ゲームループ、初心者/中級者/課金ユーザー、ゲームの基本単位、MVP コアループ
- [x] `docs/02_photo_object_extraction.md`: 入力、撮影、検出、手動補助、セグメント、後処理、品質、安全・不正、出力、phash/品質/スタブ確定値
- [x] `docs/03_mech_generation_and_stats.md`: 入力、3 型、`form_inference/1.0` 全小節、11 次元特徴量、情報量、全ステータス式、画像生成、原則、将来拡張
- [x] `docs/04_tactics.md`: DSL 構造、先勝ち評価、全条件、全行動、5 プリセット全定義、編集形式、自然言語変換
- [x] `docs/05_team_and_battle.md`: 編成、位置、対象、傾向/弱点、ターン、行動順、EN、ダメージ、特効、型相性、戦術評価、公開情報、ログ、レーティング、ランキング
- [x] `docs/06_monetization_and_fairness.md`: 課金境界、クォータ、LLM 判断基準、RevenueCat、Entitlement、Webhook、商品案、Paywall、デモ API
- [x] `docs/07_platform_and_system.md`: プラットフォーム、UX、クライアント候補、認証、API 共通規約、所有権、全データモデル、RevenueCat
- [x] `docs/08_mvp_and_roadmap.md`: MVP 内外、Phase 0〜4、全リスク、確定事項、全未決事項、RevenueCat 必須項目/デモ/検証/リスク
- [x] `docs/09_lightweight_server_architecture.md`: 原則、構成、全責務、信頼モデル、全データフロー、全 API、クライアント/サーバー指針、保存、i2i、安全性、移行、テスト、参照
- [x] `docs/10_mobile_image_generation_survey.md`: 結論、要件、全候補、比較、クロスプラットフォーム、tier、LoRA 手順、Phase 0 計画、PO 判断待ち、履歴
- [x] `docs/11_mobile_client_design.md`: 技術スタック、S00〜S08、全遷移/エラー、MVVM、API、features/1.0、選択処理、テスト、非対象
- [x] `docs/12_environments.md`: 捨てた案、3 環境、全責務、構成マトリクス、設定、データ分離、デプロイ、フェーズ、実装差分、将来、E-001〜E-005
- [x] `README.md`: 全セクション
- [x] `AGENTS.md`: 全セクション
- [x] `CLAUDE.md`: 全セクション

### 実装裏取り

- [x] 数値: ステータス基礎値/加算/キャップ、型推定、情報量重み、ダメージ、位置、EN、行動、クォータ、phash、特徴量許容差、ランキング
- [x] API: 全 FastAPI ルート、認証依存、主要 request/response モデル、課金同期、Webhook、メカ直登録
- [x] 形式: SQLite スキーマ、戦術 JSON、構造化ログ、RGBA 正規形、モバイル Codable/Serializable モデル
- [x] クライアント: Android/iOS の API URL、トークン保存、編成、ログ再生、依存関係、CI
- [x] 計画: `PLAN.md` と `config/po_pending_decisions.json` / `config/revenuecat_pending_setup.json` の追跡関係

## 総括

総 finding 数は **18 件**。

| 重大度 | 件数 |
|---|---:|
| Critical | 1 |
| High | 6 |
| Medium | 8 |
| Low | 3 |

最も強い分布は「仕様の原則は正しいが、互換・デモ・暫定経路が原則を迂回する」形である。特に課金同期、デモ Web 配信、所有権、戦術 fallback に、通常経路とは異なる第三形態が残っている。次に、2026-07-02 以降の実装還流が `docs/05`・`06`・`09` には反映された一方、`docs/02`・`07`・README/AGENTS の索引や状態説明に追記残骸が残っている。

## Findings

### SPEC-001 — クライアント申告だけで有料 Entitlement を自己付与できる

- **重大度**: Critical
- **分類**: 実装乖離（第三形態） / 文書間矛盾 / 認可境界
- **文書引用**
  - `docs/06_monetization_and_fairness.md:185-186`: 「バックエンドは RevenueCat Webhook を受け取り…」「課金状態はクライアントのみを信用せず、サーバー側でも検証・保持する」
  - `docs/07_platform_and_system.md:201-204`: 「Webhook 受信 → user_entitlements 同期。クライアントだけで課金状態を確定しない」
  - `docs/09_lightweight_server_architecture.md:78-80`: 課金の最終判定は Webhook + サーバー Entitlement
- **実装根拠**
  - `src/photo_mecha_battle/api/app.py:702-708`: 認証済みユーザーの `POST /billing/sync` が `active_entitlements` をそのまま同期処理へ渡す
  - `src/photo_mecha_battle/api/game_store.py:517-527`: 既知キーであることだけを確認し、クライアント申告を DB の有効状態へ直接反映する
  - `src/photo_mecha_battle/api/limits.py:24-31`: `generation_boost` が有効ならクォータを 20/10 から 50/30 に拡大する
  - `tests/test_phase2.py:515-521`: 一般ユーザーが `/billing/sync` に `generation_boost` を送るだけで premium クォータになる挙動を回帰固定している
- **影響**
  - 購入や RevenueCat 検証なしで有料機能を解放できる。戦闘能力そのものではないが、課金権限・生成コスト・収益境界のサーバー権威が破られる。
  - `docs/08:286` の「Webhook が間に合わない場合は CustomerInfo 判定を優先」という古いリスク対策が、未検証の自己申告同期として実装された可能性が高い。
- **推奨**
  - `/billing/sync` を「クライアントが active key 一覧を送る API」にしない。サーバーが RevenueCat Subscriber API 等から `app_user_id` の CustomerInfo を取得・検証する再同期 API に変更する。
  - 外部検証が未実装の間は fail-closed で 503/未提供とし、デモ付与は既存の管理者トークン経路だけに限定する。

### SPEC-002 — production で未設定時に `/app` が配信される fail-open

- **重大度**: High
- **分類**: 実装乖離（第三形態） / 環境・セキュリティ
- **文書引用**
  - `docs/12_environments.md:77-79`: production の Web デモ `/app/` は「配信しない」
  - `docs/12_environments.md:95-103`: 未設定時は fail-closed、production の `PMB_WEB_DIR` は未設定でマウントしない
- **実装根拠**
  - `src/photo_mecha_battle/api/app.py:37-42`: `PMB_WEB_DIR` 未設定時にリポジトリの `web/` を既定値にし、存在すれば `/app` をマウントする
  - `src/photo_mecha_battle/api/app.py:29-42`: `PMB_ENV` による production 判定も存在しない
- **影響**
  - 文書が「未設定 = 非配信」と定義しているのに、実装は「未設定 = 自動配信」である。production のパッケージに `web/` が含まれる構成では、デモ UI が意図せず公開される。
- **推奨**
  - `PMB_WEB_DIR` が明示された場合だけマウントする opt-in にする。
  - `PMB_ENV=production` では `PMB_WEB_DIR` 設定自体を起動エラーにする E-011 を production 公開前ゲートへ昇格する。

### SPEC-003 — mech/tactic の読取・simulate・チーム参照で所有権が統一されていない

- **重大度**: High
- **分類**: 実装乖離 / API 認可 / 意味の二義性
- **文書引用**
  - `docs/07_platform_and_system.md:75-80`: 戦術・チームはユーザーに紐づき、他ユーザーのリソース参照・更新・出撃を拒否する所有権方針
  - `docs/05_team_and_battle.md:193-195`: 相手の非公開戦術・seed・次行動は参照不可
- **実装根拠**
  - `src/photo_mecha_battle/api/app.py:403-418`: `GET /mechs/{id}` は認証・所有者確認なし
  - `src/photo_mecha_battle/api/app.py:445-450`: `GET /tactics/{id}` は認証・所有者確認なしで payload 全体を返す
  - `src/photo_mecha_battle/api/app.py:474-485`: tactic simulate も認証・所有者確認なし
  - `src/photo_mecha_battle/api/app.py:494-499` と `src/photo_mecha_battle/api/game_store.py:375-398`: チーム作成時、slot の mech/tactic が本人所有か検証せず ID を保存する
- **影響**
  - UUID が別経路から漏れた場合、他ユーザーの非公開戦術全文を取得・simulate でき、他ユーザーの mech/tactic を自分のチームに組み込める。
  - 文書の「他ユーザーのチーム参照」の意味が「team 行だけ」か「team が参照する全リソース」か曖昧で、実装は前者に狭く解釈している。
- **推奨**
  - private-by-default を明文化し、mech/tactic/team の GET・更新・simulate・編成参照すべてに本人所有チェックを適用する。
  - 将来公開したいメカ情報は private endpoint の例外ではなく、公開用 DTO/endpoint を別に設計する。

### SPEC-004 — EN 不足の有料 fallback が無料で実行される

- **重大度**: High
- **分類**: 意味の二義性 / 実装乖離（第三形態） / バトル公平性
- **文書引用**
  - `docs/04_tactics.md:26-38`: fallback は全スロット不成立時に必ず実行、EN を払えない行動は次スロットへ
  - `docs/04_tactics.md:89`: 「EN コストを支払えない行動は選択されない」
  - `docs/05_team_and_battle.md:111`: EN がコストに満たない行動は選択不可
  - `docs/05_team_and_battle.md:180-181`: 解決時 EN 不足なら fallback へ退避
- **実装根拠**
  - `src/photo_mecha_battle/api/app.py:141-144`: `fallback_action` は全 `ActionType` を許容し、ゼロコスト制約がない
  - `src/photo_mecha_battle/battle.py:207-212`: EN 不足を検知して同じ fallback へ置換するだけで、fallback 自身の支払可否を再拒否しない
  - `src/photo_mecha_battle/battle.py:253-270`: その fallback を解決後、`_spend_en` が 0 未満を 0 に丸めるため、不足分を払わず攻撃できる
  - `tests/test_battle_extended.py:111-124`: EN 5 でコスト 30 の `high_power_attack` を fallback にしたケースを許容し、「EN不足」ログだけを確認している
- **影響**
  - カスタム戦術で高コスト行動を fallback に置くと、EN を無視して毎ターン実行できる。課金差ではないが、ランク戦の戦術公平性を直接壊す。
- **推奨**
  - 推奨 A: fallback を EN 0 の基本行動だけに制約する（単純で UI 説明とも一致）。
  - 代替 B: fallback も払えない場合は `normal_attack` へ二段退避する。いずれを採るか仕様化し、API バリデーションとエンジンテストを同時に固定する。

### SPEC-005 — QR/ノイズの `info_score` cap が MechStats に反映されない二重定義

- **重大度**: High
- **分類**: 実装乖離（第三形態） / 単位・値の不一致 / 公平性
- **文書引用**
  - `docs/03_mech_generation_and_stats.md:181-193`: ObjectInfoScore は一意の加重和であり EN/LUCK に反映
  - `docs/03_mech_generation_and_stats.md:219-228`: `info_score` を EN と LUCK の式に使用
  - `docs/02_photo_object_extraction.md:96-97`: ノイズ/QR 対策は将来
- **実装根拠**
  - `src/photo_mecha_battle/api/capture_pipeline.py:23-27`: QR/ノイズの表示・保存用 `info_score` に独自 cap `0.35`
  - `src/photo_mecha_battle/api/game_store.py:262-264,288-309`: cap 後の値を DB と API 応答に保存・返却
  - `src/photo_mecha_battle/api/store.py:75-81`: メカ生成は ObjectRecord の capped `info_score` を使わず features から構築
  - `src/photo_mecha_battle/mech_stats.py:89-99`: MechStats は features から uncapped `info_score` を再計算して EN/LUCK に使用
- **影響**
  - API が「確定値」と返す `info_score <= 0.35` と、実際にステータスへ反映された内部 info score が異なる。
  - プレイヤー説明・不正対策・テストが「スコアを制限した」ように見える一方、戦闘性能側の EN/LUCK は制限されない。
- **推奨**
  - `compute_info_score` の唯一の確定値を作り、その値を `derive_stats` に引数で渡すか、ペナルティ込み Feature/ScorePolicy を仕様化する。
  - cap を見た目/説明だけに使うなら `display_info_score` 等へ改名し、戦闘性能に影響しないことを明記する。

### SPEC-006 — RevenueCat の必須クライアント要件が実装・タスク境界から宙吊り

- **重大度**: High
- **分類**: 宙吊り要件 / 実装乖離
- **文書引用**
  - `docs/00_root_overview.md:100-112`: RevenueCat はハッカソン必須条件
  - `docs/06_monetization_and_fairness.md:178-186`: iOS/Android SDK、Offerings、CustomerInfo、購入、購入復元、Webhook を必須化
  - `docs/08_mvp_and_roadmap.md:248-258`: 同じ項目を MVP 必須として列挙
  - `docs/11_mobile_client_design.md:153-157`: Phase 1 では RevenueCat SDK/Paywall を外部設定後まで実装しない
- **実装根拠**
  - `clients/android/app/build.gradle.kts:44-67`: RevenueCat SDK 依存がない
  - `clients/ios/project.yml:7-24`: RevenueCat package 依存がない
  - リポジトリの Swift/Kotlin/Gradle 全体に `Purchases` / RevenueCat SDK 呼び出しがない
  - `PLAN.md:31-34`: P2-006 は webhook と外部設定待ちだけを記載し、クライアント SDK/Paywall/購入/復元の個別残タスクと受入基準がない
- **影響**
  - バックエンド webhook が完成しても、購入・復元・CustomerInfo のユーザ導線は成立しない。必須要件が「外部設定待ち」に吸収され、コード残作業が見えない。
- **推奨**
  - iOS SDK、Android SDK、Offerings/Paywall、sandbox 購入、復元、App User ID 紐付けを独立タスク化し、P2-006 をサーバー連携とクライアント購入導線に分割する。

### SPEC-007 — release クライアントにも local/cleartext API URL が既定で埋め込まれる

- **重大度**: High
- **分類**: 実装乖離 / 環境設定
- **文書引用**
  - `docs/12_environments.md:75-76`: production release は本番 API URL 固定、TLS 必須
  - `docs/12_environments.md:120-125`: release に local IP / cleartext を埋め込まない
- **実装根拠**
  - `clients/android/app/build.gradle.kts:12-26`: 全 build type 共通の既定値が `http://10.0.2.2:8000`。release override や未設定時 fail がない
  - `clients/android/app/src/main/AndroidManifest.xml:8-13`: release は cleartext を許可しないため、既定 release は接続不能
  - `clients/ios/PhotoMechaBattle/PhotoMechaBattleApp.swift:25-31`: 環境変数未設定時の既定値が `http://127.0.0.1:8000`
  - `clients/ios/project.yml:18-24`: release/configuration 別 API URL 設定がない
- **影響**
  - URL 注入を忘れた release は Android では cleartext 拒否、iOS では端末自身の localhost 接続となり、起動は成功しても API が使えない。
- **推奨**
  - release は HTTPS URL の必須ビルド設定にし、未指定ならコンパイル/CI を失敗させる。local 既定値は debug configuration だけに置く。

### SPEC-008 — 「将来」扱いの顔・QR・ノイズ判定が既に本経路で有効

- **重大度**: Medium
- **分類**: 文書間矛盾 / 追記残骸 / 実装乖離
- **文書引用**
  - `docs/02_photo_object_extraction.md:91-101`: MVP 実装済みは phash・クォータ・明るさ/ブレで、ノイズ/QR/顔は「将来」
  - `docs/11_mobile_client_design.md:69-74`: 一方で現行 UI 契約は `face_detected` を 422 理由として扱う
- **実装根拠**
  - `src/photo_mecha_battle/vision/analysis.py:181-238`: face-like 判定を実装
  - `src/photo_mecha_battle/vision/analysis.py:241-307`: QR/ノイズ判定を実装し、顔は blocked、QR/ノイズは warning
  - `src/photo_mecha_battle/api/game_store.py:253-264`: メカ直登録の本経路で判定を実行
  - `PLAN.md:68`: D-009 で face-like の風景誤検出を既知問題として記録済み
- **影響**
  - docs/02 だけを読んだ実装者・テスターは有効な拒否/警告条件を把握できない。顔ヒューリスティックの false positive はユーザーの撮影をブロックする。
- **推奨**
  - 短期は有効/無効を feature flag と環境別方針で明示する。継続するなら docs/02 の実装状態・閾値・誤検出許容・UI 導線を現行実装へ更新する。

### SPEC-009 — 旧 `log_json=NULL` の text fallback をモバイルが実装していない

- **重大度**: Medium
- **分類**: API 形式乖離 / 後方互換要件の宙吊り
- **文書引用**
  - `docs/05_team_and_battle.md:219-222`: 旧行は `log_entries: null`、呼び出し側は `log` にフォールバックする
- **実装根拠**
  - `src/photo_mecha_battle/api/database.py:380-396`: 仕様どおり旧行に `log_entries=None` を返す
  - `clients/android/core/src/main/kotlin/com/photomecha/core/api/ApiModels.kt:105-113`: `logEntries` は非 nullable。JSON の明示的 `null` は default 値では吸収できない
  - `clients/ios/PhotoMechaCore/Sources/PhotoMechaCore/ApiModels.swift:192-214`: null を空配列にはするが、`log` fallback の表示モデルを作らない
  - `clients/android/app/src/main/kotlin/com/photomecha/battle/ui/BattleScreen.kt:57-92`、`clients/ios/PhotoMechaBattle/Views/BattleView.swift:29-49`: どちらも構造化 entries のみ表示
- **影響**
  - Android は旧バトル取得の decode に失敗し、iOS は空ログとして表示する。DB マイグレーション互換性をサーバーだけが実装している。
- **推奨**
  - `logEntries` を nullable/optional とし、null または空で `log` を text 表示する契約テストを両クライアントへ追加する。

### SPEC-010 — docs/07 の「現行実装と同期」がログ/Webhook 実装に追従していない

- **重大度**: Medium
- **分類**: 追記残骸 / 文書間矛盾
- **文書引用**
  - `docs/07_platform_and_system.md:9-12,82-85`: データモデルは現行 SQLite と同期済みと宣言
  - `docs/07_platform_and_system.md:160-173`: battles は `log_text` のみを列挙し、「構造化 JSON へ移行予定。現行は整形テキスト」
  - `docs/07_platform_and_system.md:183-184`: Webhook 本実装を Phase 3 の将来扱い
  - `docs/05_team_and_battle.md:219-222` と `docs/06_monetization_and_fairness.md:141-149`: いずれも実装済みと記載
- **実装根拠**
  - `src/photo_mecha_battle/api/database.py:80-98,130-147`: `log_json` と `processed_webhook_events` が現行スキーマに存在
  - `src/photo_mecha_battle/api/database.py:341-396`: 構造化ログを保存・返却
  - `src/photo_mecha_battle/api/game_store.py:529-566`: Webhook の個別付与・冪等処理を実装
- **影響**
  - 「現行同期済み」という強い宣言が誤りで、DB 移行・API クライアント・運用判断の基準を誤らせる。
- **推奨**
  - docs/07 の現行スキーマ表に `log_json` / `processed_webhook_events` を反映し、将来注記を削除する。購入詳細列が未実装である点とは分離する。

### SPEC-011 — 戦術条件 threshold の型・範囲・必須性が未定義かつ未検証

- **重大度**: Medium
- **分類**: 未定義参照 / 検証不能基準 / API 形式
- **文書引用**
  - `docs/04_tactics.md:62-75`: N を「パーセント」「EN 値」「体数」とだけ定義し、範囲・整数性・必須/禁止を定義しない
  - `docs/04_tactics.md:202-205`: 条件・行動は確定表から選び、JSON はサーバー正本
- **実装根拠**
  - `src/photo_mecha_battle/api/app.py:135-144`: threshold は `str | int | float | None` を全条件共通で受理する
  - `src/photo_mecha_battle/api/app.py:195-208`: condition kind ごとの必須性・範囲検証なし
  - `src/photo_mecha_battle/battle.py:309-326`: 実行時に `float(threshold)` / `int(threshold)` へ変換するため、`None` や不正文字列はバトル時例外になる
- **影響**
  - 無効戦術を保存時に受理し、ランク戦実行時に 500 相当の障害へ遅延させる。HP 999%、敵数 -1 など意味のない条件も保存できる。
- **推奨**
  - condition ごとに schema を分け、HP は整数 0〜100、EN は 0〜200、敵数は 1〜3、`target_form` は 3 enum、固定/always 条件は threshold 禁止と定義・検証する。

### SPEC-012 — `form_inference_version` が永続化されず将来再現性が切れる

- **重大度**: Medium
- **分類**: 宙吊り要件 / データ形式
- **文書引用**
  - `docs/03_mech_generation_and_stats.md:73-80,136-147`: `form_inference/1.0` を独立バージョンとし API 応答へ含める
  - `docs/05_team_and_battle.md:136-140`: 式・定数の版が再現性境界になる
- **実装根拠**
  - `src/photo_mecha_battle/api/database.py:52-60`: mechs に version 列がない
  - `src/photo_mecha_battle/api/game_store.py:593-602`: 作成直後応答にだけ定数を付ける
  - `src/photo_mecha_battle/api/game_store.py:326-338`: DB から再取得した mech には version がない
  - `PLAN.md:70`: D-014 として既知だが未着手
- **影響**
  - `form_inference/2.0` 導入後、既存 mech がどのルールで型決定されたか API/DB から判別できず、再計算・監査・移行判断ができない。
- **推奨**
  - 2.0 着手前ではなく、1.0 データが増える前に version 列を追加して作成時値を固定する。

### SPEC-013 — チーム傾向・弱点表示にフェーズ、算出式、タスクがない

- **重大度**: Medium
- **分類**: 宙吊り要件 / 検証不能基準
- **文書引用**
  - `docs/05_team_and_battle.md:45-67`: 編成画面で火力/耐久/速度/対空/範囲/妨害と弱点助言を表示すると定義
  - `docs/11_mobile_client_design.md:42`: S06 は 3 体 + プリセット選択だけを定義
- **実装根拠**
  - `clients/android/app/src/main/kotlin/com/photomecha/battle/ui/FormationScreen.kt:67-126`
  - `clients/ios/PhotoMechaBattle/Views/FormationView.swift:32-56`
  - 両実装とも機体・プリセット選択と出撃のみで、傾向算出/表示がない。`PLAN.md` に対応タスクもない
- **影響**
  - docs/05 上は現行機能要件だが、Phase 1 非対象とも Phase 2/3 タスクとも書かれていない。実装漏れか将来機能か判定できない。
- **推奨**
  - MVP 外なら docs/08 と docs/11 の「やらないこと」へ移す。MVP 内なら各星の算出式、弱点ルール、受入例を定義しタスク化する。

### SPEC-014 — ML/LLM/UX の受入基準が判定不能

- **重大度**: Medium
- **分類**: 検証不能基準 / 意味の二義性
- **文書引用**
  - `docs/06_monetization_and_fairness.md:89-100`: 「変換成功率が十分」「許容時間」「実用可能」「許容範囲」「挙動差が小さい」
  - `docs/10_mobile_image_generation_survey.md:225-229`: 「同一 seed で再現可能」「シルエット保持率を PO がサンプル 10 枚で確認可能」
  - `docs/07_platform_and_system.md:21-22`: 「片手操作しやすい」「短時間で完結」
- **実装根拠**
  - `scripts/diag/diag_mech_i2i.py:39-55`: 現行診断は MVP stylize の出力を記録するが、シルエット保持率・閾値・端末条件を計測しない
  - `scripts/diag/diag_mech_i2i.py:57-69`: 外部 i2i は `manual_required` の command hint までで、受入判定を実行しない
- **影響**
  - 同じ結果を見ても合格/不合格が担当者ごとに変わる。Phase 0 終了判定、端末 tier、モデル採用、自然言語戦術の品質ゲートを再現できない。
- **推奨**
  - 端末機種/OS/RAM/温度、warm/cold、画像セット、反復数、p50/p95、変換 exact-match/semantic-match、シルエット IoU または輪郭距離、PO 評価尺度と合格件数を定義する。

### SPEC-015 — production code の関数内 import が AGENTS の fail-fast 規則に違反

- **重大度**: Medium
- **分類**: 実装乖離 / 開発規約
- **文書引用**
  - `AGENTS.md:1-3`: グローバルハーネスを適用
  - 適用ルール: production code の関数/メソッド内 import を禁止し、top-level import で起動時 fail-fast
- **実装根拠**
  - `src/photo_mecha_battle/api/game_store.py:312-323`: `_render_and_store_art` 内で `from PIL import Image`
  - `src/photo_mecha_battle/api/app.py:611-617`: `create_battle` 内で `Team, TeamSlot` を import
- **影響**
  - 依存欠落や循環依存が該当経路実行まで遅延する。規約が merge blocker として機能していない。
- **推奨**
  - 既存 top-level import に統合し、`PLC0415` を lint/CI に実際に有効化する。

### SPEC-016 — 正本範囲と仕様索引が docs/11・12 を取りこぼす

- **重大度**: Low
- **分類**: 未定義参照 / 文書間矛盾
- **文書引用**
  - `docs/00_root_overview.md:47-63`: docs/00〜12 を仕様書構成として列挙
  - `AGENTS.md:5-9`: 正本を docs/00〜09、docs/10 を Phase 0 調査とだけ定義し、docs/11・12 の位置づけがない
  - `README.md:121-137`: 仕様一覧が docs/10 で終わる
  - `docs/08_mvp_and_roadmap.md:232-242`: 環境の正本を docs/12 と明示
- **実装根拠**
  - `clients/android/README.md:1-10` と `clients/ios/README.md:1-10`: 実装は docs/11 を正本としている
  - `src/photo_mecha_battle/api/db_path.py:15-24`: docs/12 の DB 環境設計が実装済み
- **影響**
  - エージェントや新規開発者が AGENTS/README だけを起点にすると、クライアント設計と環境設計を読まずに変更できる。
- **推奨**
  - docs/11 はクライアント設計正本、docs/12 は環境設計正本として AGENTS/README の索引へ追加する。

### SPEC-017 — Android テスト基盤の確定記述が JUnit 5 と実装 JUnit 4 で不一致

- **重大度**: Low
- **分類**: 単位・値/形式の不一致
- **文書引用**
  - `docs/11_mobile_client_design.md:12-22`: 技術スタック確定表で Android テストを JUnit 5 と記載
- **実装根拠**
  - `clients/android/core/build.gradle.kts:12-19`: `junit:junit:4.13.2`
  - `clients/android/core/build.gradle.kts:22-28`: JUnit Platform 有効化もない
- **影響**
  - 新規テストが JUnit 5 API 前提で追加されると実行されない/ビルドできない。小さいが「確定」表への信頼を下げる。
- **推奨**
  - JUnit 4 を正とするか JUnit 5 へ移行するかを決め、表・Gradle・CI を同時に揃える。

### SPEC-018 — AGENTS が列挙する診断スクリプト 4 本が未定義

- **重大度**: Low
- **分類**: 未定義参照 / 宙吊り運用要件
- **文書引用**
  - `AGENTS.md:66-78`: `diag_capture_pipeline.sh`、`diag_battle_replay.sh`、`diag_billing_entitlement.sh`、`diag_device_perf.sh` を診断軸として列挙し、出力へ ID/seed/commit を要求
- **実装根拠**
  - `scripts/diag/` に存在するのは `diag_mech_i2i.sh` と `diag_mech_i2i.py` のみ
  - `scripts/diag/diag_mech_i2i.sh:9-23` は seed/commit を出すが、AGENTS 列挙名とは別物
- **影響**
  - 障害時に AGENTS の手順をそのまま実行できず、診断ポリシーの「1 本に集約」が空文化する。
- **推奨**
  - 例示であるなら「将来作成する推奨名」と明記する。必須運用なら PLAN に作成タスクと最低出力契約を追加する。

## セクション別判定

| 範囲 | 判定 | 主な理由 |
|---|---|---|
| docs/00〜01 コア体験 | ✅ 良好 | 型自動推定、コアループ、3 体編成の上位原則は一貫 |
| docs/02 撮影・安全 | ❌ 要設計 | 将来扱いの安全ゲートが本経路で稼働し、score cap の意味も分裂 |
| docs/03 メカ・ステータス | ⚠️ 要補強 | 数式は実装一致。ただし capped info_score と stats の関係、version 永続化が未定義 |
| docs/04 戦術 | ❌ 要設計 | fallback EN と threshold schema が未確定 |
| docs/05 バトル | ⚠️ 要補強 | 数値・決定性は一致。所有権、legacy log、傾向表示が未接続 |
| docs/06 課金 | ❌ 要設計 | サーバー権威原則を `/billing/sync` が破る。クライアント SDK 要件も宙吊り |
| docs/07 データ/API | ⚠️ 要補強 | 所有権の適用範囲と現行スキーマ説明が不完全 |
| docs/08 ロードマップ | ⚠️ 要補強 | 必須 RevenueCat クライアント作業と一部 UI 要件のタスク対応が弱い |
| docs/09 アーキテクチャ | ⚠️ 要補強 | 主経路は概ね一致。課金同期と production demo 配信が原則を迂回 |
| docs/10 技術調査 | ⚠️ 要補強 | 候補整理は明確だが Phase 0 受入が測定不能 |
| docs/11 モバイル | ⚠️ 要補強 | 主要画面/API は一致。release URL、legacy log、RevenueCat、JUnit が乖離 |
| docs/12 環境 | ❌ 要設計 | production fail-closed と実装の既定値が逆 |
| README/AGENTS/CLAUDE | ⚠️ 要補強 | Git 規約は一致。仕様索引・診断参照・lazy import 適用に抜け |

## 問題なしと確認した点

1. **型推定式とタイブレーク**
   - docs/03:97-124 と `src/photo_mecha_battle/mech_stats.py:36-70` は係数、`1e-9`、human→bird→beast の順まで一致。
2. **情報量の基本重み**
   - docs/03:181-190 と `src/photo_mecha_battle/mech_stats.py:6-14,73-82` は 0.25/0.20/0.15/0.15/0.10/0.10/0.05 で一致。
3. **型別基礎値・加算・10〜200 cap**
   - docs/03:211-243 と `src/photo_mecha_battle/mech_stats.py:16-23,89-107` は一致（SPEC-005 の safety cap 例外を除く）。
4. **17 行動の威力・EN**
   - docs/04:91-109 と `src/photo_mecha_battle/battle.py:51-69` は一致。
5. **5 プリセット**
   - docs/04:131-190 と `src/photo_mecha_battle/tactics.py:153-217` は一致。turret の shadowing 修正も反映済み。
6. **バトル数値**
   - docs/05 の K=60、型 1.15/0.90、位置 1.00/0.95/0.90・1.10/1.00/0.85、回避 35%、critical `LUCK/500`・1.2 は `src/photo_mecha_battle/battle.py:23-69,376-416` と一致。
7. **決定性**
   - `random.Random(seed)`、SPD/team ID/position の順、最大 30 ターンは docs/05 と `src/photo_mecha_battle/battle.py:124-165,182-195` で一致。
8. **クォータ**
   - docs/06 の free 20/10、premium 50/30 と `src/photo_mecha_battle/api/limits.py:5-15` は一致。UTC 日付は `database.py:542-571` で実装。
9. **phash**
   - docs/02 の 8×8 64bit、距離 ≤8、同一ユーザー直近 50 件は `vision/analysis.py:31-41`、`capture_pipeline.py:23,53-56`、`database.py:480-485` と一致。
10. **メカ直登録の信頼モデル**
    - RGBA alpha 128、features/1.0、ε=0.05、拒否時クォータ非消費は docs/09 と `vision/analysis.py:98-142`、`game_store.py:188-310` で一致。
11. **構造化ログのサーバー実装**
    - docs/05 の fields と `battle_log_serde.py` / `database.py:341-396` は一致。
12. **DB 永続パス**
    - docs/12 の `{PMB_DATA_DIR}/pmb.sqlite3` / `PMB_DB_PATH` と `api/db_path.py:15-24` は一致。
13. **モバイルの特徴量ゴールデン契約**
    - docs/11 の ε=0.05 と Android/iOS の FeatureExtractor テスト、`tests/golden/` の 3 PNG + manifest は整合。
14. **トークン安全保存**
    - docs/11 の Android EncryptedSharedPreferences / iOS Keychain は `TokenStore.kt:3-24` / `TokenStore.swift:10-67` と一致。
15. **課金で戦術能力を増やさない境界**
    - Entitlement key は `game_store.py:501-509` に限定され、戦術 4 slot と action/condition enum に課金分岐は確認されなかった。

## 推奨アクション順

1. **即時**: SPEC-001 の `/billing/sync` を fail-closed にし、未購入 Entitlement 自己付与を止める。
2. **production 環境着手前**: SPEC-002 と SPEC-007 を解消し、server/client の release 設定を opt-in/fail-fast にする。
3. **ランク戦の外部公開前**: SPEC-003、SPEC-004、SPEC-011 を解消し、所有権・fallback・DSL 検証を固定する。
4. **撮影パイプラインの PO 検証前**: SPEC-005、SPEC-008 を裁定し、安全性ペナルティと戦闘性能の関係を一本化する。
5. **MVP 完了判定前**: SPEC-006 の RevenueCat クライアント導線を独立タスク化し、sandbox 購入・復元まで実地確認する。
6. **次回スキーマ/仕様更新時**: SPEC-009〜018 の文書残骸、version、受入基準、索引を整理する。

