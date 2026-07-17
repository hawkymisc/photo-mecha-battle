# ロードマップ・MVP スコープ整合監査

- 監査日: 2026-07-15
- 対象: `docs/00`〜`docs/12`、`PLAN.md`、実装、テスト、ルート/モバイル README、GitHub Issues / PR
- 方針: 指摘のみ。既存仕様・実装・Issue は変更しない
- 判定基準:
  - **仕様バグ**: 正本間の矛盾、または実装が正本の不変条件を破っている
  - **計画バグ**: 完了マーカー、依存順、受入基準、追跡状態が実態と合わない
  - **単なる未着手**: 未実装だが文書上も未完了として正しく追跡されている

## 監査カバレッジ

### 文書

- [x] `docs/00`: 目的、ゲーム概要、コア体験、仕様書構成、設計原則、MVP、ハッカソン条件
- [x] `docs/01`: コンセプト、プレイヤー体験、基本ループ、層別体験、MVP ループ
- [x] `docs/02`: 撮影、検出、セグメント、品質、不正対策、MVP 実装状態
- [x] `docs/03`: 型推定、FeatureVector、情報量、ステータス、画像生成、MVP 外
- [x] `docs/04`: DSL、条件・行動、プリセット、編集、自然言語生成
- [x] `docs/05`: 編成、バトル、再現性、ダメージ、ログ、ランク戦、ランキング
- [x] `docs/06`: 公平性、クォータ、RevenueCat、Entitlement、Paywall
- [x] `docs/07`: 認証、API 規約、所有権、データモデル、RevenueCat
- [x] `docs/08`: MVP 内外、Phase 0〜4、リスク、確定/未決、課金追加要件
- [x] `docs/09`: 責務分担、信頼モデル、主 API、テスト方針、MVP 外
- [x] `docs/10`: モデル調査、Phase 0 計画、暫定受入基準
- [x] `docs/11`: S00〜S08、エラー導線、API 経路、クライアントテスト、Phase 1 外
- [x] `docs/12`: 環境分離、デプロイ、フェーズ条件、実装ブロッカー

### 裏取り

- [x] Python API・DB・バトル・戦術・画像安全性実装
- [x] Python テスト全193件（2026-07-15 実行: **193 passed**、行カバレッジ 96%）
- [x] Android / iOS の API クライアントと S00〜S08 UI
- [x] Android CI・実地確認記録（PR #35）
- [x] iOS CI・未実地確認記録（PR #36）
- [x] Web デモの CPU 戦・ログ・ランキング経路
- [x] RevenueCat 依存関係、Webhook、同期 API、外部設定ファイル
- [x] GitHub Issue #1〜#6、#21、#23、#26、#27、#31 の状態

## 総括

現状は「Phase 2 バックエンドの主要 API は高いテスト密度で実装済み」だが、「iOS/Android の MVP が限定ユーザーに遊べる」という Phase 2 の目的には未到達である。主な故障モードは、API 実装完了をユーザー機能完了として扱うマーカー、Phase 0 の非ゲート化、RevenueCat の MVP/Phase 3 境界矛盾である。

さらに、課金状態の最終確定をサーバーに置く仕様に対し、`POST /billing/sync` が認証ユーザーの自己申告をそのまま既知 Entitlement に反映する。`generation_boost` を自己付与して日次クォータを増やせるため、現状の最重要リリースブロッカーである。

### 件数

| 分類 | Critical | High | Medium | Low | 計 |
|---|---:|---:|---:|---:|---:|
| 仕様バグ | 1 | 2 | 1 | 0 | 4 |
| 計画バグ | 0 | 2 | 3 | 1 | 6 |
| 単なる未着手（要検証経路） | 0 | 0 | 1 | 0 | 1 |
| **計** | **1** | **4** | **5** | **1** | **11** |

## フェーズ判定

| フェーズ | 文書上の目的 | 実態 | 判定 |
|---|---|---|---|
| Phase 0 | 主要技術の実現性確認 | i2i 実モデル・端末ベンチ・DreamLite・LLM・ストア購入検証が未完。簡易スタイライズ診断と調査はあり | ❌ ゲート未成立のまま後続実装 |
| Phase 1 | 最小ゲームループ成立 | バックエンド、Android 縦切り、両 OS ビルドは成立。Android は PR #35 でエミュレータ実地確認済み、iOS の操作確認は未実施 | ⚠️ Android 成立、iOS 受入未完 |
| Phase 2 | 限定ユーザーで遊べる MVP | 認証・保存・戦術・チーム・PvP・ランキング API は実装/テスト済み。モバイルは Phase 1 API のみで、戦術編集・永続チーム・ランク戦・ランキング・課金 UI がない | ❌ バックエンド部分のみ |
| Phase 3 | 継続性・課金導線 | Entitlement キーとサーバー土台のみ。自然言語生成、保存枠、共有、要約、イベントは未実装 | 🔲 未着手として妥当 |
| Phase 4 | 正式運用・拡張 | シーズン、イベントリーグ、高度ランキング、コミュニティ等は未実装 | 🔲 未着手として妥当 |

