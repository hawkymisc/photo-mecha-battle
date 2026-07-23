# 撮影・物体抽出・特徴量・画像生成レビュー

## 対象と結論

対象仕様は `docs/02_photo_object_extraction.md`、`docs/03_mech_generation_and_stats.md`、
`docs/10_mobile_image_generation_survey.md`。主経路の補足として `docs/09_lightweight_server_architecture.md`、
モバイル UX の補足として `docs/11_mobile_client_design.md`、実装・テスト・`PLAN.md` も照合した。

Finding は **10 件（Critical 0 / High 6 / Medium 4 / Low 0）**。
最優先は、画像ファイルの匿名公開と無期限保持、画像入力のサイズ上限欠如、RGBA マスクを省略できる
主経路である。これらはモデル品質の問題ではなく、プライバシー、サービス可用性、対戦公平性の境界を
直接壊す。

## 監査カバレッジ

- [x] 撮影入力、明るさ・ブレ警告、撮影後 UX
- [x] 検出、矩形選択、セグメンテーション、マスク後処理
- [x] 顔検出、perceptual hash、ノイズ・QR、日次クォータ
- [x] 品質スコア、11 次元特徴量、情報量スコア、ステータス反映
- [x] 生成画像と戦闘性能の分離
- [x] 入力サイズ・形式、メモリ・CPU・ディスク枯渇
- [x] 失敗時の再撮影・再選択・リトライ導線
- [x] i2i の seed 再現性、モデル非決定性、Phase 0 の実装状態
- [x] 原画像・crop・mask・art の公開範囲と保持期間
- [x] Python、Android、iOS、API・ゴールデン・診断テスト

## Findings

### CAP-ML-001 — 画像成果物が匿名公開され、保持期限もない

- **重大度**: High
- **file:line**:
  - `src/photo_mecha_battle/api/app.py:29-35`
  - `src/photo_mecha_battle/api/image_storage.py:7-36`
  - `src/photo_mecha_battle/api/database.py:99-121`
- **仕様節**:
  - `docs/02_photo_object_extraction.md`「品質評価」「出力」
  - `docs/09_lightweight_server_architecture.md`「保存方針」— 原画像は「最小限」「短期保持」
- **現状**: `StaticFiles` がストレージルート全体を `/media` に認証なしでマウントする。ルートには
  `captures`、`masks`、`crops`、`art` が同居し、削除・期限切れ処理は存在しない。互換 upload 経路では
  原写真、直登録経路でもユーザー由来 crop が保存される。
- **影響**: URL がログ、画面共有、Referer 等から漏れると、第三者が無期限に顔・室内・持ち物・背景を
  含む画像を取得できる。顔検出の false negative と組み合わさると個人情報漏えいになる。
- **再現条件**: 認証済みで画像を登録し、返却された `/media/...` URL をトークンなしの GET で開く。
  API 再起動後もファイルは残り、期限による削除は行われない。
- **推奨**: `art` の公開配信とユーザー画像の保護配信を分離する。原画像・crop・mask は所有者認証付き
  API または短寿命署名 URL に限定し、原画像の保持日数、削除ジョブ、アカウント削除時のカスケードを
  仕様化する。顔・個人情報を扱う画像は保存時暗号化とアクセス監査も追加する。

### CAP-ML-002 — サーバーとモバイルの双方に画像サイズ上限がなく、資源枯渇できる

- **重大度**: High
- **file:line**:
  - `src/photo_mecha_battle/api/app.py:244-254`
  - `src/photo_mecha_battle/api/app.py:298-329`
  - `src/photo_mecha_battle/api/game_store.py:226-233`
  - `clients/android/app/src/main/kotlin/com/photomecha/battle/ui/CaptureScreen.kt:182-192`
  - `clients/android/app/src/main/kotlin/com/photomecha/battle/data/BitmapConverters.kt:7-24`
  - `clients/ios/PhotoMechaBattle/Data/ImageConverters.swift:10-38`
- **仕様節**:
  - `docs/02_photo_object_extraction.md`「入力」
  - `docs/10_mobile_image_generation_survey.md`「端末 tier とフォールバック」
