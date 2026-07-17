# CLAUDE.md — Photo Mecha Battle

グローバルの `~/.claude/CLAUDE.md` はそのまま適用する。本ファイルはこのプロジェクト固有の差分のみを定義する。

プロジェクト固有のエージェントルールの正本は [`AGENTS.md`](AGENTS.md) にある。実装前に必ず参照すること。特に以下は重要なので本ファイルにも明記する。

## Git ブランチ運用

- **`main`**: リリース相当の安定ブランチ。直接コミットしない。`develop` からの計画的なマージのみで更新する。
- **`develop`**: 開発の統合ブランチ。新規の feature ブランチは必ず `develop` から切る（`main` からは切らない）。
- **`feature/<topic>`**: 機能・修正単位で作成し、`develop` に向けて PR を作成する。
  - PR のテスト（`python -m pytest`、カバレッジ C0 90%/C1 80%）が通っていれば、レビュー待ちにせず **ノールックでマージしてよい**（`develop` 向けに限る）。
  - マージ後は原則 feature ブランチを削除し、次の feature を切る際は改めて最新の `develop` から分岐する。
- **`develop` → `main`**: リリースタイミングなど、まとまった単位で計画的に PR・マージする。ノールックマージの対象外。

その他の仕様・テスト方針・不変条件・チェックポイントは [`AGENTS.md`](AGENTS.md) を参照。

## 開発コマンドの操作知識

- **テスト実行**: 全体は `python -m pytest`。単一ファイルのデバッグ実行は `-p no:cov -o addopts=""` が必須（素のままだとカバレッジゲートが全体基準で誤発動し、`--no-cov` でも回避できない）。詳細・実測根拠は @.claude/rules/testing.md
- **サーバー起動・実地確認**: 手順は `.claude/skills/run/SKILL.md`（`/run` で参照）。API 疎通確認は curl ではなく Python スクリプトで行う。
