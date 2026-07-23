# バックエンド API 静的レビュー

- 実施日: 2026-07-15
- 対象: `src/photo_mecha_battle/api/` を中心とするバックエンド実装と関連テスト
- 正本: `docs/07_platform_and_system.md`、`docs/09_lightweight_server_architecture.md`
- 補助参照: `docs/04_tactics.md`、`docs/05_team_and_battle.md`、`docs/06_monetization_and_fairness.md`、`docs/12_environments.md`
- 方法: 静的レビューのみ。既存コード・テストの変更およびテスト実行は行っていない。

## 総括

13 件の finding を確認した。

| 重大度 | 件数 |
|---|---:|
| Critical | 1 |
| High | 6 |
| Medium | 5 |
| Low | 1 |

最優先は、一般ユーザーが `POST /billing/sync` だけで有料 Entitlement を自己付与できる点、チーム編成時に参照リソースの所有権を検証せず他人のメカ・戦術でランク戦できる点、ランク戦の相手確保・戦績保存・レーティング更新がトランザクション化されていない点である。

## Findings

### BE-001 — クライアント申告だけで有料 Entitlement を自己付与できる

- 重大度: **Critical**
- 確信度: **High**
- file:line:
  - `src/photo_mecha_battle/api/app.py:702-708`
  - `src/photo_mecha_battle/api/game_store.py:517-527`
  - `tests/test_phase2.py:484-521`
- 対応仕様:
  - `docs/07_platform_and_system.md:201-204` — 課金状態をクライアントだけで確定しない
  - `docs/09_lightweight_server_architecture.md:78-80, 341-353` — 課金検証・Entitlement はサーバー最終判定
  - `docs/06_monetization_and_fairness.md:178-186` — Webhook を受け、クライアントだけを信用しない
- 再現/失敗シナリオ:
  1. 無課金ユーザーが通常の `X-User-Token` で `POST /billing/sync` に `{"active_entitlements":["generation_boost"]}` を送る。
  2. サーバーは RevenueCat API、署名済み購入情報、Webhook 保存状態のいずれも確認せず `generation_boost` を有効化する。
  3. `/users/quotas` は premium 上限 50/30 を返す。既存テストもこの自己付与を正常系として固定している。
  4. 空リストを送れば、Webhook で付与済みの権利もクライアントから失効できる。
- 推奨:
  - `/billing/sync` ではクライアントから Entitlement 名の配列を受け取らない。
  - RevenueCat のサーバー API を App User ID で照会して検証するか、Webhook 保存状態の再読込だけを行う。
  - 検証機構を実装するまで production では fail-closed にし、現在の正常系テストを「自己申告では付与不可」に反転する。

### BE-002 — チームが他ユーザーのメカ・戦術を参照できる

- 重大度: **High**
- 確信度: **High**
- file:line:
  - `src/photo_mecha_battle/api/app.py:211-224, 494-530`
  - `src/photo_mecha_battle/api/game_store.py:375-441`
  - `src/photo_mecha_battle/api/database.py:67-79, 252-298`
- 対応仕様:
  - `docs/07_platform_and_system.md:75-80` — 戦術・チームの所有権、他ユーザー資源の拒否
  - `docs/09_lightweight_server_architecture.md:69-80, 106-113` — 保存済み ID のみをサーバーが検証してバトル確定
- 再現/失敗シナリオ:
  1. 攻撃者が、BE-003 等で得た別ユーザーの `mech_id` / `tactic_id` を自分の `POST /teams` に設定する。
  2. 作成・更新処理は ID の存在も `user_id` も検証せず 200 を返して保存する。
  3. `POST /battles/ranked` はそのチームをロードし、被害者のメカ性能・戦術で攻撃者のランク戦を実行し、攻撃者のレーティングへ反映する。
  4. 存在しない ID もチーム作成時には成功し、出撃時に未処理 `ValueError` で 500 になる。
- 推奨:
  - チーム作成・更新を単一サービス関数へ集約し、6 個の参照すべてについて「存在」「呼出ユーザー所有」「重複可否」を保存前に検証する。
  - 違反は他ユーザー資源なら 403、不存在なら 404/422 とする。
  - クロスユーザー参照、存在しない参照、更新時差し替え、ランク戦までの負例テストを追加する。

### BE-003 — メカ・戦術詳細と戦術シミュレーションに認証・所有権検査がない

- 重大度: **High**
- 確信度: **High**
- file:line:
  - `src/photo_mecha_battle/api/app.py:403-418`
  - `src/photo_mecha_battle/api/app.py:445-450`
  - `src/photo_mecha_battle/api/app.py:474-491`
  - `tests/test_api_errors.py:45-46, 94-104`
  - `tests/test_phase2.py:92-126, 285-316`
