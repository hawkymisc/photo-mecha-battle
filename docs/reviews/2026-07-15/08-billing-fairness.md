# 課金・Entitlement・公平性・ランキング境界監査

- 監査日: 2026-07-15
- 対象: `docs/06_monetization_and_fairness.md`、`docs/07_platform_and_system.md`、`docs/09_lightweight_server_architecture.md`、関連するロードマップ・実装・テスト
- 方式: 仕様横断比較、実装静的確認、テスト確認、メモリ内再現
- 判定基準: サーバー権威、Pay to Convenience、RevenueCat の課金ライフサイクル、ランキングの再現性・一貫性

## 結論

**11 findings（Critical 1 / High 6 / Medium 4）**を確認した。

最優先は、認証済みクライアントが自己申告だけで `generation_boost` を有効化できる点（BF-001）である。加えて、他ユーザー所有のメカ・戦術を自分のランク戦チームへ組み込める点（BF-002）、有料の生成回数増加がランク戦用個体の選別回数を直接増やすため Pay-to-Win ではないという説明が成立していない点（BF-003）が、公平性の根幹に影響する。

RevenueCat SDK・Paywall・購入復元のモバイル実装が未着手であること自体は、現状の Phase 1 クライアントと `PLAN.md` で明示されたロードマップ上の未実装であり、直ちに既存機能のバグとは扱わない。ただしストア提出・課金導線公開のリリースゲートである。

## 監査カバレッジ

### 仕様

- [x] `docs/06`: 目的、基本方針、許可/禁止課金、Pay-to-Win 回避、生成クォータ、自然言語戦術、RevenueCat の役割、Entitlement、Webhook、商品案、Paywall、実装必須要件、デモ API
- [x] `docs/07`: 認証、所有権、users / tactic_sets / teams / battles / user_entitlements / daily_quotas、RevenueCat 連携
- [x] `docs/09`: 責務分担、信頼モデル、非同期 PvP、API 設計、課金、保存、セキュリティ、テスト方針
- [x] 補助仕様: `docs/03` のステータス算出、`docs/05` のリプレイ・レーティング、`docs/08` のフェーズ/未決事項、`docs/11` のモバイル範囲、`docs/12` の環境分離
- [x] 計画/外部設定: `PLAN.md`、`config/revenuecat_pending_setup.json`、`config/po_pending_decisions.json`

### 実装・テスト

- [x] `src/photo_mecha_battle/api/app.py`
- [x] `src/photo_mecha_battle/api/game_store.py`
- [x] `src/photo_mecha_battle/api/database.py`
- [x] `src/photo_mecha_battle/api/limits.py`
- [x] `src/photo_mecha_battle/tactics.py`
- [x] `tests/test_revenuecat_webhook.py`
- [x] `tests/test_phase2.py`
- [x] `tests/test_mvp_capture.py`
- [x] `tests/test_database.py`
- [x] Android/iOS の依存定義と RevenueCat 参照有無
- [x] メモリ内再現: 自己申告 `generation_boost` と他ユーザー資産によるチーム構築

## Findings

### BF-001 — クライアント自己申告だけで Entitlement を付与できる

- **重大度:** Critical
- **種別:** 実装バグ / 権威境界違反
- **file:line:** `src/photo_mecha_battle/api/app.py:191-192,702-708`; `src/photo_mecha_battle/api/game_store.py:517-527`; `tests/test_phase2.py:484-521`
- **仕様節:** `docs/06`「実装上の必須要件」(180-186)、`docs/07`「RevenueCat 連携」(197-204)、`docs/09`「セキュリティ・不正対策」(341-353)
- **現状/根拠:** 仕様は「課金状態はクライアントのみを信用せず、サーバー側でも検証・保持する」とする。一方、`POST /billing/sync` は認証済みユーザーが送った `active_entitlements` を RevenueCat へ照会せず、そのまま既知キーの真偽として保存する。既存テストは自己申告した `generation_boost` で日次メカ上限が 10 から 30 に増えることを成功条件として固定している。メモリ内でも再現済み。
- **影響/失敗シナリオ:** 無課金ユーザーが `{"active_entitlements":["generation_boost"]}` を送るだけで有料枠を取得できる。Phase 3 機能追加後は、同じ経路で戦術生成・保存枠・ログ要約も自己解放できる。Webhook の認証を強化してもこの別経路から迂回される。
- **推奨:** クライアント申告をサーバー権限に反映しない。`/billing/sync` はサーバーが RevenueCat の subscriber/CustomerInfo 相当 API をサーバー資格情報で取得して照合する方式へ変更するか、Webhook のみを権威ソースとして同期要求は再照会トリガーに限定する。自己申告による付与・失効を拒否する回帰テストを追加する。

