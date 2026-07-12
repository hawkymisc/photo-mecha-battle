package com.photomecha.battle.data

import android.graphics.Bitmap
import com.photomecha.core.features.CropAnalysis

/**
 * 撮影 → オブジェクト選択 → 分析・命名（S02→S03→S04）の画面間作業状態。
 * ナビゲーション引数で Bitmap を渡せないため Application スコープで保持する。
 */
class CaptureFlowState {
    var capturedBitmap: Bitmap? = null
    var maskedCrop: Bitmap? = null
    var analysis: CropAnalysis? = null
    var bbox: List<Double>? = null

    fun reset() {
        capturedBitmap = null
        maskedCrop = null
        analysis = null
        bbox = null
    }
}