- **現状**: API は upload/crop を全バイト読み込みしてから Pillow で全画素展開し、最大バイト数、
  最大縦横、最大総画素、デコード時間を制限しない。モバイルも `.photo` の画像を縮小せず Bitmap/UIImage、
  RGBA 配列、マスク、PNG として重複保持する。iOS 変換だけでも `raw` と `pixels` で概ね 8 bytes/pixel
  を追加確保する。
- **影響**: 小さな圧縮ファイルから巨大画素数を展開する画像で API プロセスを OOM/CPU 飽和させられる。
  通常の 12–48 MP 端末写真でもモバイルがメモリ警告、強制終了、長時間フリーズを起こし得る。
- **再現条件**: 数万 px 四方の圧縮 PNG/JPEG、または巨大 multipart を `/captures/upload` か
  `/mechs` に送る。端末側は高解像度写真で画面全体に近い矩形を選び、RGBA 変換と PNG 化を行う。
- **推奨**: リバースプロキシとアプリの両方でバイト上限を設け、デコード前に形式・寸法・総画素を検査する。
  Pillow の decompression-bomb 警告を明示的エラー化し、処理タイムアウトを設ける。端末では撮影直後に
  EXIF 向きを正規化しつつ長辺を仕様値へ縮小し、crop のみを後段へ渡す。上限値と許可形式を
  `docs/02` に受入基準として定義する。

### CAP-ML-003 — 互換 capture API に認証・所有権検証がない

- **重大度**: High
- **file:line**:
  - `src/photo_mecha_battle/api/app.py:270-295`
  - `tests/test_mvp_capture.py:29-55`
  - `tests/test_api_errors.py:8-33`
- **仕様節**:
  - `docs/02_photo_object_extraction.md`「オブジェクト検出」「セマンティックセグメンテーション」「出力」
  - `docs/09_lightweight_server_architecture.md`「データフロー」— 多段 API は開発・互換用
- **現状**: `/captures/{id}/detect`、`/captures/{id}/segment`、
  `/objects/{id}/analyze` は `require_user` を持たず、capture/object の所有者も検査しない。テストも
  トークンなしアクセスを正常系として固定している。
- **影響**: capture ID が漏れた場合、第三者が画像解析を実行し、特徴量を取得し、crop/mask を追加生成して
  CPU・ディスクを消費できる。UUID の推測困難性は認可の代替にならない。
- **再現条件**: ユーザー A が upload した capture ID を使い、未認証またはユーザー B から detect、
  segment、analyze を順に呼ぶ。現状は 401/403 ではなく成功する。
- **推奨**: 互換経路にも認証と capture→user 所有権検査を必須化する。公開環境で不要なら
  `PMB_ENV` 等でルート自体を無効化する。未認証、他ユーザー、所有者の認可マトリクステストを追加する。

### CAP-ML-004 — RGBA マスク必須仕様に反して RGB crop を受理し、性能入力を操作できる

- **重大度**: High
- **file:line**:
  - `src/photo_mecha_battle/api/game_store.py:226-248`
  - `tests/test_mech_direct_registration.py:352-362`
- **仕様節**:
  - `docs/03_mech_generation_and_stats.md`「メカ生成の入力」— crop とセグメンテーションマスク
  - `docs/09_lightweight_server_architecture.md`「メカ生成（主経路）」— alpha が確定マスクの RGBA PNG
- **現状**: `convert("RGBA")` により、アルファを持たない RGB 画像を全面不透明へ暗黙変換する。
  テストはこの挙動を「互換挙動」として受理し、`area == 1.0` を期待している。Content-Type と Pillow の
  実デコード形式も照合しない。
- **影響**: 改変クライアントはマスクを省略して `area=1.0` を得られ、HP、型推定、情報量の入力を
  意図的に変えられる。サーバー再計算は送られた crop との一致しか確認しないため、偽の全面前景を検出できない。
  生成画像そのものから性能を計算してはいないが、「確定マスク由来の分析値」という分離境界は破られる。
- **再現条件**: アルファなし RGB PNG と、それからサーバー式で算出した features を multipart 送信する。
  `test_direct_registration_accepts_rgb_crop_as_full_foreground` と同様に 200 が返り、面積は 1.0 になる。
- **推奨**: 主経路では `image.format == "PNG"`、RGBA、アルファの存在、前景率の妥当範囲を必須化する。
  互換が必要なら戦闘性能を持たないデモ専用経路へ隔離する。元写真との対応を検証できない限界も
  信頼モデルに明記し、将来は端末 attestation または原画像の短期再検証を検討する。

