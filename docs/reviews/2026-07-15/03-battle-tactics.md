# バトル・戦術・メカ能力 仕様実装監査

- 監査日: 2026-07-15
- 対象仕様:
  - `docs/03_mech_generation_and_stats.md`
  - `docs/04_tactics.md`
  - `docs/05_team_and_battle.md`
  - `AGENTS.md` の決定性・公平性・TDD 不変条件
- 対象実装・テスト: `src/photo_mecha_battle/` と `tests/` のうち、メカ能力、戦術、バトル、永続ログ、課金境界、関連 API
- 方式: 仕様・実装・テストの静的横断監査。既存ファイルを変更しない制約を守るため、pytest は実行せず、テストコードの受入基準を直接監査した。

## 監査カバレッジ

- [x] `docs/03`: 型推定、特徴量範囲、情報量スコア、型別基礎値、加算式、品質ペナルティ、キャップ、性能と見た目の分離
- [x] `docs/04`: スロット構造、先勝ち評価、EN 不足フォールスルー、基本行動、全条件、全行動、プリセット、課金非依存
- [x] `docs/05`: チーム位置、ターゲット、単一 PRNG、ターン、行動順、EN、ダメージ、乱数、クリティカル、型相性、公開情報、構造化ログ、保存
- [x] `AGENTS.md`: 同一 seed 再現性、評価順、フォールスルー、基本行動退避、ダメージ式、情報量境界、情報非対称、Entitlement 非依存
- [x] 実装裏取り: `features.py`, `mech_stats.py`, `tactics.py`, `tactics_serde.py`, `battle.py`, `battle_log_serde.py`
- [x] 統合経路裏取り: `api/app.py`, `api/game_store.py`, `api/database.py`, `api/store.py`
- [x] テスト裏取り: `test_battle*.py`, `test_damage_scaling.py`, `test_tactics*.py`, `test_mech_stats.py`, `test_form_inference.py`, `test_battle_log_serde.py`, `test_phase2.py`

## 総括

Finding は **13 件**（High 6、Medium 7）。内訳は **実装バグ 10 件、仕様バグ 3 件**である。

数式・型相性・プリセット本体は概ね仕様と一致する。一方、公平性境界では、他ユーザーの機体・戦術を自チームへ組み込める参照所有権欠落と、非公開戦術を無認証取得できる API がある。また、EN を払えない基本行動がそのまま実行されるため、任意の高コスト行動を無料の fallback にできる。

決定性について、同一プロセス・同一コード・同一入力の再実行は決定的である。しかし、乱数消費順を固定するゴールデンテストと、入力スナップショット・入力ハッシュ・ルール版を伴う永続リプレイ情報がないため、変更をまたぐログ再現性は保証できない。

## Finding 一覧

### BT-001 — 他ユーザーの機体・戦術をランク戦チームへ組み込める

- **重大度**: High
- **分類**: 実装バグ
- **実装箇所**:
  - `src/photo_mecha_battle/api/app.py:211-224` — 位置だけを検証して任意の `mech_id` / `tactic_id` を保存
  - `src/photo_mecha_battle/api/app.py:494-499` — 作成者の認証はするが参照資産の所有者を検証しない
  - `src/photo_mecha_battle/api/game_store.py:426-441` — ID から機体・戦術を所有者条件なしでロード
- **仕様節**:
  - `docs/05_team_and_battle.md`「チーム編成」「バトル基本方針」
  - `docs/05_team_and_battle.md`「戦術 AI が参照できる情報」
  - `AGENTS.md:48`「サーバー権威」
- **根拠**: チーム作成者の `user_id` と、DB の mech/tactic 行が持つ `user_id` を比較する処理がない。
- **具体的失敗シナリオ**: 攻撃者が別ユーザーの機体 ID と戦術 ID を得ると、それらを 3 枠に指定した自分名義のチームを作成できる。`POST /battles/ranked` はそのチームをサーバー側で正規ロードし、他人の能力値・戦術でレーティング戦を確定する。
- **推奨**: チーム作成・更新のトランザクション内で、全 mech/tactic の存在、所有者一致、位置一意性を検証する。別ユーザー資産混入を 403 で拒否する API テストを追加する。