### BF-002 — 他ユーザーのメカ・戦術をランク戦へ持ち込める

- **重大度:** High
- **種別:** 実装バグ / 所有権・非公開情報境界違反
- **file:line:** `src/photo_mecha_battle/api/app.py:403-418,445-485,494-530`; `src/photo_mecha_battle/api/game_store.py:375-441`; `src/photo_mecha_battle/api/database.py:199-243`
- **仕様節:** `docs/05`「戦術 AI が参照できる情報」(183-195)、`docs/07`「所有権」(75-80)、`docs/09`「バトル入力」(106-114)
- **現状/根拠:** `POST/PUT /teams` はチーム自体の所有者は確認するが、各 `mech_id` / `tactic_id` の所有者を確認しない。`load_team_for_battle` も ID だけで読み込む。また `GET /tactics/{id}` と `/tactics/{id}/simulate` は認証・所有権確認なしで、仕様上非公開の戦術全文を返却/実行する。被害者所有の高ステータスメカ 3 体と戦術 3 件を攻撃者のチームへ保存し、バトル読込できることをメモリ内で再現済み。
- **影響/失敗シナリオ:** ID がログ、デバッグ情報、端末内データ等から漏れた場合、対戦相手の非公開戦術を閲覧し、強いメカを自分のランク戦チームとして使用できる。UUID の推測困難性は認可の代替にならない。
- **推奨:** チーム作成・更新時に全メカ/戦術の `user_id == request user` を一括検証し、不一致を 403 にする。戦術取得・simulate に認証と所有権確認を追加する。DB の参照整合性も有効化し、他ユーザー資産混入・戦術閲覧の拒否テストを追加する。

### BF-003 — `generation_boost` はランク戦個体の選別回数を増やす

- **重大度:** High
- **種別:** 仕様上の公平性矛盾 / Pay-to-Win リスク
- **file:line:** `docs/06_monetization_and_fairness.md:50-64`; `docs/03_mech_generation_and_stats.md:192-243`; `src/photo_mecha_battle/api/limits.py:5-31`; `src/photo_mecha_battle/api/game_store.py:154-186`
- **仕様節:** `docs/06`「生成クォータ（確定）」「Pay to Win 回避原則」、`docs/03`「情報量スコア」「ステータス算出式」
- **現状/根拠:** 仕様は premium のメカ生成を 10/日から 30/日に増やし、「生成の試行回数を増やすのみ」なので利便性と結論づける。しかし各生成結果の特徴量は HP/ATK/DEF/SPD/TEC/EN/LUCK に反映され、そのままランク戦へ使用できる。生成・保存した個体数にもランク適格性にも共通上限がない。
- **影響/失敗シナリオ:** 課金者は非課金者の 3 倍の候補から上位個体を選別できる。個体ごとの式が同じでも、探索予算の差が期待最大ステータスと編成最適化へ直結するため、戦闘能力差が生じうる。「バトル性能は変わらない」という Paywall 表示も実態とずれる。
- **推奨:** 少なくともランク適格メカの生成/登録回数は全員共通にする。premium の追加回数を見た目再生成、未確定プレビュー、保存整理など戦闘性能を変えない用途へ限定する案が望ましい。現方式を維持するなら、生成回数別の上位個体分布と勝率差をシミュレーションし、許容差を受入基準として定義する。

### BF-004 — `CANCELLATION` 受信時に権限を早期失効する

