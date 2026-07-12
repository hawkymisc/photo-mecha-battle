package com.photomecha.battle.data

import android.graphics.Bitmap
import com.photomecha.core.image.RgbaImage
import java.io.ByteArrayOutputStream

fun Bitmap.toRgbaImage(): RgbaImage {
    val converted = if (config == Bitmap.Config.ARGB_8888) this else copy(Bitmap.Config.ARGB_8888, false)
    val pixels = IntArray(converted.width * converted.height)
    converted.getPixels(pixels, 0, converted.width, 0, 0, converted.width, converted.height)
    return RgbaImage(converted.width, converted.height, pixels)
}

fun RgbaImage.toBitmap(): Bitmap {
    val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
    bitmap.setPixels(pixels, 0, width, 0, 0, width, height)
    return bitmap
}

/** docs/09 主経路の crop パート: 正規形 RGBA を PNG（可逆）でエンコードする。 */
fun Bitmap.toPngBytes(): ByteArray {
    val stream = ByteArrayOutputStream()
    compress(Bitmap.CompressFormat.PNG, 100, stream)
    return stream.toByteArray()
}
