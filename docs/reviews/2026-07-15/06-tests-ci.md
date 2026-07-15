# テスト・CI・品質ゲート監査

- 監査日: 2026-07-15
- 対象: `pyproject.toml`、`tests/**`、`clients/android/**`、`clients/ios/**`、`.github/workflows/**`、カバレッジ設定
- 基準: `AGENTS.md` の C0 90% / C1 80%、TDD、決定性、戦術評価、公平性、API テスト方針
- 総合判定: **部分適合**
- Findings: **7件（High 2 / Medium 4 / Low 1）**

## エグゼクティブサマリー

ローカルの標準コマンド `python -m pytest` は 193 テストすべて成功し、C0 97.1631% / C1 89.3013% で規定値を満たした。バトルの seed 固定、戦術スロット順、EN 不足時のフォールスルー、ダメージ式、情報量スコア、API エラー、共有ゴールデンフィクスチャには具体的な回帰テストがある。

一方、GitHub Actions に Python ジョブが存在せず、この合格結果と C0/C1 閾値は PR の自動 merge gate になっていない。また、AGENTS.md が明示する「Entitlement の有無で戦闘能力が変わらないこと」の比較テストがなく、完全な BattleResult の決定性と戦術評価の非公開情報非依存も十分には固定されていない。

## 実行コマンドと結果

### 1. 作業ツリー確認

```text
git status --short --branch
```

結果: exit 0。既存ブランチ `feature/docs-environments-design` 上に、監査前から `CLAUDE.md`、`clients/android/README.md`、`scripts/android_dev.sh` の未コミット変更があった。監査では変更していない。

### 2. Python 全テスト（標準 merge 判定）

```text
python -m pytest
```

結果: **exit 0、193 passed、1 warning、4.98s**。

```text
collected 193 items
...
193 passed, 1 warning in 4.98s
TOTAL  1833 statements / 52 missed / 458 branches / 47 partial / 96% displayed total
Coverage JSON written to file coverage.json
```

警告:

```text
tests/test_diag_mech_i2i.py::test_mvp_stylize_baseline_is_reproducible_for_fixed_seed
ResourceWarning: unclosed database in <sqlite3.Connection ...>
```

### 3. coverage.json の規定式による再集計

```text
python -c 'import json; t=json.load(open("coverage.json"))["totals"]; print("covered_lines={} num_statements={} C0={:.4f}%".format(t["covered_lines"], t["num_statements"], 100*t["covered_lines"]/t["num_statements"])); print("covered_branches={} num_branches={} C1={:.4f}%".format(t["covered_branches"], t["num_branches"], 100*t["covered_branches"]/t["num_branches"]))'
```

結果: exit 0。

```text
covered_lines=1781 num_statements=1833 C0=97.1631%
covered_branches=409 num_branches=458 C1=89.3013%
```

判定:

- C0: 97.1631% >= 90% — **PASS**
- C1: 89.3013% >= 80% — **PASS**

補足: 同集計の初回試行は、ワンライナー内の f-string の引用符エスケープ誤りで `SyntaxError`（exit 1）となった。上記の `.format()` 版に直して成功しており、テストまたは対象コードの失敗ではない。

### 4. Android / iOS 軽量環境確認

```text
python --version
java -version
command -v swift >/dev/null 2>&1 && swift --version || echo SWIFT_NOT_FOUND
test -x clients/android/gradlew && echo GRADLEW_EXECUTABLE || echo GRADLEW_NOT_EXECUTABLE
```

結果: exit 0。

```text
Python 3.13.11
java: command not found
SWIFT_NOT_FOUND
GRADLEW_EXECUTABLE
```

判断: Android は Gradle wrapper 自体は実行可能だが Java 17 がなく、iOS は Swift toolchain がない。監査のためだけに JDK / Swift / Android 依存を導入するのは環境変更とダウンロードコストが大きいため、`./gradlew :core:test` と `swift test` は実行せず、テストコード・ビルド設定・CI 定義の静的確認に限定した。

### 5. 監査対象の既存差分確認

```text
git diff -- .github/workflows pyproject.toml tests clients/android/core clients/ios/PhotoMechaCore
```

結果: exit 0、差分なし。以下の所見は監査開始時点の対象コードに対するもの。

## Findings

### TCI-001 — Python テストと C0/C1 が CI merge gate になっていない