## Findings

### RMS-SPEC-001 — クライアント自己申告で premium Entitlement を付与できる

- **分類**: 仕様バグ（実装乖離）
- **重大度**: **Critical**
- **根拠**:
  - `docs/06_monetization_and_fairness.md:180-186` — 課金状態はクライアントだけを信用せず、サーバーでも検証・保持する
  - `docs/09_lightweight_server_architecture.md:78-80,341-353` — 課金の最終確定は Webhook + サーバー Entitlement
  - `src/photo_mecha_battle/api/app.py:702-708` — `/billing/sync` は通常ユーザー認証だけで `active_entitlements` を受理
  - `src/photo_mecha_battle/api/game_store.py:517-527` — 申告された既知キーをそのまま DB に反映
  - `tests/test_phase2.py:484-503,515-520` — ユーザー申告だけで `generation_boost` が有効化され、premium クォータになることを仕様として固定
- **影響**: 任意の認証ユーザーが `generation_boost`、`premium_tactics` 等を自己付与できる。D-004 で管理者限定にしたデモ API を別経路から迂回し、課金境界と生成クォータを破る。
- **推奨**: `/billing/sync` を「RevenueCat サーバー API で CustomerInfo を検証してから反映」に変更する。検証を実装するまでは production で無効化するか、状態を読み取り専用にする。自己申告による付与テストは拒否テストへ置き換え、本番公開ブロッカーとして追跡する。

### RMS-PLAN-001 — Phase 2 の完了マーカーが API 完了をユーザー機能完了として扱っている

- **分類**: 計画バグ
- **重大度**: **High**
- **根拠**:
  - `docs/08_mvp_and_roadmap.md:81-94` — Phase 2 は「限定ユーザーで遊べる状態」で、戦術編集・チーム編成・非同期 PvP・ランキングを含む
  - `PLAN.md:28-33` — P2-003「Tactic slot editor」、P2-004「Async PvP」、P2-005「Ranking」を `✅`
  - `PLAN.md:45` — 同時にモバイルの残課題として「Phase 2 機能（戦術編集・ランク戦・課金）」を明記
  - `docs/11_mobile_client_design.md:153-158` — モバイル Phase 1 では戦術編集、チーム永続化、ランク戦、ランキング UI を実装しない
  - `clients/android/core/src/main/kotlin/com/photomecha/core/api/ApiClient.kt:34-59`
  - `clients/ios/PhotoMechaCore/Sources/PhotoMechaCore/ApiClient.swift:25-71`
    — 両クライアントとも Phase 1 の登録・メカ・プリセット・CPU デモ戦 API だけで、`/tactics`、`/teams`、`/battles/ranked`、`/ranking` を持たない
- **影響**: PLAN だけを見ると Phase 2 の中核が完成しているように見えるが、実ユーザーはモバイルから利用できない。MVP 完成率、次の優先順位、PO レビュー対象を誤る。
- **推奨**: P2-003〜P2-005 を「backend API」と「mobile UI/integration/E2E」に分割し、現行行は `⚠️` にする。Phase 2 の完了条件を、両 OS で永続チーム作成→ランク戦→ランキング反映まで操作できることにする。

### RMS-SPEC-002 — 自然言語戦術が「MVP 後」と「MVP 課金デモ必須」に二重所属している

- **分類**: 仕様バグ
- **重大度**: **High**
- **根拠**:
  - `docs/08_mvp_and_roadmap.md:40-50` — 自然言語戦術生成は MVP 後
  - `docs/08_mvp_and_roadmap.md:96-107` — Phase 3 実装
  - `docs/08_mvp_and_roadmap.md:244-268` — 一方で「MVP に追加する必須項目」の最小課金デモを `premium_tactics` にし、自然言語戦術生成画面を解放
  - `docs/06_monetization_and_fairness.md:129-137` — `premium_tactics` の機能ゲート対象は未実装
  - `clients/android/app/build.gradle.kts:44-66`、`clients/ios/project.yml:7-24` — RevenueCat SDK 依存なし
