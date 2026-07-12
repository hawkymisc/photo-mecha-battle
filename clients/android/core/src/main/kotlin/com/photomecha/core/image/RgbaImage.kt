package com.photomecha.core.image

/**
 * プラットフォーム非依存の RGBA 画像コンテナ。
 *
 * docs/09 クライアント厚め経路の features/1.0 移植はこの型の上で行い、
 * Android (Bitmap) / JVM テスト (BufferedImage) から変換して使う。
 * pixels は 0xAARRGGBB のパック表現。
 */
class RgbaImage(val width: Int, val height: Int, val pixels: IntArray) {
    init {
        require(pixels.size == width * height) { "pixel buffer size mismatch" }
    }

    fun alpha(index: Int): Int = (pixels[index] ushr 24) and 0xFF
    fun red(index: Int): Int = (pixels[index] ushr 16) and 0xFF
    fun green(index: Int): Int = (pixels[index] ushr 8) and 0xFF
    fun blue(index: Int): Int = pixels[index] and 0xFF

    companion object {
        /** サーバー実装 `canonicalize_rgba_crop` と同一の前景判定閾値。 */
        const val MASK_FOREGROUND_THRESHOLD = 128

        fun pack(a: Int, r: Int, g: Int, b: Int): Int =
            ((a and 0xFF) shl 24) or ((r and 0xFF) shl 16) or ((g and 0xFF) shl 8) or (b and 0xFF)
    }
}

/**
 * サーバー実装 `canonicalize_rgba_crop` の移植:
 * alpha < 128 の画素は RGB もアルファもゼロ化、alpha >= 128 は 255 に二値化する。
 */
fun RgbaImage.canonicalize(): RgbaImage {
    val out = IntArray(pixels.size)
    for (i in pixels.indices) {
        out[i] = if (alpha(i) >= RgbaImage.MASK_FOREGROUND_THRESHOLD) {
            (pixels[i] and 0x00FFFFFF) or (0xFF shl 24)
        } else {
            0
        }
    }
    return RgbaImage(width, height, out)
}