- **重大度:** High
- **種別:** 仕様・実装のライフサイクル誤り
- **file:line:** `docs/06_monetization_and_fairness.md:151-157`; `src/photo_mecha_battle/api/game_store.py:511-515,562-565`; `tests/test_revenuecat_webhook.py:55-77`
- **仕様節:** `docs/06`「Webhook イベント処理（MVP）」
- **現状/根拠:** 仕様・実装・テストのすべてが `CANCELLATION` を即時失効としている。RevenueCat 公式の webhook flow では、通常の解約時は現課金期間の末尾まで Entitlement が有効で、アクセス削除は `EXPIRATION` 時に行う。`CANCELLATION` は自動更新停止や課金問題の通知であり、失効時点ではない。
- **影響/失敗シナリオ:** 月途中で自動更新を停止した正規購入者や grace period 中の利用者が、支払済み期間を残して機能を失う。復元/同期が未整備なため、次のイベントまで不整合が継続する。
- **推奨:** 通常の `CANCELLATION` では権限を維持し、更新予定状態だけを記録する。`EXPIRATION` で失効する。返金等の即時失効が必要な場合は `cancel_reason`、`expiration_at_ms`、RevenueCat 現在状態の再照会を組み合わせる。現テストを公式ライフサイクルに合わせて修正する。

参考: <https://www.revenuecat.com/docs/integrations/webhooks/event-flows>

### BF-005 — Webhook の順序・有効期限・原子的反映を管理できない

- **重大度:** High
- **種別:** 実装バグ / 失敗時不整合
- **file:line:** `src/photo_mecha_battle/api/database.py:93-98,130-135,405-438`; `src/photo_mecha_battle/api/app.py:711-730`; `src/photo_mecha_battle/api/game_store.py:529-566`
- **仕様節:** `docs/06`「Webhook イベント処理（MVP）」、`docs/07`「user_entitlements」(175-184)、`docs/09`「課金（最終）」(69-80)
- **現状/根拠:** 保存状態は `is_active` だけで、`event_timestamp_ms`、`expiration_at_ms`、商品、環境、更新元を保持しない。`event.id` は重複排除にしか使われず、異なる ID の古いイベントが後着した場合の順序判定がない。複数 Entitlement の更新と processed marker も個別 commit で、1 トランザクションではない。
- **影響/失敗シナリオ:** ネットワーク遅延で古い `RENEWAL` が `EXPIRATION` 後に到着すると失効済み権限を再付与できる。逆順のイベントで正規利用者を失効させる可能性もある。プロセス停止が複数キー更新の途中で起きると、一時的に商品の一部機能だけが有効になる。
- **推奨:** Entitlement ごとに最終イベント時刻、有効期限、商品、更新元を保存し、古いイベントを拒否する。Webhook event の登録、全 Entitlement 更新を同一 DB トランザクションにする。順不同・重複・途中失敗の fault-injection テストを追加する。

### BF-006 — バトル保存・双方レーティング・キュー更新が非原子的で再試行も非冪等

- **重大度:** High
- **種別:** 実装バグ / ランキング整合性
- **file:line:** `src/photo_mecha_battle/api/app.py:572-608`; `src/photo_mecha_battle/api/game_store.py:470-499`; `src/photo_mecha_battle/api/database.py:173-181,337-378`
- **仕様節:** `docs/05`「レーティング反映（MVP）」(251-268)、`docs/09`「非同期 PvP バトル」(136-152)
- **現状/根拠:** `save_battle`、各プレイヤーの `update_rating`、各チームの dequeue がそれぞれ commit される。API に idempotency key や一意な match ticket がなく、クライアント再送は別バトルとして再決済される。
- **影響/失敗シナリオ:** バトル保存後・片側レーティング更新後にプロセスが落ちると、勝者だけ加点、敗者据え置き、またはキュー残留になる。タイムアウト後のクライアント再試行で同一意図のレーティングが複数回変動する。
- **推奨:** match/battle ID を事前発行し、バトル結果保存、双方レーティング、キュー更新を単一トランザクションで確定する。クライアント idempotency key または単回使用 match ticket に UNIQUE 制約を置き、再送時は既存結果を返す。