- **影響**: 現行スコープでは、MVP 完了条件を満たすために Phase 3 機能を先に実装する必要がある。フェーズ飛ばしを誘発し、課金デモの受入基準が達成不能になる。
- **推奨**: MVP の最小課金デモを既にサーバー実装がある `generation_boost` に変更するか、自然言語戦術を明示的に Phase 2 へ移す。どちらの場合も SDK、Offerings、購入、復元、CustomerInfo、Webhook の両 OS 受入項目を同じフェーズへ置く。

### RMS-SPEC-003 — MVP 外の安全性機能が有効化され、既知の誤検出でコアループを遮断する

- **分類**: 仕様バグ（スコープ/実装乖離）
- **重大度**: **High**
- **根拠**:
  - `docs/02_photo_object_extraction.md:96-101` — ノイズ、QR、顔・個人情報検出はいずれも `🔲 将来`
  - `docs/11_mobile_client_design.md:69-75` — Phase 1 UI は `face_detected` を現行エラーとして扱う
  - `src/photo_mecha_battle/vision/analysis.py:205-238,241-300` — 顔・QR・ノイズ検出を実装し、顔は `blocked`
  - `tests/test_mvp_capture.py:82-99` — 顔らしき画像の 422 拒否を回帰固定
  - `PLAN.md:68`、Issue #21 — 暖色系風景を高頻度で顔と誤検出する既知バグ
- **影響**: MVP 外機能が撮影→メカ生成の主経路を遮断する。仕様上は未実装なので、誤検出率・許容基準・リリース判断の責任所在もない。
- **推奨**: β 前まで無効化/`warning` 化する案と、MVP へ正式昇格して実写陰性データセット・誤検出率基準を設ける案を PO 判断にする。Issue #21 を撮影主経路のリリースブロッカーとして扱う。

### RMS-PLAN-002 — Phase 0 の検証項目が PLAN に網羅されず、未成立のまま Phase 1/2 へ進んでいる

- **分類**: 計画バグ
- **重大度**: **High**
- **根拠**:
  - `docs/08_mvp_and_roadmap.md:54-65` — 抽出、セグメント品質、情報量妥当性、i2i、ローカル LLM、両 OS 性能を Phase 0 に定義
  - `docs/08_mvp_and_roadmap.md:270-278` — RevenueCat の両 OS SDK、テスト購入、復元、CustomerInfo、画面解放、Webhook も Phase 0 検証
  - `PLAN.md:3-11` — Phase 0 行は画像生成調査/試作/ベンチ/DreamLite/診断だけで、抽出品質、情報量妥当性、LLM、RevenueCat の追跡行がない
  - `PLAN.md:8-10` — 実モデル試作・端末ベンチ・DreamLite は `🔲` のまま
  - `PLAN.md:13-46` — 一方で Phase 1/2/2.5 の多数を完了扱い
- **影響**: Phase 0 が「後続へ進むためのゲート」なのか「将来研究の並列トラック」なのか不明で、フェーズ飛ばしを判定できない。MVP 外へ移した i2i/LLM が Phase 0 を永久に未完了にする。
- **推奨**: Phase 0 を「MVP 主経路ゲート」と「将来研究スパイク」に分離する。前者には抽出/特徴量のゴールデン一致、端末処理時間、RevenueCat sandbox の両 OS 実証を置き、後者へ高品質 i2i・ローカル LLM を移す。

### RMS-PLAN-003 — P0-005 の `✅` は実 i2i 再現性ではなく簡易スタイライズ再現性だけを証明する

- **分類**: 計画バグ
- **重大度**: **Medium**
- **根拠**:
  - `PLAN.md:11` — P0-005 を「seed 固定再現性」として `✅`
  - `docs/10_mobile_image_generation_survey.md:214-229` — Phase 0d は i2i 診断で、受入基準は生成結果の再現性・端末時間・シルエット保持
  - `scripts/diag/diag_mech_i2i.py:39-69` — 実行するのは `mvp_stylize`; external i2i は `not_run` または `manual_required`
  - `tests/test_diag_mech_i2i.py:13-33` — テストも簡易スタイライズの hash とスクリプト終了だけを検証
- **影響**: 高品質 i2i の決定性を確認済みと誤読できる。実モデルでは seed 固定でも OS/バックエンド差があり得るため、採用判断の証拠にならない。
- **推奨**: P0-005 を「MVP stylize 診断基盤」に改名するか `⚠️` にし、実モデルの同一端末再現・クロス OS 許容差・出力 artifact を別受入項目にする。

### RMS-PLAN-004 — Phase 0〜2 の受入基準が完了判定可能な形になっていない

