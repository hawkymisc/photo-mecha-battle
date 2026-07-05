# テスト実行 — 実測済みの落とし穴

方針（何をテストするか・TDD 優先領域）は [`AGENTS.md`](../../AGENTS.md) が正本。本ファイルは**実行コマンドの操作知識**のみを扱う。

## コマンド

| 目的 | コマンド |
|---|---|
| 全体実行（merge 判定はこれのみ） | `python -m pytest` |
| 単一ファイル / 単一テストのデバッグ実行 | `python -m pytest tests/test_X.py -p no:cov -o addopts=""` |

## カバレッジゲートの挙動（2026-07-05 実測）

`tests/conftest.py` の `pytest_sessionfinish` が `coverage.json` を読み、C0 90% / C1 80% 未満なら**テストが全部パスしていても exit 1** にする。

- **部分実行は素のままだと必ず失敗する**: `python -m pytest tests/test_models.py` → 2 passed でも `C0 40.2% < 90%` で失敗（カバレッジは常にパッケージ全体基準のため）。
- **`--no-cov` では回避できない**: cov プラグイン自体は登録されたままなのでゲート判定 `hasplugin("_cov")` が真になり、しかも**前回実行の stale な `coverage.json`** を読んで誤発動する。
- 正しい回避は `-p no:cov -o addopts=""`（プラグインごと無効化 + `pyproject.toml` の `--cov` 系 addopts を空に上書き）。
- `--no-cov` や `-p no:cov` を merge 判定に使わない（AGENTS.md のカバレッジ基準）。最終確認は必ず素の `python -m pytest`。

## テスト環境の前提

- `fresh_game_store`（autouse fixture）が各テストに in-memory SQLite + tmp media dir を注入する。テスト間で状態は残らない。
- 管理系エンドポイントのシークレットは conftest が固定値を環境変数に設定する:
  - `PMB_ADMIN_TOKEN` = `test-admin-secret`（`POST /billing/entitlements` 用）
  - `PMB_REVENUECAT_WEBHOOK_SECRET` = `test-revenuecat-secret`（RevenueCat Webhook 用）
- 認可系のテストは `tests/test_phase2.py` のマトリクス形式（未認証 401 / 第三者 403 / 当事者 200）に倣う。