### BF-007 — CPU フォールバックを無制限に繰り返してランキングを増やせる

- **重大度:** High
- **種別:** 仕様上のランキング設計欠陥
- **file:line:** `src/photo_mecha_battle/api/app.py:572-608`; `src/photo_mecha_battle/api/game_store.py:466-493`; `tests/test_phase2.py:324-333`
- **仕様節:** `docs/05`「レーティング反映（MVP）」(251-268)、`docs/08`「Phase 2：MVP」(81-95)
- **現状/根拠:** 対戦相手がいなければ CPU 戦になり、勝利で +10 される。`POST /battles/ranked` は事前のマッチ成立、単回チケット、回数制限、クールダウンを要求せず、何度でも直接呼べる。
- **影響/失敗シナリオ:** CPU に安定勝利できる編成がエンドポイントを反復し、対人戦をせずにレーティングとランキング順位を無制限に上げられる。BF-003 の多試行個体選別と組み合わさると課金者のランキング優位を増幅する。
- **推奨:** CPU フォールバックはグローバル PvP レーティング対象外にするのが最も明確。対象に残すなら、単回使用 match ticket、期間上限、期待値ゼロになる rating 式、bot 対戦の別ランキングを設計する。

### BF-008 — 購入復元時のユーザー同一性・alias・transfer が未定義

- **重大度:** Medium
- **種別:** 実装ギャップ / 復元・同期不整合
- **file:line:** `src/photo_mecha_battle/api/app.py:717-730`; `src/photo_mecha_battle/api/game_store.py:545-560`; `tests/test_revenuecat_webhook.py:119-145`
- **仕様節:** `docs/06`「RevenueCat の役割」(117-127)・「実装上の必須要件」(178-186)、`docs/07`「RevenueCat 連携」(197-204)
- **現状/根拠:** Webhook は `app_user_id` が内部 user UUID と完全一致する場合だけ処理する。`original_app_user_id` / `aliases` を参照せず、`TRANSFER` は unknown event として無視する。RevenueCat は webhook でユーザー検索時に original ID と aliases の双方を確認するよう案内している。
- **影響/失敗シナリオ:** 匿名 RevenueCat ID で購入後にログインした場合、端末変更・再インストール・アカウント統合・購入 transfer で `user_not_found` または `ignored_event` となる。移転元に権限が残り、移転先に付かない二重不整合も起こりうる。
- **推奨:** 購入前に内部 user ID を RevenueCat App User ID として login/bind する契約を明文化する。alias/original ID の対応表を保持し、`TRANSFER` を処理するか、復元時にサーバーが RevenueCat 現在状態を再照会して全スナップショットを原子的に同期する。

参考: <https://www.revenuecat.com/docs/integrations/webhooks/event-types-and-fields>

### BF-009 — seed リプレイに必要な入力スナップショットとルール版がない

- **重大度:** Medium
- **種別:** 仕様の宙吊り / 監査・再現性
- **file:line:** `src/photo_mecha_battle/api/database.py:80-91,341-396`; `src/photo_mecha_battle/api/game_store.py:426-483`; `src/photo_mecha_battle/api/database.py:245-250,277-298`
- **仕様節:** `docs/05`「バトル基本方針」(69-75)・「式変更と過去バトルの互換性」(136-140)、`docs/09`「非同期 PvP バトル」(136-155)
- **現状/根拠:** battle には seed と結果ログを保存するが、対戦時のメカ stats、戦術 payload、チーム配置の不変スナップショット、バトルエンジン版を保存しない。チーム・戦術は後から更新可能である。
- **影響/失敗シナリオ:** ランク戦後に戦術を更新したりバランス定数を変えると、同じ seed でも元バトルを再シミュレーションできない。不正申告やランキング事故の調査で「どの入力で確定したか」を証明できない。保存済み `log_json` の再生はできるため、表示リプレイ自体は壊れない。
- **推奨:** 「リプレイ」を構造化ログ再生だけと定義し、seed 再シミュレーション保証を外すか、対戦時の team/mech/tactic snapshot と `battle_rules_version` を保存する。ランキング監査には後者を推奨する。