### BT-002 — 非公開戦術の全スロットを無認証で取得・実行できる

- **重大度**: High
- **分類**: 実装バグ
- **実装箇所**:
  - `src/photo_mecha_battle/api/app.py:445-450` — `GET /tactics/{id}` に認証・所有権検証がなく payload 全体を返す
  - `src/photo_mecha_battle/api/app.py:474-490` — simulate も認証・所有権検証なし
  - `tests/test_phase2.py:92-126` — GET を認証ヘッダーなしで呼び、現状を追認
- **仕様節**:
  - `docs/05_team_and_battle.md`「戦術 AI が参照できる情報」— 相手の非公開戦術全文は不可
  - `AGENTS.md:27` — 非公開情報を参照しないことを間接的にも検証
- **根拠**: tactic 行には `user_id` があるが、GET/simulate 経路で利用されていない。
- **具体的失敗シナリオ**: 戦術 ID が共有 URL、ログ、BT-001 の資産 ID などから漏れた場合、第三者は認証なしで条件順、閾値、行動、fallback を取得し、対策チームを組める。
- **推奨**: GET/PUT/simulate を一貫して `require_user` + 所有者一致にする。公開共有機能が必要なら、非公開 ID と分離した明示的な公開コピーを設計する。第三者・未認証の 401/403 テストを追加する。

### BT-003 — EN 不足の高コスト fallback が無料で実行される

- **重大度**: High
- **分類**: 実装バグ
- **実装箇所**:
  - `src/photo_mecha_battle/battle.py:207-212` — EN 不足時に fallback へ差し替えるが、fallback の支払可否を再検証しない
  - `src/photo_mecha_battle/battle.py:253-270` — 差し替え後の攻撃を解決し、EN は `max(0, ...)` で 0 にするだけ
  - `tests/test_battle_extended.py:111-124` — 支払不能 fallback を許し、「EN不足」ログの存在だけを確認
- **仕様節**:
  - `docs/04_tactics.md`「判定方式」「行動候補」— EN コストを払えない行動は選択されない
  - `docs/05_team_and_battle.md`「EN」「戦術評価」— 不足時は基本行動へ退避
- **根拠**: `fallback_action=heavy_artillery` のような入力も許可され、二度目の affordability check がない。
- **具体的失敗シナリオ**: EN 0 の機体が fallback に重砲撃（コスト 40、威力 1.60）を設定すると、毎ターン EN 0 のまま重砲撃できる。通常攻撃 fallback のユーザーより明確に有利になる。
- **推奨**: 仕様決定 BT-004 後、(A) fallback を EN 0 の基本攻撃だけに制限する、または (B) 支払不能 fallback を `normal_attack` へ最終退避する。無料実行を期待する現テストは修正し、実行 action と EN 消費も検証する。

### BT-004 — fallback 自体が支払不能な場合の契約が未定義

- **重大度**: Medium
- **分類**: 仕様バグ
- **仕様箇所**:
  - `docs/04_tactics.md:24-39`「戦術セットの構造」「判定方式」
  - `docs/04_tactics.md:85-109`「行動候補」
  - `docs/05_team_and_battle.md:167-181`「戦術評価」
- **実装裏取り**:
  - `src/photo_mecha_battle/tactics.py:107-122` — fallback に任意の `ActionType` を許可
  - `src/photo_mecha_battle/api/app.py:141-144` — API も任意の action を許可
