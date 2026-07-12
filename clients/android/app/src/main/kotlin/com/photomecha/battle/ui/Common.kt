package com.photomecha.battle.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.photomecha.core.api.ApiErrorKind
import com.photomecha.core.api.ApiException

/** docs/11 エラー時遷移: ApiException → ユーザー向け文言。 */
fun ApiException.userMessage(): String = when (kind) {
    ApiErrorKind.UNAUTHORIZED -> "セッションが切れました。もう一度登録してください。"
    ApiErrorKind.DUPLICATE -> "同じ写真は使えません。別の被写体を撮影してください。"
    ApiErrorKind.UNSAFE_CAPTURE -> when (reason) {
        "face_detected" -> "顔が写っている写真は使えません。別の被写体を撮影してください。"
        "crop_too_small" -> "切り抜きが小さすぎます。被写体に近づいて撮り直してください。"
        "empty_mask" -> "被写体を検出できませんでした。選択をやり直してください。"
        "solid_color_crop" -> "単色の被写体は使えません。別の被写体を選んでください。"
        else -> "この写真は使用できません。撮り直してください。"
    }
    ApiErrorKind.CLIENT_OUTDATED -> "アプリの更新が必要です。最新版にアップデートしてください。"
    ApiErrorKind.QUOTA_EXCEEDED -> "本日の生成回数の上限に達しました。明日また試してください。"
    ApiErrorKind.NOT_FOUND -> "データが見つかりませんでした。"
    ApiErrorKind.INVALID -> "入力内容に問題があります。やり直してください。"
    ApiErrorKind.SERVER -> "サーバーエラーが発生しました。しばらくして再試行してください。"
    ApiErrorKind.NETWORK -> "通信に失敗しました。ネットワークを確認して再試行してください。"
}

@Composable
fun LoadingBox(label: String) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        CircularProgressIndicator()
        Text(label, modifier = Modifier.padding(top = 16.dp))
    }
}

@Composable
fun ErrorBox(message: String, retryLabel: String = "再試行", onRetry: (() -> Unit)?) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(message, style = MaterialTheme.typography.bodyLarge)
        if (onRetry != null) {
            Button(onClick = onRetry, modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) {
                Text(retryLabel)
            }
        }
    }
}

/** メカ型の表示ラベル（docs/03）。 */
fun formLabel(form: String): String = when (form) {
    "bird" -> "鳥形"
    "human" -> "人型"
    "beast" -> "獣型"
    else -> form
}

/** 位置の表示ラベル（docs/05）。 */
fun positionLabel(position: String): String = when (position) {
    "front" -> "前衛"
    "middle" -> "中衛"
    "back" -> "後衛"
    else -> position
}