- 重大度: **High**
- 根拠: `.github/workflows/android.yml:1-30`、`.github/workflows/ios.yml:1-40`、`pyproject.toml:22-32`
- 事実: workflow は Android と iOS の2本のみで、`python -m pytest` を実行する job がない。リポジトリ検索でも workflow 内の `pytest` / `coverage` は0件だった。
- 影響: Python 実装・テスト・カバレッジを壊す PR が、GitHub Actions 上では検出されない。`AGENTS.md:30-42` が merge blocker と定義する C0 90% / C1 80% は、開発者がローカルで標準コマンドを実行するという運用依存になっている。
- 推奨: Python 3.11 以上で依存をインストールし、**素の `python -m pytest`** を実行する backend workflow を追加する。少なくとも `src/**`、`tests/**`、`pyproject.toml`、workflow 自身の変更で起動し、PR の required check に設定する。

### TCI-002 — Entitlement 有無による戦闘能力不変の比較テストがない

- 重大度: **High**
- 根拠: `AGENTS.md:18-22`、`tests/test_phase2.py:416-521`、`src/photo_mecha_battle/api/limits.py:5-31`
- 事実: Entitlement テストは付与・認証・同期・生成クォータを検証しているが、同一チーム・戦術・seed について Entitlement 無効/有効の結果、戦術スロット数、条件、行動を比較していない。これは AGENTS.md が明示する課金境界の固定対象である。
- 影響: 将来 `premium_tactics` や `extra_tactic_slots` の分岐が戦闘経路へ混入しても、現在の suite では Pay to Win 回帰を直接検出できない。
- 推奨: 無課金と各既知 Entitlement 有効状態で同一のチーム・戦術・seed を実行し、BattleResult 全体、利用可能な戦術条件/行動、ranked のスロット制約が一致するパラメータ化テストを追加する。`generation_boost` だけは生成クォータ差を別テストで維持する。

### TCI-003 — カバレッジゲートが stale な coverage.json を参照できる

- 重大度: **Medium**
- 根拠: `tests/conftest.py:86-106`、`.claude/rules/testing.md:12-19`
- 事実: session finish hook は pytest-cov plugin の有無を見た後、作業ディレクトリ上の `coverage.json` をそのまま読む。レポートが今回の session で生成されたかは検証しない。既存文書にも `--no-cov` では stale report を読んで誤発動すると明記されている。
- 影響: 非標準実行で偽陽性・偽陰性が起こり、古い高カバレッジレポートで誤って合格と判断する余地がある。標準の `python -m pytest` は今回正しく新規レポートを生成しており、この実測結果自体は有効。
- 推奨: session 開始時に旧レポートを除去し、今回の coverage session 由来であることを確認してから閾値判定する。可能なら pytest-cov/coverage の実行中データから判定し、ファイルの鮮度に依存させない。merge 判定コマンドは引き続き一意に保つ。

### TCI-004 — 決定性テストが BattleResult 全体の完全一致を固定していない

- 重大度: **Medium**
- 根拠: `tests/test_battle.py:7-31`、`tests/test_damage_scaling.py:201-216`、`src/photo_mecha_battle/battle.py:72-114`
- 事実: 同一 seed のテストは winner、turns、`format_log()` を比較する。`format_log()` は `actor_team` と `DamageEvent.target_id` を文字列に含めないため、構造化 `log_entries` の一部が変わってもテストが通る。また、別プロセスでの再現性は検証していない。
- 影響: API が返す構造化ログだけが非決定的になった場合や、プロセス依存の順序が混入した場合に、AGENTS.md の「ログ・結果が完全一致」を満たさない回帰を見逃す。
- 推奨: 新しい入力オブジェクトで2回実行した `BattleResult` をシリアライズし、seed、winner、turns、各 TurnLogEntry、各 DamageEvent を完全比較する。加えて固定 fixture を別プロセスで実行し、正規化 JSON または hash の一致を確認する小さなテストを設ける。

### TCI-005 — 戦術評価が非公開情報に依存しないことの回帰テストがない

- 重大度: **Medium**
- 根拠: `AGENTS.md:24-28`、`src/photo_mecha_battle/battle.py:281-336`、`tests/test_battle_extended.py:213-245`
- 事実: 条件種別と公開戦闘状態の分岐テストはある。一方、公開状態を同一に保ったまま相手戦術、将来行動、seed などの非公開情報だけを変え、選択行動が不変であることを確認するテストはない。現行 `_choose_action` の引数には相手戦術・seed がなく設計上は良好だが、その境界はテスト仕様として固定されていない。
- 影響: 将来の機能追加で forbidden context が evaluator に渡されても、戦術の公平性回帰を直接検出できない。
- 推奨: 公開 BattleState fixture を戦術評価 API の唯一の入力境界として明示し、非公開情報が異なる2ケースで選択結果が同一になるテスト、または evaluator が非公開フィールドを受け取れない型/adapter の契約テストを追加する。

### TCI-006 — SQLite ResourceWarning が品質ゲートを通過している

