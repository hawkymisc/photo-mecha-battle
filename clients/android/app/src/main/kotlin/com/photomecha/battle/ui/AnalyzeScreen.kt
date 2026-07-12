package com.photomecha.battle.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.unit.dp
import com.photomecha.battle.PmbApplication
import com.photomecha.battle.data.toPngBytes
import com.photomecha.core.api.ApiErrorKind
import com.photomecha.core.api.ApiException
import com.photomecha.core.api.MechDirectPayload
import com.photomecha.core.features.FeatureExtractor
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * S04 分析・命名（docs/11）。
 * 特徴量プレビュー（情報量スコア）を表示し、`POST /mechs` 直登録（docs/09 主経路）を行う。
 * 表示値はプレビューであり、確定値は常にサーバー応答（docs/09 信頼モデル）。
 */
@Composable
fun AnalyzeScreen(
    app: PmbApplication,
    onCreated: (String) -> Unit,
    onRecapture: () -> Unit,
    onReselect: () -> Unit,
    onUnauthorized: () -> Unit,
) {
    val analysis = app.captureFlow.analysis
    val maskedCrop = app.captureFlow.maskedCrop
    if (analysis == null || maskedCrop == null) {
        ErrorBox("抽出データがありません。選択からやり直してください。", retryLabel = "選択へ戻る") { onReselect() }
        return
    }

    var name by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<ApiException?>(null) }
    val scope = rememberCoroutineScope()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Text("分析結果（プレビュー）", style = MaterialTheme.typography.titleMedium)
        Text(
            "確定値はサーバーが決定します",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(bottom = 8.dp),
        )
        Image(
            bitmap = maskedCrop.asImageBitmap(),
            contentDescription = "抽出オブジェクト",
            modifier = Modifier.fillMaxWidth().height(220.dp),
        )
        Text(
            "情報量スコア: ${"%.2f".format(analysis.infoScore)}",
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(top = 8.dp),
        )
        LinearProgressIndicator(
            progress = { analysis.infoScore.toFloat().coerceIn(0f, 1f) },
            modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        )
        for ((dimension, value) in analysis.features.asMap()) {
            Text(
                "$dimension: ${"%.3f".format(value)}",
                style = MaterialTheme.typography.bodySmall,
            )
        }
        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            label = { Text("メカの名前") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        )
        error?.let {
            Text(
                it.userMessage(),
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 8.dp),
            )
            when (it.kind) {
                ApiErrorKind.DUPLICATE, ApiErrorKind.UNSAFE_CAPTURE -> {
                    if (it.reason == "empty_mask" || it.reason == "solid_color_crop") {
                        OutlinedButton(onClick = onReselect, modifier = Modifier.fillMaxWidth().padding(top = 4.dp)) {
                            Text("選択をやり直す")
                        }
                    } else {
                        OutlinedButton(onClick = onRecapture, modifier = Modifier.fillMaxWidth().padding(top = 4.dp)) {
                            Text("撮り直す")
                        }
                    }
                }
                else -> Unit
            }
        }
        Button(
            onClick = {
                busy = true
                error = null
                scope.launch {
                    try {
                        val payload = MechDirectPayload(
                            name = name.trim(),
                            algoVersion = FeatureExtractor.ALGO_VERSION,
                            bbox = app.captureFlow.bbox,
                            features = analysis.features.asMap(),
                        )
                        // PNG エンコードは重いので main thread から逃がす（ANR 防止）
                        val pngBytes = withContext(Dispatchers.Default) { maskedCrop.toPngBytes() }
                        val response = app.apiClient.createMechDirect(payload, pngBytes)
                        app.captureFlow.reset()
                        onCreated(response.id)
                    } catch (e: ApiException) {
                        if (e.kind == ApiErrorKind.UNAUTHORIZED) onUnauthorized() else error = e
                    } finally {
                        busy = false
                    }
                }
            },
            enabled = name.isNotBlank() && !busy,
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 12.dp)
                .align(Alignment.CenterHorizontally),
        ) {
            Text(if (busy) "生成中…" else "メカを生成する")
        }
    }
}