### CAP-ML-005 — 形状特徴量が仕様上の意味を表さず、複数次元が bbox 比率へ縮退している

- **重大度**: High
- **file:line**:
  - `src/photo_mecha_battle/vision/analysis.py:85-95`
  - `src/photo_mecha_battle/vision/analysis.py:145-160`
  - `clients/android/core/src/main/kotlin/com/photomecha/core/features/FeatureExtractor.kt:149-189`
  - `clients/ios/PhotoMechaCore/Sources/PhotoMechaCore/FeatureExtractor.swift:140-176`
- **仕様節**:
  - `docs/03_mech_generation_and_stats.md`「特徴量ベクトル（FeatureVector・11 次元）」
  - `docs/03_mech_generation_and_stats.md`「型推定ルール」「特徴量による加算」
- **現状**: `area` は前景画素率ではなくマスク bbox の面積、`symmetry` は左右の画素対称性ではなく
  bbox の縦横差、`roundness` は `1 - elongation * 0.5`、`shape_complexity` も elongation と
  roundness だけから導出される。異なるシルエットが同じ bbox なら、これらの多くが同値になる。
- **影響**: 細い枠と中身の詰まった物体、左右非対称と対称な物体を区別できず、area→HP、
  roundness→DEF、symmetry→TEC、form 推定が仕様の意味と異なる。ゴールデン一致は三実装が同じ誤った
  proxy を再現していることしか保証しない。
- **再現条件**: 200×200 の透明画像に同一 bbox の「2 px の枠」と「塗りつぶし矩形」を作る。
  実測では前景率が約 0.032 対 0.648 でも、area は約 0.648 対 0.656、elongation/roundness/symmetry は
  同値になった。
- **推奨**: `area` は前景画素数/総画素、`roundness` は輪郭面積と周長、`symmetry` は左右反転 mask の
  IoU、`shape_complexity` は輪郭複雑度等で定義する。変更は `features/2.0` として導入し、同じ bbox で
  内部形状だけ異なる対照テストとステータス回帰テストを追加する。

### CAP-ML-006 — perceptual hash と日次クォータが check-then-write で競合回避できない

- **重大度**: High
- **file:line**:
  - `src/photo_mecha_battle/api/game_store.py:221-251`
  - `src/photo_mecha_battle/api/game_store.py:302-305`
  - `src/photo_mecha_battle/api/game_store.py:568-576`
  - `src/photo_mecha_battle/api/database.py:480-485`
  - `src/photo_mecha_battle/api/database.py:545-562`
- **仕様節**:
  - `docs/02_photo_object_extraction.md`「不正・悪用対策」「重複検出」「撮影品質判定」
- **現状**: 重複確認、クォータ残数確認、capture/mech 保存、使用数加算が一つの DB トランザクションに
  入っていない。重複 hash の一意制約もなく、クォータ更新にも上限条件がない。テストは逐次リクエストのみ。
- **影響**: 同一ユーザーの並列リクエストが全て同じ残数・hash 履歴を見て通過し、重複登録と日次上限超過を
  起こせる。将来 GPU 生成を追加すると直接的な課金・資源消費につながる。
- **再現条件**: 残り 1 回のユーザーで異なる画像、または未登録の同一画像を複数接続から同時送信する。
  各処理が increment/insert 前に `_ensure_*_quota` と `list_capture_hashes` を通過できる。
- **推奨**: 使用枠を条件付き `UPDATE ... WHERE used < limit` で原子的に予約し、失敗時に返却する。
  hash はユーザー・比較窓の要件に合う予約テーブルまたは直列化トランザクションで守る。並列 API テストを追加する。
  なお 64-bit aHash、距離 8、同一ユーザー直近 50 件という逐次時の実装値は `docs/02` と一致しており、
  その MVP 選択自体は本 finding の対象外。

### CAP-ML-007 — 品質 warning が主経路の UX に届かず、capture_quality も撮影品質とマスク余白を混同する

- **重大度**: Medium
- **file:line**:
  - `src/photo_mecha_battle/vision/analysis.py:145-178`
  - `src/photo_mecha_battle/api/game_store.py:253-309`
  - `clients/android/app/src/main/kotlin/com/photomecha/battle/ui/CaptureScreen.kt:95-107`
  - `clients/ios/PhotoMechaBattle/Views/CaptureView.swift:138-172`