- 対応仕様:
  - `docs/07_platform_and_system.md:49-57, 75-80`
  - `docs/09_lightweight_server_architecture.md:69-80, 236-246`
  - `AGENTS.md` の戦術テスト方針 — 相手戦術全文は非公開情報
- 再現/失敗シナリオ:
  - 未認証で `GET /mechs/{id}` を呼ぶと、永続メカでは `user_id`、確定 stats、art URL を取得できる。
  - 未認証で `GET /tactics/{id}` を呼ぶと、別ユーザーの戦術全文を取得できる。
  - 未認証で `POST /tactics/{id}/simulate` に任意の `mech_id` を組み合わせ、他人の資産を読み込んだシミュレーションを実行できる。
  - 関連テストはヘッダーなし 200 を正常系としており、401/403 分岐が存在しない。
- 推奨:
  - 3 エンドポイントすべてに `require_user` を追加し、DB 行の `user_id` と一致しなければ 403 にする。
  - シミュレーションでは tactic と mech の両方の所有権を検査する。
  - 未認証 401、第三者 403、所有者 200 の契約テストを資源ごとに追加する。

### BE-004 — 互換 capture/object API が実ユーザー画像を無認証で処理できる

- 重大度: **High**
- 確信度: **High**
- file:line:
  - `src/photo_mecha_battle/api/app.py:238-241, 270-295`
  - `src/photo_mecha_battle/api/game_store.py:93-118, 627-639`
  - `src/photo_mecha_battle/api/capture_pipeline.py:83-146`
  - `tests/test_mvp_capture.py:29-40`
  - `tests/test_form_inference.py:160-169, 207-216`
- 対応仕様:
  - `docs/07_platform_and_system.md:75-80` — ユーザー由来オブジェクトの所有権
  - `docs/09_lightweight_server_architecture.md:222-234` — 多段 API は CLI / 自動テスト / サーバー単体検証用
  - `docs/09_lightweight_server_architecture.md:341-353` — 不正対策の最終判定はサーバー
- 再現/失敗シナリオ:
  1. 他ユーザーの upload `capture_id` を知る第三者が、トークンなしで detect / segment を呼ぶ。
  2. 原画像を読み込み、crop・mask・`extracted_objects` を何度でも新規作成できる。
  3. object ID を知れば analyze で特徴量・品質情報を無認証取得できる。
  4. API は「デバッグ用」とされるが、production 環境で無効化するガードがなく、実 DB と実メディアを操作する。
- 推奨:
  - persisted capture/object を扱う経路には認証と capture 所有者検査を必須化する。
  - demo 用 in-memory 経路と実ユーザー経路を別ルーターに分離し、`PMB_ENV=production` では demo ルーターをマウントしない。
  - 未認証、第三者、所有者、production 無効化をテストする。

### BE-005 — メカ直登録が DB・ファイル・クォータを原子的に保存しない

- 重大度: **High**
- 確信度: **High**
- file:line:
  - `src/photo_mecha_battle/api/game_store.py:266-310`
  - `src/photo_mecha_battle/api/game_store.py:170-186`
  - `src/photo_mecha_battle/api/database.py:183-197, 440-465, 487-522, 545-562`
  - `src/photo_mecha_battle/api/image_storage.py:14-31`
- 対応仕様:
  - `docs/09_lightweight_server_architecture.md:93-104, 203-215` — 検証後に確定値を一体として保存し、拒否時はクォータ非消費
  - `docs/09_lightweight_server_architecture.md:316-324` — crop / feature / battle log の保存境界
- 再現/失敗シナリオ:
  - capture ファイル保存後に `save_capture` が失敗すると孤児ファイルが残る。
  - `save_capture` 成功後に crop/mask/object/mech のいずれかが失敗すると、200 は返らないのに途中まで DB とファイルが残る。
  - mech 保存後の `mechs_used` increment が失敗すると、メカは存在するがクォータ未消費になる。
  - 最後の `captures_used` increment が失敗すると、クライアントには 500 が返る一方、メカと mech quota は確定済みとなり、再試行で重複判定される。
  - テストは検証拒否が「最初の永続化より前」であるケースだけで、途中失敗の rollback を検証していない。
- 推奨:
  - DB 操作を一つの明示トランザクションにまとめ、Database の各 save/increment から個別 `commit()` を除く。
  - ファイルは一時パスへ書き、DB commit 後に atomic rename、失敗時に補償削除する。
  - 各保存点へ fault injection したテストで、孤児行・孤児ファイル・クォータ差分がないことを確認する。

