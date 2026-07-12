package com.photomecha.battle.ui

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import com.photomecha.battle.PmbApplication
import com.photomecha.battle.data.toBitmap
import com.photomecha.battle.data.toRgbaImage
import com.photomecha.core.features.FeatureExtractor
import com.photomecha.core.image.Segmentation
import kotlin.math.max
import kotlin.math.min
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * S03 オブジェクト選択（docs/11 / docs/02）。
 * 撮影画像上を矩形ドラッグで指定 → 簡易マスク生成 → プレビュー確認。
 */
@Composable
fun SelectObjectScreen(app: PmbApplication, onConfirmed: () -> Unit, onRetake: () -> Unit) {
    val source = app.captureFlow.capturedBitmap
    if (source == null) {
        ErrorBox("撮影画像がありません。撮影からやり直してください。", retryLabel = "撮影へ戻る") { onRetake() }
        return
    }

    var dragStart by remember { mutableStateOf<Offset?>(null) }
    var dragEnd by remember { mutableStateOf<Offset?>(null) }
    var viewSize by remember { mutableStateOf(IntSize.Zero) }
    var maskPreview by remember { mutableStateOf<Bitmap?>(null) }
    var emptyMaskWarning by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("被写体を囲んでください", style = MaterialTheme.typography.titleMedium)
        Text(
            "ドラッグで矩形を指定 → マスクを確認して確定",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(bottom = 8.dp),
        )
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
            contentAlignment = Alignment.Center,
        ) {
            val displayed = maskPreview ?: source
            Image(
                bitmap = displayed.asImageBitmap(),
                contentDescription = "撮影画像",
                contentScale = ContentScale.Fit,
                modifier = Modifier
                    .fillMaxSize()
                    .aspectRatio(source.width.toFloat() / source.height)
                    .onSizeChanged { viewSize = it }
                    .pointerInput(source) {
                        detectDragGestures(
                            onDragStart = {
                                maskPreview = null
                                emptyMaskWarning = false
                                dragStart = it
                                dragEnd = it
                            },
                            onDrag = { change, _ -> dragEnd = change.position },
                        )
                    }
                    .drawWithContent {
                        drawContent()
                        val start = dragStart
                        val end = dragEnd
                        if (start != null && end != null && maskPreview == null) {
                            val rect = Rect(
                                Offset(min(start.x, end.x), min(start.y, end.y)),
                                Offset(max(start.x, end.x), max(start.y, end.y)),
                            )
                            drawRect(
                                color = Color.Yellow,
                                topLeft = rect.topLeft,
                                size = rect.size,
                                style = Stroke(width = 4f),
                            )
                        }
                    },
            )
        }
        if (emptyMaskWarning) {
            Text(
                "被写体を検出できませんでした。範囲を選び直してください。",
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(vertical = 4.dp),
            )
        }
        Row(modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
            OutlinedButton(onClick = onRetake, modifier = Modifier.weight(1f)) {
                Text("撮り直す")
            }
            if (maskPreview == null) {
                Button(
                    onClick = {
                        val crop = cropBySelection(source, dragStart, dragEnd, viewSize) ?: return@Button
                        val (croppedBitmap, bbox) = crop
                        busy = true
                        scope.launch {
                            // 画像処理は重いので main thread から逃がす（ANR 防止）
                            val analysis = withContext(Dispatchers.Default) {
                                FeatureExtractor.analyze(
                                    Segmentation.maskByCornerDistance(croppedBitmap.toRgbaImage()),
                                )
                            }
                            busy = false
                            if (analysis.foregroundRatio <= 0.0) {
                                emptyMaskWarning = true
                                return@launch
                            }
                            app.captureFlow.maskedCrop = analysis.canonical.toBitmap()
                            app.captureFlow.analysis = analysis
                            app.captureFlow.bbox = bbox
                            maskPreview = app.captureFlow.maskedCrop
                        }
                    },
                    enabled = dragStart != null && dragEnd != null && !busy,
                    modifier = Modifier.weight(1f).padding(start = 8.dp),
                ) {
                    Text(if (busy) "生成中…" else "マスク生成")
                }
            } else {
                Button(
                    onClick = onConfirmed,
                    modifier = Modifier.weight(1f).padding(start = 8.dp),
                ) {
                    Text("この抽出で進む")
                }
            }
        }
    }
}

/** 画面座標の矩形選択を元画像座標へ変換してクロップする。戻り値は (crop, 正規化 bbox)。 */
private fun cropBySelection(
    source: Bitmap,
    dragStart: Offset?,
    dragEnd: Offset?,
    viewSize: IntSize,
): Pair<Bitmap, List<Double>>? {
    if (dragStart == null || dragEnd == null) return null
    if (viewSize.width == 0 || viewSize.height == 0) return null
    val scaleX = source.width.toFloat() / viewSize.width
    val scaleY = source.height.toFloat() / viewSize.height
    val left = (min(dragStart.x, dragEnd.x) * scaleX).toInt().coerceIn(0, source.width - 1)
    val top = (min(dragStart.y, dragEnd.y) * scaleY).toInt().coerceIn(0, source.height - 1)
    val right = (max(dragStart.x, dragEnd.x) * scaleX).toInt().coerceIn(left + 1, source.width)
    val bottom = (max(dragStart.y, dragEnd.y) * scaleY).toInt().coerceIn(top + 1, source.height)
    val crop = Bitmap.createBitmap(source, left, top, right - left, bottom - top)
    val bbox = listOf(
        left.toDouble() / source.width,
        top.toDouble() / source.height,
        right.toDouble() / source.width,
        bottom.toDouble() / source.height,
    )
    return crop to bbox
}