- **仕様節**:
  - `docs/02_photo_object_extraction.md`「撮影画面」「品質評価」「撮影品質判定」
  - `docs/03_mech_generation_and_stats.md`「品質ペナルティ」
- **現状**: モバイルの撮影前警告は明るさだけで、仕様にあるブレ警告がない。直登録で暗さ・ブレが
  `warning` になっても、応答に `safety_status`/`safety_reason` を返さず、クライアントは撮り直しを
  提案できない。さらに `capture_quality` は透明背景を黒にした canonical crop 全体で計算するため、
  同じ被写体でもマスク余白・前景率で明るさとブレが変わる。direct の `quality_json` は
  `background_mix` しか保存せず、`QualityScores` の各項目も残さない。
- **影響**: ユーザーは警告理由を知らないまま HP/ATK を減点される。抽出の仕方が「撮影品質」に混入し、
  納得感と公平性を損なう。品質劣化の運用分析もできない。
- **再現条件**: 同じ前景を、透明余白の広い crop とタイトな crop で登録する。実測した細い枠では
  `capture_quality≈0.027`、塗りつぶしでは `≈0.852` となった。暗い/ブレた crop は成功応答になるが、
  UI に warning は出ない。
- **推奨**: 撮影品質はマスク前の撮影 crop または前景画素だけから算出し、抽出品質とは別次元にする。
  主経路応答に品質項目と warning/action を返し、S02 にブレ警告、S04 に理由付き撮り直し導線を追加する。
  quality 各項目の閾値・合成式・テスト画像を仕様化する。

### CAP-ML-008 — MVP 外の顔ヒューリスティックが blocking で有効化され、誤検出と見逃しを生む

- **重大度**: Medium
- **file:line**:
  - `src/photo_mecha_battle/vision/analysis.py:181-238`
  - `src/photo_mecha_battle/vision/analysis.py:294-307`
  - `tests/test_vision.py:57-85`
  - `PLAN.md:68`
- **仕様節**:
  - `docs/02_photo_object_extraction.md`「不正・悪用対策」— 顔・個人情報は将来、β 公開前必須
- **現状**: 実モデルではなく RGB 肌色率・矩形比・エッジ率を使う proxy が、顔らしいと判定すると
  即 `blocked` にする。合成の明るい肌色顔と単色物体しかテストせず、既知の D-009 / Issue #21 には
  暖色の風景・木材等の false positive が記録されている。一方、暗い照明・多様な肌色・小さい顔・横顔・
  遮蔽顔・文字による個人情報は十分検出できない。
- **影響**: 正常な被写体を確定的に拒否して「撮り直し」を繰り返させる一方、顔を含む画像を安全だと
  誤認し得る。CAP-ML-001 の匿名配信と組み合わさるとプライバシー事故になる。
- **再現条件**: 肌色条件に合う暖色テクスチャを画像の 15% 以上に配置すると false positive を作れる。
  逆に `_is_skin_tone` の `r > 95` 等を満たさない暗い顔領域は判定対象外になる。
- **推奨**: 現 MVP では仕様どおり未実装として blocking を外すか warning に下げる。β 公開前に
  顔検出モデル、OCR/個人情報検出、代表的な肌色・照明・姿勢を含む評価セット、false positive/negative の
  受入上限を導入する。**実顔検出の未実装自体はロードマップ上正当であり、現フェーズのバグ扱いはしない**。
  本 finding は、将来項目の不完全な proxy を現在の強制ブロックとして有効化したことを対象とする。

### CAP-ML-009 — 直登録の永続化が非原子的で、失敗後の再試行が重複扱いになる

- **重大度**: Medium
- **file:line**:
  - `src/photo_mecha_battle/api/game_store.py:266-305`
  - `tests/test_mech_direct_registration.py:249-259`
- **仕様節**:
  - `docs/02_photo_object_extraction.md`「出力」
  - `docs/11_mobile_client_design.md`「エラー時遷移」
- **現状**: capture ファイル/行、crop、mask、extracted_object を保存した後に art、mech、クォータを
  保存するが、途中失敗時の DB rollback とファイル削除がない。テストは検証段階の 422 だけを対象にし、
  永続化途中の I/O/DB 失敗を扱わない。