### BE-006 — クォータと phash 重複判定が競合に弱く上限を超過できる

- 重大度: **High**
- 確信度: **High**
- file:line:
  - `src/photo_mecha_battle/api/game_store.py:221-251, 568-576`
  - `src/photo_mecha_battle/api/capture_pipeline.py:52-72`
  - `src/photo_mecha_battle/api/database.py:480-485, 545-562`
- 対応仕様:
  - `docs/06_monetization_and_fairness.md:50-63` — UTC 日次上限と 429
  - `docs/09_lightweight_server_architecture.md:91-113, 341-350` — phash、クォータはサーバー最終判定
- 再現/失敗シナリオ:
  - 残り 1 枠で 2 リクエストを並行送信すると、双方が `_ensure_*_quota()` の同じ usage を読み、双方が成功後に increment して上限 +1 になる。
  - 同一画像を並行送信すると、双方が `list_capture_hashes()` で未登録を確認してから別 capture として保存できる。
  - `daily_quotas` の increment 自体は SQL で加算されるが、「上限未満なら加算」の条件が同じ文・トランザクションにない。
  - テストは逐次呼出しのみで並行ケースがない。
- 推奨:
  - クォータは条件付き `UPDATE ... WHERE used < limit` またはトランザクション内の行ロック相当で予約し、更新行数 0 を 429 とする。
  - phash はユーザー単位の排他制御を加える。近似一致は単純 UNIQUE 制約にできないため、同一ユーザーの登録クリティカルセクションを直列化する。
  - 2 以上の並行リクエストによる上限境界・同一 crop テストを追加する。

### BE-007 — マッチ相手の確保とバトル・レーティング確定が非原子的

- 重大度: **High**
- 確信度: **High**
- file:line:
  - `src/photo_mecha_battle/api/app.py:552-608`
  - `src/photo_mecha_battle/api/game_store.py:443-499`
  - `src/photo_mecha_battle/api/database.py:316-339, 341-378`
- 対応仕様:
  - `docs/09_lightweight_server_architecture.md:136-155` — match 後にサーバーが両チームを読み込み、結果保存・レーティング更新
  - `docs/05_team_and_battle.md:251-268` — ランク戦結果とレーティングはサーバー確定、キュー済み最近接相手を選択
- 再現/失敗シナリオ:
  - `/battles/match` は相手 ID を返すだけで予約せず、`/battles/ranked` はその相手を使わず再検索する。この間に別ユーザーが同じ相手を取得・消費でき、表示された相手と実戦相手が変わる。
  - 複数リクエストが同じ queued team を同時選択し、同一相手を複数戦へ利用して複数回レーティング更新できる。
  - battle insert、A の rating、B の rating、各 dequeue が個別 commit のため、途中障害で「ログだけ保存」「片側 rating だけ更新」「キュー残留」が起きる。
  - 既存 PvP テストは単一スレッドの正常系のみ。
- 推奨:
  - match reservation（match ID、両 team ID、期限、状態）を永続化し、ranked はその予約 ID を消費する契約にする。
  - 相手 claim、battle 保存、両 rating 更新、dequeue を一つの DB トランザクションにまとめる。
  - 同一 reservation の再送には同じ結果を返す idempotency を設け、並行 claim・途中失敗テストを追加する。

### BE-008 — 戦術条件の threshold 契約を検証せず、不正な 200 または 500 になる

- 重大度: **Medium**
- 確信度: **High**
- file:line:
  - `src/photo_mecha_battle/api/app.py:135-145, 195-208, 439-466`
  - `src/photo_mecha_battle/tactics.py:65-68, 113-122`
  - `src/photo_mecha_battle/battle.py:302-322`
- 対応仕様:
  - `docs/04_tactics.md:55-75` — condition ごとの threshold 型・意味
  - `docs/07_platform_and_system.md:59-73` — 入力不正・検証拒否のエラー応答
- 再現/失敗シナリオ:
  - `target_form` に `"dragon"` を送ると `_build_tactic_set()` の `MechForm(...)` が未捕捉で 500 になる。
  - `self_hp_below` に `"abc"` または `null` を送ると作成時は 200 で永続化され、ランク戦時の `float(threshold)` で 500 になる。
  - 固定閾値条件に不要な値、HP/EN に負数や過大値を送っても保存される。
  - テストは列挙値とスロット数を中心にし、condition-threshold の組合せ行列がない。
- 推奨:
  - Pydantic の model validator で condition ごとに required/forbidden type と範囲を検証する。
  - target form は列挙値、HP は 0..100、EN はゲーム上限、残数は 1..3 等を明示する。
  - API 層で 422 に統一し、全 ConditionKind × 境界値 × 型不正の表駆動テストを追加する。