- **分類**: 計画バグ
- **重大度**: **Medium**
- **根拠**:
  - `docs/08_mvp_and_roadmap.md:52-120` — 各 Phase は目的と実装項目のみで、終了条件、対象端末、データセット、操作シナリオ、合否閾値がない
  - `docs/08_mvp_and_roadmap.md:124-142` — 「セグメンテーション品質」「情報量の納得感」は対策のみで測定方法がない
  - `docs/10_mobile_image_generation_survey.md:225-229` — 「シルエット保持率を PO が確認可能」は保持率の算式・合格値がなく、受入基準になっていない
  - `docs/06_monetization_and_fairness.md:89-100` — LLM の「十分」「許容時間」「実用可能」に数値がない
- **影響**: 実装の存在、テスト成功、PO の体験受入が混同され、完了マーカーの一貫した更新ができない。
- **推奨**: 各 Phase に最小限の Exit Criteria を追加する。Phase 1 は両 OS の縦切り操作、Phase 2 は戦術編集→永続チーム→ランク戦→ランキング反映、Phase 0 品質は固定データセット・端末 tier・閾値で定義する。

### RMS-VERIFY-001 — iOS と Phase 2 公開 UI 統合経路が未検証

- **分類**: 単なる未着手（検証ギャップ）
- **重大度**: **Medium**
- **根拠**:
  - `docs/11_mobile_client_design.md:142-151` — UI/カメラは実機相当スモークが merge 前ゲート
  - `.github/workflows/ios.yml:15-40` — core テストと generic simulator build のみで、アプリ操作はしない
  - `clients/ios/README.md:40-46` — 実機での登録→撮影→CPU戦→ログは未実施の確認手順
  - `PLAN.md:45` — iOS 体験確認と Phase 2 モバイル機能を残課題として `⚠️`
  - `docs/12_environments.md:163-170,176-181` — Phase 2 必須の staging は未構築
  - PR #35 — Android の登録→メカ3体→CPU戦はエミュレータ確認済み
  - PR #36 — iOS は core test / build 成功、実機体験は未チェック
- **影響**: iOS のカメラ、権限、Keychain、multipart、API 接続を含む公開経路は動作未確認。Phase 2 の PvP/ランキング/課金は両 OS とも UI 経路自体がない。
- **推奨**: 現在の `⚠️` は維持し、iOS 実機 Phase 1 と両 OS Phase 2 を別タスクにする。Phase 2 は staging + sandbox 課金を含む保存可能な E2E シナリオを実行してから完了にする。

### RMS-SPEC-004 — docs/07 の battles データモデルが実装済み構造化ログを未実装と記載する

- **分類**: 仕様バグ（文書更新漏れ）
- **重大度**: **Medium**
- **根拠**:
  - `docs/07_platform_and_system.md:82-85` — データモデルは現行実装と同期済みと宣言
  - `docs/07_platform_and_system.md:160-173` — `log_text` のみを列挙し、構造化 JSON は「移行予定（現行は整形テキスト）」と記載
  - `docs/05_team_and_battle.md:204-222` — `log_json` / `log_entries` を実装済みと記載
  - `src/photo_mecha_battle/api/database.py:80-92,142-147,355-395` — `log_json` のスキーマ、移行、保存、取得を実装
  - `tests/test_database.py:17-70` — 構造化ログと旧行フォールバックを検証
- **影響**: API/DB 移行を設計する人が、完了済み D-003 を再実装対象と判断する。docs/07 冒頭の「同期済み」という信頼性も落ちる。
- **推奨**: battles 表に `log_json` を追記し、移行予定注記を「実装済み、旧行は null」に更新する。

### RMS-PLAN-005 — 完了済み D タスクの GitHub Issues が open のまま残っている

- **分類**: 計画バグ（追跡状態）
- **重大度**: **Medium**
- **根拠**:
  - `PLAN.md:61-69` — D-002、D-003、D-004、D-007、D-008、D-010 は `✅`
  - GitHub Issues（2026-07-15 取得）— 対応する #1、#2、#3、#5、#6、#23 はすべて **OPEN**
  - `docs/04_tactics.md:190-192`、`docs/05_team_and_battle.md:129-140,219-222`、`docs/06_monetization_and_fairness.md:141-149,188-197` — 実装済み記録あり
  - Python 全テスト 193 passed — 上記修正の回帰テストも green
- **影響**: GitHub 上では既修正のセキュリティ/バトル障害が未解決に見え、実際の open blocker（#21、#31）と区別できない。進捗集計と引き継ぎが誤る。
- **推奨**: 修正 PR とテスト証拠を付けて #1、#2、#3、#5、#6、#23 を close する。部分完了の #4 は外部設定完了まで open を維持する。