- **影響**: art 保存や mech INSERT が失敗すると orphan ファイル・行が残る。ユーザーが同じ入力を
  リトライすると、先に残った capture hash により 409 duplicate となり、元のメカも完成していないのに
  回復できない。保存容量も徐々に漏れる。
- **再現条件**: `save_capture`/`save_extracted_object` 成功後に `save_art` または `save_mech` を
  I/O エラーにする。API は失敗するが capture は残り、同じ crop の再送は重複拒否される。
- **推奨**: DB 保存を一トランザクションにまとめ、ファイルは一時名へ書いて commit 後に確定する。
  失敗時 cleanup と冪等性キーを実装し、途中失敗の各注入点から再試行可能であることをテストする。

### CAP-ML-010 — 高品質 i2i の再現性基準を MVP スタイライズ試験で代用している

- **重大度**: Medium
- **file:line**:
  - `docs/10_mobile_image_generation_survey.md:214-229`
  - `src/photo_mecha_battle/vision/mech_i2i_diag.py:1-48`
  - `tests/test_diag_mech_i2i.py:13-33`
  - `PLAN.md:7-11`
- **仕様節**:
  - `docs/10_mobile_image_generation_survey.md`「Phase 0 検証計画」
  - `docs/10_mobile_image_generation_survey.md`「端末 tier とフォールバック」
- **現状**: 受入基準は「同一 seed + 同一入力で生成結果が再現可能」とするが、同一端末/同一 runtime、
  byte 一致か知覚一致か、許容差、Core ML と stable-diffusion.cpp 間の扱いを定義していない。
  完了扱いの P0-005 は乱数で合成した crop に決定的な PIL スタイライズを適用するだけで、SD 1.5、
  LoRA、img2img、端末 backend の非決定性を検証していない。文書は `.sh` を成果物とするが実体は `.py`。
- **影響**: 実モデル導入時に同じ seed でも backend、量子化、scheduler、GPU/NPU kernel 差で出力が
  変わり得るのに、Phase 0 の再現性を満たしたと誤認する。ゴールデン画像の更新条件と不正調査時の再現範囲も
  決められない。
- **再現条件**: 現テストを実行すると `pipeline == "mvp_stylize (render_mech_art)"` の hash 一致だけで
  green になり、i2i モデルを一度もロードしない。
- **推奨**: 「同一モデル hash・runtime/version・scheduler・seed・入力での知覚距離上限」と
  「異 runtime 間は構造/色/型識別性の品質下限」に分ける。モデル hash、LoRA hash、全推論パラメータを
  診断ログへ残し、P0-002〜004 の実モデルで評価する。**高品質 i2i 本体の未実装は
  `PLAN.md` P0-002〜004 が未着手と明記しており、ロードマップ上正当である**。現行の簡易スタイライズも
  `docs/03` の MVP 方針に一致するため、未実装そのものはバグ扱いしない。

## 問題なしと確認した点

- `perceptual_hash` の 8×8 grayscale aHash、Hamming 距離 8、同一ユーザー直近 50 件は
  `docs/02` の確定値と一致する。アルゴリズムの衝突耐性は限定的だが、MVP の明示的選択である。
- `FeatureVector` の 0.0〜1.0 検証、情報量スコア重み、品質ペナルティ、ステータス 10〜200 clamp は
  `docs/03` と実装・単体テストが一致する。
- クライアント申告 features はサーバーで再計算され、差分 0.05 超を拒否する。iOS/Android/Python の
  ゴールデン一致も用意されている。
- `render_mech_art` は art だけを生成し、型・stats はその前に分析値から確定される。**生成画像の
  ピクセルを戦闘性能へ逆流させる実装は確認されなかった**。
- ノイズ・QR の score cap は直登録主経路とテストに存在する。ただし `docs/02` では将来扱いのままで、
  実装済み状態への文書更新が必要である。
- 高品質 i2i、LoRA、端末 tier 別生成の未実装は P0-002〜004 / β 以降として明記されており、
  現時点ではバグではない。

## 推奨順序

1. 公開前ブロッカー: CAP-ML-001、002、003、004。
2. 公平性・不正対策: CAP-ML-005、006。
3. UX と運用耐性: CAP-ML-007、008、009。
4. 実モデル Phase 0 着手前: CAP-ML-010。