### BE-009 — 互換画像 API の不正入力が 4xx ではなく 500 になる

- 重大度: **Medium**
- 確信度: **High**
- file:line:
  - `src/photo_mecha_battle/api/app.py:244-267, 277-287`
  - `src/photo_mecha_battle/api/capture_pipeline.py:45-72, 99-146`
  - `src/photo_mecha_battle/vision/segmentation.py:17-32`
  - `tests/test_mvp_capture.py:29-98`
- 対応仕様:
  - `docs/07_platform_and_system.md:59-73` — 入力不正は 400/422
  - `docs/09_lightweight_server_architecture.md:203-215` — bbox 形式、画像デコード不能の契約
- 再現/失敗シナリオ:
  - `/captures/upload` に空ではない非画像 bytes を送ると PIL の `UnidentifiedImageError`/`OSError` が `ValueError` catch に入らず 500 になる。
  - `/captures/{id}/segment` の bbox に 3 要素を送ると unpack で `ValueError`、逆転・ゼロ面積では空 crop の `getpixel` 等が失敗し、いずれも未処理 500 になり得る。
  - direct `/mechs` の bbox には validator があるが、互換 API の `SegmentRequest` には同等の validator がない。
  - 関連テストは正常画像、重複、unsafe のみで、壊れた画像・bbox 負例がない。
- 推奨:
  - upload の画像 decode 例外を限定捕捉し、cause を保持して 400 に変換・ログ出力する。
  - bbox validator を共有モデル/関数に抽出し、両経路で同じ 422 契約を使う。
  - 3 要素、範囲外、逆転、ゼロ面積、NaN、壊れた画像を追加テストする。

### BE-010 — 画像サイズ無制限かつ async エンドポイント内で同期 CPU/IO を実行する

- 重大度: **Medium**
- 確信度: **High**
- file:line:
  - `src/photo_mecha_battle/api/app.py:244-254, 298-330, 370-381`
  - `src/photo_mecha_battle/api/game_store.py:206-310`
- 対応仕様:
  - `docs/09_lightweight_server_architecture.md:299-327` — 単一 API プロセス、画像アップロードと DB 書込がボトルネック
  - `docs/07_platform_and_system.md:19-26` — 非同期処理活用
- 再現/失敗シナリオ:
  - upload は `file.file.read()`、direct は `await crop_part.read()` でサイズ上限なしに全 bytes をメモリへ読む。
  - direct `/mechs` は `async def` のイベントループ上で PIL 解析、全画素走査、複数ファイル書込、同期 SQLite commit、art render を直接実行する。
  - 少数の巨大画像または複数同時登録でメモリ圧迫とイベントループ停止が起き、認証・ランキング等の無関係な API も待たされる。
  - サイズ上限、同時実行、応答性のテストがない。
- 推奨:
  - Content-Length と実読込 bytes の双方に上限を設け、超過を 413 とする。PIL の pixel count/decompression bomb も制限する。
  - CPU/同期 IO 部分を bounded thread pool へ移すか、エンドポイントを同期化して FastAPI の threadpool 管理に載せる。
  - 同時実行数制限と、大画像・複数並行時のメモリ/レイテンシテストを追加する。

### BE-011 — SQLite の参照整合性が実際には有効でない

- 重大度: **Medium**
- 確信度: **High**
- file:line:
  - `src/photo_mecha_battle/api/database.py:32-37, 42-136`
  - `src/photo_mecha_battle/api/database.py:252-298, 341-378`
- 対応仕様:
  - `docs/07_platform_and_system.md:82-195` — users / mechs / tactics / teams / battles 間のデータモデル
  - `docs/09_lightweight_server_architecture.md:69-80, 316-324` — 永続化はサーバー責務
- 再現/失敗シナリオ:
  - SQLite は既定で `PRAGMA foreign_keys=OFF` だが、接続後に有効化していないため、宣言済みの `mechs.user_id` 等も強制されない。
  - teams の mech/tactic IDs、battles の player/team IDs、capture/object 以外の多くは FK 宣言自体がない。
  - 削除・障害・直接 DB 操作・BE-002 の入力により孤児行を保存でき、PostgreSQL 移行時に初めて制約違反が顕在化する。
  - テストは不正参照の insert が失敗することを確認していない。
- 推奨:
  - 接続直後に `PRAGMA foreign_keys=ON` を設定し、有効値を検証する。
  - 全参照列へ仕様に沿った FK と必要な index を追加し、既存 DB は事前整合性検査付き migration にする。
  - 不正 user/mech/tactic/team/capture 参照を DB 層テストで拒否する。

