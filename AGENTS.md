# Agent Rules — Photo Mecha Battle

グローバルハーネス（`~/.claude/CLAUDE.md`、`dotfiles/codex/AGENTS.md`、`~/.claude/rules/`）はそのまま適用する。本ファイルはゲーム開発に落とし込む**プロジェクト固有の差分**のみを定義する。

## 仕様の唯一の情報源

- ゲーム仕様は [`docs/00`](docs/00_root_overview.md)〜[`09`](docs/09_lightweight_server_architecture.md) が正本（一覧は [docs/00 の仕様書構成](docs/00_root_overview.md#仕様書構成)）。実装前に該当ドキュメントを読み、矛盾があればコードより先に仕様を直す。
- **システム分担・API の主経路**は [`docs/09_lightweight_server_architecture.md`](docs/09_lightweight_server_architecture.md) を正とする（旧 [`docs/07`](docs/07_platform_and_system.md) のサーバー集中型構成は 2026-07-02 に廃止・統合済み。[`docs/07`](docs/07_platform_and_system.md) は認証・データモデル・API 共通規約を担当）。
- [`docs/08_mvp_and_roadmap.md`](docs/08_mvp_and_roadmap.md) の「MVP では実装しないもの」はスコープ外。着手するにはユーザー明示の GO が必要。
- 設計判断を変えたら、同一セッション内で `docs/` 内の関連キーワードを grep し、上位の設計原則・下位の API 案の両方を整合させる（ハーネスの Document Consistency を `docs/` に適用）。

## TDD — 仕様をテストコードに書く

ハーネスの TDD 方針に従い、**再現性と公平性が仕様の中核**である領域を優先してテストする。

| 領域 | テストで固定すべき仕様 |
|---|---|
| バトルエンジン | 同一 `seed` + 同一入力でログ・結果が完全一致すること |
| 戦術評価 | スロット 1→N の順序評価、行動不能時のフォールスルー、基本行動への退避 |
| 型相性・ダメージ | [`docs/05`](docs/05_team_and_battle.md) の倍率・式。乱数範囲は seed 固定で検証 |
| 情報量スコア | [`docs/03`](docs/03_mech_generation_and_stats.md) の重み付け。極端入力へのキャップ |
| 課金境界 | Entitlement の有無で戦術スロット数・条件・行動が変わらないこと |

**テストの書き方**

- バトルは「1 ターンの条件成立 → 選択行動 → ダメージ解決」を小さなケースに分解する。E2E 一本に頼らない。
- 戦術は公開戦闘状態のフィクスチャを用意し、非公開情報（相手戦術全文、次行動、seed）を参照していないことを間接的にも検証する。
- ML / 画像生成はゴールデン画像＋許容誤差、またはモックアダプタで境界をテストする。実モデル推論を CI の必須ゲートにしない（Phase 0 検証スクリプトで扱う）。

## カバレッジ基準（merge ブロッカー）

`photo_mecha_battle` パッケージに対し、pytest + pytest-cov（`--cov-branch`）で以下を満たすこと。

| 指標 | 定義 | 閾値 |
|---|---|---|
| C0 | 命令（行）カバレッジ `covered_lines / num_statements` | **90% 以上** |
| C1 | 分岐カバレッジ `covered_branches / num_branches` | **80% 以上** |

- 実行: `python -m pytest`（`pyproject.toml` の `addopts` で JSON レポートを出力）
- 閾値チェック: [`tests/conftest.py`](tests/conftest.py) の `pytest_sessionfinish` が `coverage.json` を検証する
- 新規モジュール追加時は、エラーパス・境界条件を含めて閾値を維持する
- カバレッジ不足を `--no-cov` で回避して merge しない

## 実装の不変条件（コードレビュー・Coderabbit の追加観点）

グローバルの Code Review に加え、以下は **merge ブロッカー** とする。

1. **サーバー権威**: バトル結果・ランキング・課金状態の確定はサーバー側。クライアントのみの判定で権限を解放しない。
2. **戦闘中ノー LLM**: ランタイムのターン解決・ダメージ計算・戦術選択に LLM / 非決定的 API を呼ばない。自然言語戦術はコンパイル時のみ（Phase 3 以降）。
3. **性能と見た目の分離**: ステータス・スキルは `feature_vector` / `info_score` 等の分析値から算出。生成メカ画像のピクセルやプロンプトから戦闘力を導かない。
4. **Pay to Convenience**: `Entitlement` は保存枠・要約・装飾・戦術コンパイル導線に限定。条件候補・行動候補・ランク戦スロット数に課金分岐を入れない。
5. **ユーザー画像の扱い**: [`docs/02`](docs/02_photo_object_extraction.md) の安全性・不正対策（顔検出、perceptual hash、品質スコア）をスキップするショートカットを入れない。

## 不可逆操作のゲーム固有チェックポイント

ハーネスの Trust + Checkpoint に加え、以下は実行前に停止して trade-off を提示する。

| 操作 | リスク |
|---|---|
| 本番 DB の `battles` / `user_entitlements` 削除・上書き | 対戦記録・課金状態の喪失 |
| ユーザー画像バケットの一括削除 | 復元不能 |
| RevenueCat 商品・Entitlement 定義の変更 | 既存購入者の権限不整合 |
| バトル式・型相性・戦術 DSL の破壊的変更 | 過去ログとの再現不能、ランキングの不公平 |
| 生成 API の本番キーでの大量呼び出し | 課金発生 |

## 調査・診断（diagnosis.md のゲーム適用）

診断はコマンドの逐次実行ではなく **1 本のスクリプト** にまとめる。ゲームでよく使う軸:

```text
scripts/diag/
  diag_capture_pipeline.sh    # 検出→セグメント→品質スコア
  diag_battle_replay.sh       # seed + battle_id でログ再現
  diag_billing_entitlement.sh # RevenueCat CustomerInfo ↔ サーバー同期
  diag_device_perf.sh         # 端末での推論時間・発熱（Phase 0）
```

スクリプト出力には **再現手順**（入力 ID、seed、コミット hash）を含める。

## バグ管理のスコープ分類

ハーネスの 3-Step Escalation を使う際、Issue ラベル・PLAN 追記は領域で分ける。

| 領域 | 例 |
|---|---|
| `capture` | 検出漏れ、マスク品質、安全性フィルタ |
| `mech` | スコア納得感、型との不整合、生成失敗 |
| `tactics` | スロット優先順位、条件の誤評価、UI 編集 |
| `battle` | 再現不能、ログ欠落、型相性、行動順 |
| `billing` | Entitlement ずれ、復元失敗、Webhook 未着 |

現在タスクの領域外のバグは Handover 注意書きだけにせず、必ず Issue → PLAN → deferred 記載。

## フェーズ管理

- [`docs/08`](docs/08_mvp_and_roadmap.md) の Phase 0〜4 を PLAN の基準とする。タスク完了時は `✅` / `⚠️` / `🔲` を更新（ハーネスの project-management）。
- Phase を飛ばして Phase 3 機能（自然言語戦術、ログ要約）に入る場合は、縦切りループ（撮影→メカ→プリセット戦術→ダミーバトル→ログ）が Phase 1 相当で通っていることを先に確認する。

## PO レビュー — 何をユーザーに見せるか

ハーネスの PO Review 境界に従う。**動くかはエージェントが先に確認し、PO には意図・体験の判定だけを求める。**

| マイルストーン | PO に確認してもらうこと |
|---|---|
| Phase 1 縦切り | 撮影→抽出→メカ生成→プリセット選択→バトルログが一連で気持ちよく流れるか |
| 戦術編集 | 4 スロット編集が片手・短時間でできるか。ログの「条件成立理由」が理解できるか |
| 非同期 PvP | 結果とログが納得感あるか。負けた原因が戦術改善に繋がるか |
| Paywall | 「利便性のみ・戦闘性能は不変」の説明が誤解なく伝わるか |
| RevenueCat デモ | 購入・復元・Entitlement 解放がストアテスト環境で一通り動くか |

実機確認が必要な変更（カメラ、課金、バトル演出）では、シミュレータだけの検証を merge 条件にしない。

## ドキュメント更新タイミング

ハーネスの maintain-documents に従い、実装で判明したことは仕様へ還流する。

- 数値が確定したら（ダメージ式の係数、位置補正、品質閾値）→ 該当 `docs/0N_*.md` とテストを同時更新
- MVP 外に着手したら → [`docs/08`](docs/08_mvp_and_roadmap.md) の「未決事項」を減らすか、明示的に未決のまま残す理由を書く
- API・データモデルを実装したら → [`docs/07`](docs/07_platform_and_system.md) の案と実コードの差分を解消する

## エラーハンドリング

`~/.claude/rules/error-surfacing.md` を適用する。ゲーム固有の注意:

- 撮影・推論・生成の失敗は握り潰さず、ユーザー向けに「再撮影」「別オブジェクト選択」へ繋がるエラー種別を返す
- バトル再現失敗は `seed`・`battle_id`・入力ハッシュをログに残す
- 課金エラーはストア側メッセージと RevenueCat のエラーコードを両方記録する

## サブエージェント・並列作業

Task ツールで分割する場合の推奨境界:

```text
battle-engine   … 決定的シミュレーションのみ（IO なし）
tactics-dsl     … 条件・行動のパースと評価
capture-ml      … 検出・セグメント・特徴量（アダプタ境界を守る）
client-ui       … 画面・導線（仕様の UX 原則: 片手操作、短時間ループ）
billing         … RevenueCat ↔ サーバー同期
```

サブエージェント成果物はコミット前に `git diff` で目視確認する（ハーネスの Team Agent Output Review）。特に **battle-engine と billing の境界** でクライアントのみの権限解放が混ざっていないか確認する。

## Git ブランチ運用

グローバルハーネスの Git 運用に加え、本プロジェクトでは以下を優先する。

- **`main`**: リリース相当の安定ブランチ。直接コミットしない。`develop` からの計画的なマージのみで更新する。
- **`develop`**: 開発の統合ブランチ。新規の feature ブランチは必ず `develop` から切る（`main` からは切らない）。
- **`feature/<topic>`**: 機能・修正単位で作成し、`develop` に向けて PR を作成する。
  - PR のテスト（`python -m pytest`、カバレッジ C0 90%/C1 80%）が通っていれば、レビュー待ちにせず **ノールックでマージしてよい**（`develop` 向けに限る）。
  - マージ後は原則 feature ブランチを削除し、次の feature を切る際は改めて最新の `develop` から分岐する。
- **`develop` → `main`**: リリースタイミングなど、まとまった単位で計画的に PR・マージする。ノールックマージの対象外（`AGENTS.md` の不可逆操作チェックポイントに準じ、必要なら trade-off を提示してから進める）。

## セッション終了時

開発モードで観察可能な成果物を変更したターンは、ハーネスどおり PO レビュー要否を判定する。実機確認が必要な場合は、確認手順（ビルド方法・テストアカウント・画面遷移）を一行で具体的に書く。