- **矛盾**: 「fallback は必ず実行」と「EN コストを払えない行動は選択されない」が、fallback に高コスト行動を選べる現スキーマでは同時に成立しない。
- **具体的失敗シナリオ**: EN 5、fallback が sniper_shot（コスト 35）のとき、無料実行、無行動、通常攻撃への再退避のどれが正しいか仕様から決められず、クライアントごとに異なる検証を実装し得る。
- **推奨**: **A（推奨）**: fallback は `normal_attack` / `normal_shot` / `normal_shell` など EN 0 の基本攻撃に限定する。**B**: 任意 action を許し、支払不能時の最終 action を別途一意に定義する。仕様、API バリデーション、テストを同時更新する。

### BT-005 — 保存済みバトルから同一入力を復元できない

- **重大度**: High
- **分類**: 実装バグ
- **実装箇所**:
  - `src/photo_mecha_battle/api/database.py:341-375` — seed、team ID、結果、ログは保存するが、機体能力・戦術 payload のスナップショット、入力ハッシュ、ルール版がない
  - `src/photo_mecha_battle/api/database.py:380-396` — 取得結果にも入力・版情報がない
  - `src/photo_mecha_battle/api/game_store.py:355-357` — 戦術は同じ ID の payload を上書き更新する
- **仕様節**:
  - `docs/05_team_and_battle.md`「バトル基本方針」— 同一 seed・同一入力でログまで完全再現
  - `docs/05_team_and_battle.md`「ダメージ式」— 同一式・定数内のみ再現
  - `AGENTS.md:18,126` — 完全一致、再現失敗時の seed・battle_id・入力ハッシュ
- **根拠**: 保存ログ自体は正史として閲覧できるが、「同一入力」の再構築材料が保存されていない。
- **具体的失敗シナリオ**: バトル後に参加チームの戦術を同じ tactic ID のまま更新すると、保存 seed と現在チームを再シミュレーションしても別ログになる。どの入力が違ったかを入力ハッシュで判定できない。
- **推奨**: battle 作成時に canonical な両チーム機体能力・form・位置・戦術 payload、battle rules version、input hash を保存する。保存ログ閲覧と再シミュレーション検証を分け、再現結果のハッシュ一致テストを追加する。

### BT-006 — 乱数消費順を固定するゴールデンテストがない

- **重大度**: Medium
- **分類**: 実装バグ（テスト欠落）
- **実装・テスト箇所**:
  - `src/photo_mecha_battle/battle.py:135` — 1 個の `random.Random(seed)` を使用
  - `src/photo_mecha_battle/battle.py:386-408` — 回避、乱数幅、クリティカルの順で可変回数消費
  - `tests/test_battle.py:7-31`
  - `tests/test_damage_scaling.py:201-216`
- **仕様節**:
  - `docs/05_team_and_battle.md`「バトル基本方針」— 乱数消費順序も仕様の一部
  - `AGENTS.md:18,20`
- **根拠**: 現テストは同じ実装を同じ seed で 2 回動かして formatted log を比較するだけで、期待される乱数列・構造化ログ・結果全体のゴールデン値を固定しない。
- **具体的失敗シナリオ**: デバッグ用に `rng.random()` を 1 回追加しても、2 回の実行は互いに一致するためテストは通る。しかし以後の全ダメージ・回避・クリティカルがずれ、既存 seed の再現結果が変わる。
- **推奨**: 代表バトルについて seed、入力 payload、`BattleResult` 全体、構造化ログ JSON のゴールデンを固定する。回避成立・不成立、範囲攻撃、クリティカルを含む複数 fixture を用意する。

### BT-007 — ダメージ式の複合倍率と乱数境界がテストで固定されていない

- **重大度**: High
- **分類**: 実装バグ（TDD 不変条件未充足）
- **実装・テスト箇所**:
  - `src/photo_mecha_battle/battle.py:389-408` — ダメージ式本体
  - `tests/test_battle_extended.py:134-158` — 貫通テストの `defended < pierce or defended <= pierce` は実質 `<=` で、1.15 を固定しない
  - `tests/test_battle_extended.py:174-187,301-310` — 追撃・迎撃も順序または正値だけ
  - `tests/test_damage_scaling.py:45-66,158-180` — K と型相性は正確に固定済み