### RMS-PLAN-006 — ルート README の仕様一覧が docs/11・docs/12 を反映していない

- **分類**: 計画バグ（文書インベントリ）
- **重大度**: **Low**
- **根拠**:
  - `docs/00_root_overview.md:47-63` — docs/00〜12 の13文書を一覧化
  - `README.md:121-137` — 仕様書一覧が docs/10 で終わり、モバイル設計 docs/11 と環境設計 docs/12 がない
- **影響**: 新規参加者が Phase 1 の正本と環境ゲートを見落としやすい。実装状態そのものには影響しない。
- **推奨**: README の仕様一覧へ docs/11・docs/12 を追加する。

## 正しく未着手として追跡されている項目

以下は不足ではあるが、現状の文書・PLAN が未完了を正しく表しており、完了マーカーのバグではない。

- `PLAN.md:8-10` — SD 1.5 LoRA 試作、端末ベンチ、DreamLite PoC
- `PLAN.md:33,64` と `config/revenuecat_pending_setup.json:13-50` — RevenueCat 外部商品設定・Webhook secret
- `PLAN.md:68` — 顔誤検出 Issue #21（ただし RMS-SPEC-003 のスコープ判断は必要）
- `PLAN.md:70`、Issue #31 — `form_inference_version` 永続化
- `PLAN.md:84-86`、`docs/12_environments.md:191-202` — production ガード、staging、クライアントフレーバー
- `docs/06_monetization_and_fairness.md:133-137` — Phase 3 の自然言語生成、保存枠、ログ要約、外見要素
- `docs/08_mvp_and_roadmap.md:109-120` — Phase 4 のシーズン、イベント、高度ランキング、コミュニティ

## MVP 対象外の正常確認

- リアルタイム PvP はなく、実装は非同期 API（`/battles/match`、`/battles/ranked`）。
- 戦闘中 LLM 呼び出しはない。戦術評価は決定的 DSL。
- 高品質 i2i 常時 GPU ワーカー、マーケット、トレード、AR、位置情報、ギルド、育成ツリーの実装は見当たらない。
- 状態異常は導入されず、`disrupt` は低威力攻撃のままテスト固定されている。
- Phase 3/4 のコード先行は Entitlement の予約キーとサーバー土台に限定され、機能本体のフェーズ飛ばしはない。

## 正常確認点

1. **バックエンドの回帰品質**: `python -m pytest` は 193 passed、行カバレッジ 96%。C0 90% / C1 80% のゲートを満たす。
2. **決定的バトル**: seed 固定再現、先勝ち戦術、EN 不足フォールスルー、ダメージ式、型相性がテストで固定されている。
3. **サーバー権威バトル**: ランク戦 seed はサーバー生成で、モバイルは `log_entries` を再生するだけで勝敗・ダメージを再計算しない。
4. **特徴量のクロスプラットフォーム境界**: Android/iOS とサーバーが共通ゴールデンを ε=0.05 で検証する。PR #35/#36 の CI は green。
5. **Android Phase 1**: PR #35 に登録→メカ3体生成→編成→CPU戦→ログ再生のエミュレータ実地確認記録がある。
6. **部分完了マーカー**: P25-007、P2-006、D-005 は残課題を明記した `⚠️` であり、状態表現は妥当。
7. **将来機能の隔離**: 高品質 i2i、自然言語戦術、状態異常、Phase 4 機能は概ね将来節へ隔離されている。
8. **課金公平性の戦闘境界**: 戦術スロット上限・条件・行動・バトル計算に Entitlement 分岐は見当たらない。RMS-SPEC-001 は利便性権限の不正付与であり、戦闘ロジック自体の P2W 分岐ではない。

## 推奨アクション順

1. **即時リリースブロック**: RMS-SPEC-001 の `/billing/sync` 自己申告付与を閉じる。
2. **PO スコープ裁定**: RMS-SPEC-002 の RevenueCat MVP デモを `generation_boost` にするか、自然言語戦術を Phase 2 へ移すか決める。
3. **MVP 状態を再表示**: RMS-PLAN-001 に従い、Phase 2 を backend / mobile / E2E に分割してマーカーを更新する。
4. **撮影主経路を安定化**: RMS-SPEC-003 と Issue #21 の短期方針を決める。
5. **フェーズゲート再定義**: RMS-PLAN-002〜004 に従い Phase 0/1/2 の Exit Criteria を追加する。
6. **追跡衛生**: docs/07、README、完了済み Issues を実態へ同期する。