### BF-010 — Webhook payload の sandbox/production 環境を検証しない

- **重大度:** Medium
- **種別:** 環境境界の防御不足
- **file:line:** `src/photo_mecha_battle/api/app.py:711-730`; `config/revenuecat_pending_setup.json:43-50`
- **仕様節:** `docs/12`「環境ごとの責務」(42-78)・「構成要素と環境マトリクス」(81-105)、`docs/09`「課金（最終）」(69-80)
- **現状/根拠:** `environment` は RevenueCat payload に含まれるが、request model は event を非型付き dict として受け、処理時に検証しない。外部設定 TODO も共有シークレットだけで、期待環境の検証条件を持たない。
- **影響/失敗シナリオ:** RevenueCat ダッシュボードの送信先設定を誤り、sandbox event が production API に届いた場合、テスト購入で本番 Entitlement が付与される。DB 分離だけでは受信時の誤配送を防げない。
- **推奨:** `PMB_ENV` 等から期待する RevenueCat environment を決定し、staging は `SANDBOX`、production は `PRODUCTION` 以外を拒否する。環境別 webhook URL・secret・project/app ID も検証する。

### BF-011 — 戦術保存枠の無料/有料上限と移行規則が未定義

- **重大度:** Medium
- **種別:** ロードマップ上正当な未実装 / 仕様の宙吊り
- **file:line:** `docs/06_monetization_and_fairness.md:129-139`; `docs/08_mvp_and_roadmap.md:96-107,224-229`; `src/photo_mecha_battle/api/app.py:439-466`; `src/photo_mecha_battle/api/database.py:228-250`
- **仕様節:** `docs/06`「Entitlement 定義（正）と実装状態」、`docs/08`「Phase 3：β版」「課金関連」
- **現状/根拠:** `extra_tactic_slots` は「戦闘スロットではなく保存枠」と正しく区別され、Phase 3 未実装として追跡されている。一方、無料枠・premium 枠の具体数、上限到達時、失効時に上限超過データをどう扱うかが未決で、現 API は全員が無制限に保存できる。
- **影響/失敗シナリオ:** Phase 3 で突然上限を導入すると、既存無料ユーザーの保存済み戦術を削除/編集不能にするか、既存ユーザーだけ無制限にするかの不公平な移行判断が必要になる。失効時に戦術を削除するとユーザーデータ喪失、戦闘チームから外すとランキング編成が壊れる。
- **推奨:** Phase 3 着手前に無料/有料枠数、超過時は「既存閲覧・使用可、追加保存不可」等の非破壊規則、チーム参照中戦術の扱い、grandfathering を決定する。これは現 Phase 1 のバグではないが、課金導入前の設計ゲートとする。

## 正常確認点