- **仕様節**:
  - `docs/05_team_and_battle.md`「ダメージ式」「行動特効」「型相性」
  - `AGENTS.md:20,26` — 倍率・式・乱数範囲を小ケースで固定
- **未固定項目**: 防御 0.6、位置の割算、命中重視 1.10、貫通 1.15、迎撃 1.10、追撃 0.85、RandomRange の引数 0.9/1.1、回避境界 35%、クリティカル境界と倍率 1.2 の厳密値。
- **具体的失敗シナリオ**: 防御倍率を 0.6 から 0.5、乱数幅を 0.9–1.1 から 0.8–1.2 に誤変更しても、現行のログ確認・大小比較中心のテストの多くは通り、ランク戦バランスだけが変わる。
- **推奨**: 1 テスト 1 補正で他倍率を 1.0 に固定し、式の整数切り捨て結果を exact assert する。記録型 RNG で `uniform(0.9, 1.1)` と random 呼出順も検証する。

### BT-008 — 条件 kind ごとの必須 threshold と型を API が検証しない

- **重大度**: High
- **分類**: 実装バグ
- **実装箇所**:
  - `src/photo_mecha_battle/api/app.py:135-144` — 全 condition へ共通の nullable union 型を使用
  - `src/photo_mecha_battle/api/app.py:195-208` — kind と threshold の対応検証なし
  - `src/photo_mecha_battle/battle.py:309-326` — 実行時に `float()` / `int()` 変換
- **仕様節**:
  - `docs/04_tactics.md`「条件候補」— kind ごとにパーセント、EN 値、体数、form、threshold なしを区別
  - `AGENTS.md:19,41` — 境界・エラーパスを含む TDD
- **具体的失敗シナリオ**: `self_hp_below` に threshold `null` または `"abc"` を保存でき、ランク戦の手番で `float(None)` / `float("abc")` が発生してバトル API が 500 になる。`target_form` に threshold なしなら、エラーにならず永遠に不成立になる。
- **推奨**: condition を discriminated union にし、kind ごとに threshold の必須性・型を API 保存時に検証する。不正 tactic は 422 で拒否し、実行時例外を発生させない。

### BT-009 — condition threshold の許容範囲が仕様化されていない

- **重大度**: Medium
- **分類**: 仕様バグ
- **仕様箇所**:
  - `docs/04_tactics.md:62-75`「条件候補」
- **実装裏取り**:
  - `src/photo_mecha_battle/api/app.py:135-144`
  - `src/photo_mecha_battle/battle.py:309-326`
- **問題**: パーセントの 0–100、EN の 0–最大値、敵数の 1–3、整数限定か否かが定義されていない。
- **具体的失敗シナリオ**: HP threshold 1000% は常時成立、-1% は生存中に成立しない。敵数 0 は常時成立する。UI と API が別々の範囲を採用すると、保存可能だが再編集不能な戦術が生じる。
- **推奨**: 各 kind に型、下限、上限、端点の包含、刻みを定義する。推奨は HP 0–100 の整数、EN 0–200 の整数、敵数 1–3 の整数、固定条件は threshold 禁止。

### BT-010 — デモバトル API は位置重複を受理する

- **重大度**: Medium
- **分類**: 実装バグ
- **実装箇所**:
  - `src/photo_mecha_battle/api/app.py:611-628` — 枠数 3 のみ検証し、front/middle/back の集合を検証しない
  - 対照: `src/photo_mecha_battle/api/app.py:211-214` — 永続チーム経路は位置集合を検証
- **仕様節**:
  - `docs/05_team_and_battle.md`「チーム編成」— 前衛・中衛・後衛各 1 体、違反は API 400
