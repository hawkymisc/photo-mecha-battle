package com.photomecha.battle.ui

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.photomecha.battle.PmbApplication
import java.util.concurrent.Executors

/**
 * S02 撮影（docs/11 / docs/02 撮影 UX）。
 * CameraX プレビュー + 輝度ベースの明るさ警告。シャッターで Bitmap を確保し S03 へ。
 */
@Composable
fun CaptureScreen(app: PmbApplication, onCaptured: () -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var hasPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED,
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted -> hasPermission = granted }

    LaunchedEffect(Unit) {
        if (!hasPermission) permissionLauncher.launch(Manifest.permission.CAMERA)
    }

    if (!hasPermission) {
        ErrorBox("カメラ権限が必要です。設定から許可してください。", retryLabel = "権限を再要求") {
            permissionLauncher.launch(Manifest.permission.CAMERA)
        }
        return
    }

    var brightnessWarning by remember { mutableStateOf<String?>(null) }
    var capturing by remember { mutableStateOf(false) }
    var captureError by remember { mutableStateOf<String?>(null) }
    val imageCapture = remember { ImageCapture.Builder().build() }
    val analysisExecutor = remember { Executors.newSingleThreadExecutor() }

    DisposableEffect(Unit) {
        onDispose { analysisExecutor.shutdown() }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Box(modifier = Modifier.weight(1f)) {
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { viewContext ->
                    val previewView = PreviewView(viewContext)
                    val providerFuture = ProcessCameraProvider.getInstance(viewContext)
                    providerFuture.addListener({
                        val provider = providerFuture.get()
                        val preview = Preview.Builder().build().also {
                            it.setSurfaceProvider(previewView.surfaceProvider)
                        }
                        // docs/02: プレビュー中の明るさ警告（輝度平均のヒューリスティック）
                        val analysis = ImageAnalysis.Builder()
                            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                            .build()
                        analysis.setAnalyzer(analysisExecutor) { imageProxy ->
                            val luma = imageProxy.averageLuma()
                            brightnessWarning = when {
                                luma < 50 -> "暗すぎます。明るい場所で撮影してください"
                                luma > 220 -> "明るすぎます。露出を調整してください"
                                else -> null
                            }
                            imageProxy.close()
                        }
                        provider.unbindAll()
                        provider.bindToLifecycle(
                            lifecycleOwner,
                            CameraSelector.DEFAULT_BACK_CAMERA,
                            preview,
                            imageCapture,
                            analysis,
                        )
                    }, ContextCompat.getMainExecutor(viewContext))
                    previewView
                },
            )
            brightnessWarning?.let {
                Surface(
                    color = MaterialTheme.colorScheme.errorContainer,
                    modifier = Modifier.align(Alignment.TopCenter).padding(12.dp),
                ) {
                    Text(it, modifier = Modifier.padding(8.dp))
                }
            }
        }
        captureError?.let {
            Text(
                it,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(horizontal = 16.dp),
            )
        }
        Button(
            onClick = {
                capturing = true
                captureError = null
                imageCapture.takePicture(
                    ContextCompat.getMainExecutor(context),
                    object : ImageCapture.OnImageCapturedCallback() {
                        override fun onCaptureSuccess(image: ImageProxy) {
                            val bitmap = image.toUprightBitmap()
                            image.close()
                            app.captureFlow.reset()
                            app.captureFlow.capturedBitmap = bitmap
                            capturing = false
                            onCaptured()
                        }

                        override fun onError(exception: ImageCaptureException) {
                            capturing = false
                            captureError = "撮影に失敗しました: ${exception.message}"
                        }
                    },
                )
            },
            enabled = !capturing,
            modifier = Modifier.fillMaxWidth().padding(16.dp),
        ) {
            Text(if (capturing) "撮影中…" else "シャッター")
        }
    }
}

/** ImageAnalysis (YUV) の Y 平面から平均輝度を求める。 */
private fun ImageProxy.averageLuma(): Int {
    val buffer = planes[0].buffer
    buffer.rewind()
    var sum = 0L
    var count = 0
    // 全画素は不要なのでストライドサンプリング
    while (buffer.hasRemaining()) {
        sum += (buffer.get().toInt() and 0xFF)
        count++
        if (buffer.remaining() >= 16) buffer.position(buffer.position() + 15)
    }
    return if (count == 0) 128 else (sum / count).toInt()
}

/** JPEG ImageProxy を回転補正済み Bitmap へ変換する。 */
private fun ImageProxy.toUprightBitmap(): Bitmap {
    val buffer = planes[0].buffer
    buffer.rewind()
    val bytes = ByteArray(buffer.remaining())
    buffer.get(bytes)
    val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
    val rotation = imageInfo.rotationDegrees
    if (rotation == 0) return bitmap
    val matrix = Matrix().apply { postRotate(rotation.toFloat()) }
    return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
}