1. **戦闘スロット数は Entitlement 非依存:** `TacticCreateRequest` と `TacticSet.from_slots` の双方が最大 4 を固定しており、課金分岐はない（`src/photo_mecha_battle/api/app.py:141-144`; `src/photo_mecha_battle/tactics.py:107-122`; `tests/test_tactics.py:53-56`）。
2. **条件・行動カタログは共通:** battle/tactics 実装は Entitlement を参照せず、課金キーが使用される production path は現在クォータ判定のみである。
3. **クォータキーの分離:** `generation_boost` だけが 20/10 を 50/30 に拡張し、`premium_tactics` 等は拡張しない（`src/photo_mecha_battle/api/limits.py:5-31`; `tests/test_mvp_capture.py:102-125`）。
4. **デモ付与 API は fail-closed:** `PMB_ADMIN_TOKEN` 未設定・誤り・欠落時に 403 となり、未知 Entitlement も拒否する（`src/photo_mecha_battle/api/app.py:62-72,685-699`; `tests/test_phase2.py:428-468`）。
5. **Webhook 認証は fail-closed:** 共有 secret 未設定・欠落・不一致時に 401 となる（`src/photo_mecha_battle/api/app.py:75-85`; `tests/test_revenuecat_webhook.py:223-262`）。
6. **Webhook 再送の同一 ID は検出:** processed event ID を保存し、同一 ID の再送を無視する（`src/photo_mecha_battle/api/database.py:423-438`; `tests/test_revenuecat_webhook.py:193-207`）。ただし BF-005 の順序制御は別途必要。
7. **ランク戦 seed・勝敗・rating はサーバー確定:** クライアント seed を無視し、サーバー生成 seed で結果を保存する（`src/photo_mecha_battle/api/app.py:162-166,572-608`; `src/photo_mecha_battle/api/game_store.py:449-493`; `tests/test_phase2.py:153-181`）。
8. **バトルログの参照制御:** 永続ランク戦ログは当事者だけが取得でき、第三者は 403（`src/photo_mecha_battle/api/app.py:642-658`; `tests/test_phase2.py:336-385`）。
9. **構造化ログが正史:** `log_json` を保存し、過去行は text log にフォールバックするため、現行の表示リプレイはバランス変更後も保持される（`src/photo_mecha_battle/api/database.py:341-396`; `tests/test_database.py:17-71`）。
10. **外部設定は明示追跡:** 商品↔Entitlement 紐付けと webhook secret は `config/revenuecat_pending_setup.json` に分離され、安全側未設定を維持している。

## ロードマップ上正当な未実装（バグと区別）

- **RevenueCat SDK / Offerings / Paywall / restorePurchases / CustomerInfo:** Android Gradle と iOS Package/XcodeGen に RevenueCat 依存がなく、クライアントコードにも参照がない。ただし `docs/11:153-157` は Phase 1 対象外、`PLAN.md:33-45` は P2-006/P25-007 を進行中として明記している。現時点ではロードマップ上正当だが、`docs/06:178-186` と `docs/08:248-278` によりストア課金公開前の必須ゲート。
- **`premium_tactics`、`extra_tactic_slots`、`battle_log_summary`、`cosmetic_pack_access`:** `docs/06:129-139` と `docs/08:96-120` で Phase 3 以降として明記されており、未実装自体はバグではない。BF-011 の上限・失効規則だけは着手前に決定が必要。
- **RevenueCat ダッシュボード設定:** 商品定義、Entitlement 紐付け、共有 secret は `config/revenuecat_pending_setup.json` で外部ブロッカーとして追跡済み。コード未実装ではないが、完了前は実購入連携が成立しない。
- **Elo、シーズン、ページネーション:** 固定デルタと上位 20 件は MVP の明示仕様であり、高度なランキングは Phase 4。未実装をバグとはしない。ただし BF-006/BF-007 の整合性・乱用防止は現 MVP 内の問題。

## 不足しているテスト

- `/billing/sync` の自己申告付与を拒否するテスト
- Webhook の out-of-order、期限比較、複数キー途中失敗、transaction rollback
- `CANCELLATION` 後も `EXPIRATION` まで有効であること
- `TRANSFER`、aliases/original App User ID、購入復元
- sandbox event の production 拒否
- 他ユーザーの mech/tactic を team に指定した場合の 403
- 非公開 tactic の取得/simulate の 401/403
- ランク戦 endpoint 再送の冪等性、片側 rating 更新失敗の rollback
- CPU 戦反復による rating 増加を禁止または制限するテスト
- Entitlement 有無で戦術 4 スロット・条件・行動・勝敗が完全同一であることを直接比較する公平性テスト

## 推奨対応順

1. **課金公開前ブロッカー:** BF-001、BF-004、BF-005、BF-008、BF-010
2. **ランキング公開前ブロッカー:** BF-002、BF-006、BF-007
3. **公平性の PO 判断:** BF-003。生成追加枠を rank-eligible 個体の探索へ使わせるかを再決定
4. **Phase 3 着手前:** BF-011 の保存枠・失効・移行規則を確定
5. **監査/運用強化:** BF-009 の snapshot / rules version 方針を決定