- **具体的失敗シナリオ**: `POST /battles` に front を 3 件送ると受理され、3 機すべてが前衛攻防補正と同一ターゲット優先度を持つ仕様外バトルになる。
- **推奨**: `POST /teams` と同じ集合検証を共通 validator に抽出し、重複・欠落位置を 400/422 で拒否する。

### BT-011 — generic な先勝ち評価を固定するテストがない

- **重大度**: Medium
- **分類**: 実装バグ（テスト欠落）
- **実装・テスト箇所**:
  - `src/photo_mecha_battle/battle.py:281-293` — 実装は tuple 順に評価して最初を返す
  - `tests/test_battle_extended.py:86-108` — turret の防御到達性のみ
  - `tests/test_battle_extended.py:313-327` — 支払不能スロットの skip は確認済み
- **仕様節**:
  - `docs/04_tactics.md`「判定方式」「先勝ち評価とスロット順序」
  - `AGENTS.md:19`
- **具体的失敗シナリオ**: 将来 `_choose_action` を集合化・優先度ソートするリファクタで、二つの条件が同時成立した際に slot 2 が選ばれても、turret 固有テストと単一スロットテストは通り得る。
- **推奨**: slot 1 と slot 2 が同時成立し、異なる action を持つ最小 fixture で slot 1 を exact assert する。slot 1 支払不能時に slot 2、全不成立時に fallback も同じ fixture 群で固定する。

### BT-012 — Entitlement 有無で戦闘能力が不変であることをテストしていない

- **重大度**: Medium
- **分類**: 実装バグ（TDD 不変条件未充足）
- **実装・テスト箇所**:
  - `src/photo_mecha_battle/api/game_store.py:501-509` — Entitlement キー定義
  - `tests/test_phase2.py:416-509` — 付与・同期だけを検証
  - `tests/test_revenuecat_webhook.py` — イベント反映だけを検証
- **仕様節**:
  - `docs/04_tactics.md`「条件候補」「行動候補」「中級者向けスロット編集」
  - `AGENTS.md:22,51` — Entitlement の有無でスロット数・条件・行動を変えない
- **現状確認**: `battle.py`, `tactics.py`, `mech_stats.py` に Entitlement 分岐はなく、現行挙動自体は公平である。
- **具体的失敗シナリオ**: 将来 `extra_tactic_slots` 実装時に「保存枠」を「ランク戦スロット数」と取り違えても、現在の課金テストは DB の active flag だけを見るため検出しない。
- **推奨**: 無課金・各 Entitlement 付与後で、catalog、4 スロット上限、同一 seed のランク戦入力と結果が不変である統合テストを追加する。

### BT-013 — 情報量・ステータスの極端入力とキャップが受入基準として固定されていない

- **重大度**: Medium
- **分類**: 仕様バグ
- **仕様箇所**:
  - `docs/03_mech_generation_and_stats.md`「情報量スコア」「ステータス算出式」「キャップ」
  - `AGENTS.md:21` — 重み付けと極端入力へのキャップをテスト
- **実装・テスト裏取り**:
  - `src/photo_mecha_battle/mech_stats.py:73-107` — 重み、式、10–200 clamp は仕様どおり
  - `tests/test_mech_stats.py:26-36` — 1 次元だけで重みを確認
  - `tests/test_mech_stats.py:53-57` — 品質差の大小だけを確認
  - `tests/test_form_inference.py:97-110` — 0/1 境界は form のみ
- **問題**: 現係数では有効な 0.0–1.0 入力から全ステータスが 10 または 200 に到達せず、仕様にある「極端入力へのキャップ」を公開経路で観測する受入ケースが定義できない。
- **具体的失敗シナリオ**: 将来係数を増やして 200 を超える値が初めて発生した際、clamp の削除、ペナルティ適用順、切り捨て順が変わっても、現在の中間値・大小比較テストでは境界回帰を見逃す。
- **推奨**: 全 0、全 1、`capture_quality=0.5` の直前・一致・直後について全 7 ステータスの exact 値を仕様表とテストに追加する。キャップを将来安全弁とするならその旨を明記し、`_clamp(9/10/200/201)` の単体テストも置く。

