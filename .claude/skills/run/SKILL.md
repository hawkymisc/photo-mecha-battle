---
name: run
description: Photo Mecha Battle のバックエンド API + 動作確認用 Web クライアントを起動し、コアループを実地確認する手順。/run・/verify・実機確認・PO レビュー準備のときに使う。
---

# アプリの起動と実地確認

## 起動

```bash
python -m uvicorn photo_mecha_battle.api.app:app --reload --port 8000
```

- Web クライアント（開発用プロトタイプ）: http://127.0.0.1:8000/app/
- OpenAPI docs: http://127.0.0.1:8000/docs
- スマホ実機から確認する場合は `--host 0.0.0.0` を付け、`http://<LAN内IP>:8000/app/` を開く（実機カメラでの撮影確認用。ファイアウォールでポート 8000 の許可が必要な場合あり）。

## 環境変数（未設定時の挙動は意図的な無効化）

| 変数 | 未設定時 |
|---|---|
| `PMB_ADMIN_TOKEN` | `POST /billing/entitlements` が常に 403（事実上無効） |
| `PMB_REVENUECAT_WEBHOOK_SECRET` | RevenueCat Webhook が常に 401（事実上無効） |

課金系を手元で試すときだけ任意の値を設定する。「403/401 が返る」は未設定環境では正常。

## データ

- 永続化先は `data/`（gitignore 済み: SQLite + メディアファイル）。状態をリセットしたければ `data/` を削除してよい（開発用データのみ、復元不要）。

## スモーク確認の順序（コアループ）

Web クライアント上で: 写真アップロード → 検出・抽出 → メカ生成 → 戦術選択 → チーム編成（3体）→ CPU 戦バトル → ログ確認 → ランキング。

API を直接叩く場合はこの依存順で: `POST /auth/register`（`X-User-Token` を取得）→ `POST /captures/upload`（multipart）→ `POST /mechs` → `POST /tactics` → `POST /teams` → `POST /battles` → `GET /battles/{id}`。

- API の疎通確認は curl ではなく Python（`httpx` / `requests`）スクリプトで行う（ユーザーグローバルの api-testing ルール）。
- サーバー不要の CLI デモ: `python scripts/vertical_slice.py`（撮影→バトルの縦切り）、`python scripts/demo_battle.py`（バトルのみ）、`python scripts/mvp_flow.py`。

## 確認の観点

- バトル結果・ランキングはサーバー応答のみを信頼する（web/ クライアントは何も判定しない設計 — docs/09 信頼モデル）。クライアント側に判定ロジックが混入していたらそれ自体がバグ。
- バトルの再現確認は同一 `seed` + 同一入力でログ完全一致を見る。