### BE-012 — migration が任意の OperationalError を握り潰す

- 重大度: **Medium**
- 確信度: **High**
- file:line:
  - `src/photo_mecha_battle/api/database.py:138-148`
- 対応仕様:
  - `docs/07_platform_and_system.md:82-85` — 現行 SQLite スキーマを正として保持
  - `docs/12_environments.md:69-87, 127-136` — production 永続 DB と schema migration の安全性
  - プロジェクト Error Surfacing 規約 — production code の例外握り潰し禁止
- 再現/失敗シナリオ:
  - `ALTER TABLE` が「duplicate column」以外の DB lock、read-only、I/O、破損等で失敗しても `pass` する。
  - 起動は成功したように見え、後続の `INSERT ... art_url` や `log_json` で遅れて 500 になるため、根本原因と起動時点の文脈を失う。
  - migration failure のテストがない。
- 推奨:
  - `PRAGMA table_info` で列存在を先に確認し、必要な ALTER の失敗は cause 付きで起動失敗にする。
  - versioned migration を導入し、適用済み version と schema 検証を記録する。
  - read-only/lock/途中 migration の失敗テストを追加する。

### BE-013 — production 経路に関数内 import が残り fail-fast しない

- 重大度: **Low**
- 確信度: **High**
- file:line:
  - `src/photo_mecha_battle/api/app.py:611-617`
  - `src/photo_mecha_battle/api/game_store.py:312-323`
- 対応仕様:
  - プロジェクト Lazy Import Ban — production code の関数内 import 禁止、依存欠落は起動時 fail-fast
- 再現/失敗シナリオ:
  - `POST /battles` を初めて呼ぶまで `Team` / `TeamSlot` の import 問題が表面化しない。
  - art 生成を初めて行うまで関数内 PIL import が評価されない。なお同モジュール冒頭ですでに PIL を import 済みで、この import は冗長でもある。
  - lint で PLC0415 を有効化していなければ再発する。
- 推奨:
  - すべて module top-level import へ移し、ruff `PLC0415` を CI 対象にする。

## 問題なしと確認した点

- `X-User-Token` の欠落・無効は `require_user` で 401 に統一され、`/auth/me` 等の保護済み API では関連テストがある（`app.py:49-59`、`tests/test_phase2.py:319-321`）。
- ランク戦 seed は `secrets.randbits` でサーバー生成され、クライアント seed を無視する。応答と保存値の一致もテストされている（`game_store.py:449-470`、`tests/test_phase2.py:153-181`）。
- `GET /battles/{id}` は認証を要求し、対人戦は当事者のみ、CPU 戦は player A のみに制限する 401/403 テストがある（`app.py:642-658`、`tests/test_phase2.py:336-385`）。
- direct `/mechs` は `algo_version`、bbox、feature 11 次元、0..1 範囲、サーバー再計算差分、最小解像度、空 mask、単色、phash、unsafe 判定を実装し、主要な拒否分岐がテストされている（`app.py:298-367`、`game_store.py:206-310`、`tests/test_mech_direct_registration.py`）。
- クライアント送信 `form` と stats はランク戦の確定値として採用せず、型・stats をサーバー側で計算している（`app.py:101-118, 370-395`、`game_store.py:170-186, 593-602`）。
- バトルログは整形テキストに加えて構造化 JSON を保存・返却し、旧レコードのフォールバックもテストされている（`database.py:341-396`、`tests/test_database.py:17-71`）。
- RevenueCat Webhook とデモ Entitlement API は共有シークレット未設定時に fail-closed であり、未知 Entitlement キーのフィルタ、event ID 冪等性、付与/失効の主要分岐にテストがある（`app.py:62-85, 685-730`、`game_store.py:501-566`、`tests/test_revenuecat_webhook.py`）。
- Entitlement によってランク戦の戦術スロット数・条件・行動を増やす分岐は見つからず、クォータ拡大は `generation_boost` に限定されている（`limits.py:5-31`）。

## テスト上の主な空白

個別 finding に記載したものに加え、横断的には以下が不足している。

- すべてのユーザー所有リソースについて、未認証 401 / 第三者 403 / 所有者 200 の共通契約テスト
- team 内 mech/tactic の存在・所有権を組み合わせた負例
- quota 境界、phash、match claim、Webhook idempotency の並行実行
- DB・ファイル・quota・rating 更新の各地点へ障害を注入する rollback テスト
- malformed image、巨大画像、decompression bomb、bbox、戦術 threshold の表駆動負例
- debug/compat ルーターが production で無効になることの環境テスト
