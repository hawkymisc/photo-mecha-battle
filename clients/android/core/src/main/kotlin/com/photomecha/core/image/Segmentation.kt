package com.photomecha.core.image

import kotlin.math.abs

/**
 * docs/11 S03 オブジェクト選択の MVP 簡易マスク生成。
 *
 * サーバー vision/segmentation.py `segment_bbox` と同型のヒューリスティック:
 * 左上コーナー画素との RGB マンハッタン距離 > 55 を前景とする。
 * 将来のオンデバイス ML 差し替えはこの関数のインターフェース内に閉じる。
 */
object Segmentation {

    const val FOREGROUND_DISTANCE_THRESHOLD = 55

    /** crop 領域の RGBA 画像に二値アルファ（前景 255 / 背景 0）を付与して返す。 */
    fun maskByCornerDistance(crop: RgbaImage): RgbaImage {
        val cornerR = crop.red(0)
        val cornerG = crop.green(0)
        val cornerB = crop.blue(0)
        val out = IntArray(crop.pixels.size)
        for (i in crop.pixels.indices) {
            val distance = abs(crop.red(i) - cornerR) +
                abs(crop.green(i) - cornerG) +
                abs(crop.blue(i) - cornerB)
            out[i] = if (distance > FOREGROUND_DISTANCE_THRESHOLD) {
                (crop.pixels[i] and 0x00FFFFFF) or (0xFF shl 24)
            } else {
                0
            }
        }
        return RgbaImage(crop.width, crop.height, out)
    }
}