- 重大度: **Medium**
- 根拠: `tests/test_diag_mech_i2i.py:13-33`、`pyproject.toml:22-25`、今回の `python -m pytest` 出力
- 事実: 全テストは成功したが、固定 seed の i2i 診断テスト実行中に `unclosed database` の ResourceWarning が1件出た。pytest 設定に warning を error 化する規定はない。
- 影響: 接続寿命の不備が継続的に見逃され、長時間プロセスや反復診断で file descriptor / lock / メモリ問題に発展しうる。警告の表示位置だけでは生成元 connection を一意に断定できないため、allocation traceback を有効にした切り分けが必要。
- 推奨: `PYTHONTRACEMALLOC=1` または warning traceback で connection の生成元を特定し、fixture/診断処理で明示的に close する。修正後は少なくとも `ResourceWarning` を CI で error にする。

### TCI-007 — モバイル側にカバレッジ・静的品質ゲートがない

- 重大度: **Low**
- 根拠: `clients/android/core/build.gradle.kts:12-28`、`clients/ios/PhotoMechaCore/Package.swift:13-19`、`.github/workflows/android.yml:15-30`、`.github/workflows/ios.yml:15-40`
- 事実: Android は core unit test と debug APK assemble、iOS は Swift Package test と simulator build を行うが、JaCoCo/xccov、lint、format、warning-as-error の閾値がない。なお AGENTS.md の C0/C1 は明示的に `photo_mecha_battle` Python package を対象としているため、これは C0/C1 違反ではなく品質上の残余リスクである。
- 影響: クライアントテストが少ないままでも green になり、API client、画像特徴量移植、エラー導線の未検証分岐が増えても可視化されない。
- 推奨: まず core module に限定して Android unit-test coverage と Swift Package coverage を計測・保存し、現状値を基準線にする。閾値導入は実測後に段階的に行い、アプリ UI/実機テストとは別 gate にする。

## 正常確認点

1. **C0/C1 設定は規定と一致**  
   `pyproject.toml:22-29` は package 全体に `--cov=photo_mecha_battle --cov-branch --cov-report=json` を設定し、`tests/conftest.py:11-12,96-106` は C0 90.0 / C1 80.0 を AGENTS.md と同じ式で判定する。今回の実測も両方 PASS。

2. **標準テスト suite は全件 green**  
   193件が成功し、skip / xfail はなかった。テスト検出先も `tests` に固定されている。

3. **バトルの基本決定性が固定されている**  
   `tests/test_battle.py:7-31` と `tests/test_damage_scaling.py:201-216` は、同一 seed で winner、turns、表示ログが一致することを確認する。実装も `src/photo_mecha_battle/battle.py:127-165` でローカル `random.Random(seed)` を使用している。

4. **戦術評価の主要仕様が小さなテストに分解されている**  
   `tests/test_tactics.py:14-56` はスロット数・順序到達性・fallback を、`tests/test_battle_extended.py:86-124,313-327` は条件優先順位、行動不能時のフォールスルー、基本行動退避を検証する。E2E だけに依存していない。

5. **ダメージ・型相性・境界値が仕様値で固定されている**  
   `tests/test_damage_scaling.py:45-216` は docs/05 の係数、現実的 stat 帯、上下限、型相性順序、引き分け、seed 決定性を検証する。

6. **情報量スコアと極端入力を検証している**  
   `tests/test_mech_stats.py:26-74` は docs の重み、品質影響、0..1 正規化拒否を確認する。`tests/test_golden_features.py:29-45` は共有画像 fixture と server 実装の一致、algo version、info score、form を固定する。

7. **API テスト方針に適合**  
   Python endpoint tests は FastAPI `TestClient`、Android は `MockWebServer`、iOS は `URLProtocol` stub を使用する。`tests/**` に curl / 外部実ネットワーク呼び出しはなく、認証・所有権・エラー・multipart 契約を再現可能なコードで検証している。

8. **モバイル共有ゴールデンテストが存在**  
   Android `GoldenFeaturesTest.kt:17-78` と iOS `GoldenFeaturesTests.swift:8-141` は `tests/golden/**` を共通正本として許容誤差内の parity を確認する。両 mobile workflow は shared fixture 変更でも起動する。

9. **モバイル CI は unit test と build を分離している**  
   Android は JVM core test + debug APK assemble、iOS は Swift Package test + simulator build を定義しており、実モデル推論や実機 E2E を必須 gate にしていないため、AGENTS.md の「実モデルを CI 必須にしない」と整合する。

## 結論

ローカルの Python suite とカバレッジ水準は健全で、テスト内容も仕様追跡性が高い。しかし現状は「良いローカルテスト」であって「強制された merge gate」ではない。最優先は Python workflow の追加、次に課金境界の不変性テスト、続いて完全な構造化 BattleResult の決定性テストである。