## 正常確認事項

1. **同一 seed の局所決定性**: `battle.py:135` はバトルごとに単一の `random.Random(seed)` を生成し、グローバル乱数を使っていない。
2. **入力オブジェクトの保護**: `battle.py:136-137,167-175` はチームを戦闘用に clone し、呼出元の HP/EN を変異させない。
3. **行動順**: `battle.py:182-195` は SPD 降順、team ID、position ID の順で仕様どおり決定的に sort する。
4. **戦術の評価順・フォールスルー**: `battle.py:288-293` は保存順に走査し、支払不能スロットを skip している。BT-003 の fallback 再検証だけが欠ける。
5. **主ターゲット**: `battle.py:344-353` は front → middle → back の順で選択する。
6. **型相性**: `battle.py:23-30,411-416` は bird > beast > human > bird、1.15 / 0.90 / 1.00 と一致し、`test_battle_extended.py:127-131` で exact 値を確認している。
7. **ダメージ素点**: `battle.py:393-408` は `ATK × SkillPower × 60 / (DEF + 100)`、最低 1、整数切り捨てを実装し、`test_damage_scaling.py:45-66` が基準例 32 を固定している。
8. **型相性込みの exact damage**: `test_damage_scaling.py:158-180` は 1.15 / 0.90 適用後の整数値を固定している。
9. **行動プロフィール**: `battle.py:51-69` の威力・EN コスト・対象数は `docs/04` の表と一致する。
10. **プリセット**: `tactics.py:153-217` は `docs/04` の 5 プリセットと一致し、turret の shadowing は除去済み。
11. **特徴量範囲**: `features.py:26-29` は全 11 次元を 0.0–1.0 に制限する。
12. **情報量スコア**: `mech_stats.py:6-14,73-82` の全重みは `docs/03` と一致し、総和は 1.0。
13. **ステータス式**: `mech_stats.py:16-23,89-107` の基礎値、加算、品質ペナルティ、clamp は `docs/03` と一致する。
14. **型推定の決定性**: `mech_stats.py:25-70` は式、`1e-9` tie、human → bird → beast の順を実装し、代表例・同点・0/1 境界テストがある。
15. **性能と見た目の分離**: 戦闘能力は `FeatureVector` から `derive_stats` で決まり、生成 art の pixel/prompt は `battle.py` / `mech_stats.py` に入力されない。
16. **戦闘中ノー LLM**: バトル・戦術選択経路に LLM または外部非決定 API 呼出しはない。
17. **課金分岐の非混入**: 現時点で `battle.py`, `tactics.py`, `mech_stats.py` は Entitlement を参照しない。
18. **サーバー seed**: `game_store.py:449-471` はランク戦 seed を `secrets.randbits` でサーバー生成し、クライアント seed を結果確定に使用しない。
19. **構造化ログ保存**: `battle_log_serde.py:17-66` と `database.py:341-396` は仕様の turn、actor、condition、action、damage events、note を保存・復元する。
20. **保存済みログの正史性**: ルール変更後も DB の `log_text` / `log_json` 自体は再計算されず保持される。BT-005 は保存済み表示ではなく再シミュレーション可能性の問題である。

## 推奨対応順

1. BT-001、BT-002 を同時に修正し、資産所有権と非公開戦術境界を閉じる。
2. BT-004 を決定してから BT-003 を修正し、無料高コスト fallback を禁止する。
3. BT-008、BT-009、BT-010 で API 境界を固定し、仕様外入力による 500・仕様外バトルをなくす。
4. BT-005、BT-006 で canonical input、rules version、hash、乱数ゴールデンを導入する。
5. BT-007、BT-011、BT-012、BT-013 の TDD 欠落を小さな単体ケースで埋める。
