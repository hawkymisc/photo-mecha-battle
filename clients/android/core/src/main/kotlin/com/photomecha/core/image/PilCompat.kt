package com.photomecha.core.image

import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * PIL (Pillow) 互換の画像処理プリミティブ。
 *
 * docs/11「features/1.0 のネイティブ移植仕様」の実装。サーバー正本
 * (vision/analysis.py) と同じ結果を ε=0.05 以内で再現しなければならない。
 * 検証は tests/golden/ のゴールデンフィクスチャで行う。
 */
object PilCompat {

    /** PIL convert("L"): ITU-R 601-2 の固定小数点実装（ImagingConvert.c L24 準拠）。 */
    fun grayscale(image: RgbaImage): IntArray {
        val out = IntArray(image.width * image.height)
        for (i in out.indices) {
            out[i] = (image.red(i) * 19595 + image.green(i) * 38470 + image.blue(i) * 7471 + 0x8000) shr 16
        }
        return out
    }

    /**
     * PIL ImageFilter.FIND_EDGES: 3x3 カーネル (-1,...,8,...,-1)、除数 1、オフセット 0。
     * 画像外周 1px は入力値をそのまま保持し、結果は 0..255 にクランプする。
     */
    fun findEdges(gray: IntArray, width: Int, height: Int): IntArray {
        val out = gray.copyOf()
        for (y in 1 until height - 1) {
            for (x in 1 until width - 1) {
                val i = y * width + x
                val sum = 8 * gray[i] -
                    gray[i - width - 1] - gray[i - width] - gray[i - width + 1] -
                    gray[i - 1] - gray[i + 1] -
                    gray[i + width - 1] - gray[i + width] - gray[i + width + 1]
                out[i] = min(255, max(0, sum))
            }
        }
        return out
    }

    /** PIL histogram(): L 値の 256 bin ヒストグラム。 */
    fun histogram(gray: IntArray): IntArray {
        val bins = IntArray(256)
        for (value in gray) bins[value]++
        return bins
    }

    /** シャノンエントロピー（bit）。サーバー `_entropy_from_histogram` の分子部分。 */
    fun shannonEntropy(histogram: IntArray): Double {
        val total = histogram.sum()
        if (total == 0) return 0.0
        var entropy = 0.0
        for (count in histogram) {
            if (count == 0) continue
            val p = count.toDouble() / total
            entropy -= p * (ln(p) / ln(2.0))
        }
        return entropy
    }

    /** PIL ImageStat.Stat.mean / var と同一定義（母分散）。 */
    fun meanAndVariance(values: IntArray): Pair<Double, Double> {
        if (values.isEmpty()) return 0.0 to 0.0
        var sum = 0.0
        var sum2 = 0.0
        for (v in values) {
            sum += v
            sum2 += v.toDouble() * v
        }
        val n = values.size.toDouble()
        val mean = sum / n
        return mean to (sum2 - sum * sum / n) / n
    }

    private fun bicubicKernel(x: Double): Double {
        // PIL の bicubic filter（a = -0.5、support = 2.0）
        val ax = abs(x)
        val a = -0.5
        return when {
            ax < 1.0 -> ((a + 2.0) * ax - (a + 3.0)) * ax * ax + 1.0
            ax < 2.0 -> (((ax - 5.0) * ax + 8.0) * ax - 4.0) * a
            else -> 0.0
        }
    }

    /**
     * PIL Image.resize(..., BICUBIC) 互換の 2 パス分離リサイズ。
     * PIL 同様、水平パスの結果を 8bit に丸めてから垂直パスを行う。
     */
    fun resizeBicubic(image: RgbaImage, dstWidth: Int, dstHeight: Int): RgbaImage {
        val horizontal = resamplePass(
            src = image.pixels, srcW = image.width, srcH = image.height,
            dstSize = dstWidth, horizontal = true,
        )
        val vertical = resamplePass(
            src = horizontal, srcW = dstWidth, srcH = image.height,
            dstSize = dstHeight, horizontal = false,
        )
        return RgbaImage(dstWidth, dstHeight, vertical)
    }

    private fun resamplePass(src: IntArray, srcW: Int, srcH: Int, dstSize: Int, horizontal: Boolean): IntArray {
        val srcLen = if (horizontal) srcW else srcH
        val lines = if (horizontal) srcH else srcW
        val scale = srcLen.toDouble() / dstSize
        val filterScale = max(scale, 1.0)
        val support = 2.0 * filterScale

        // 各出力位置の畳み込み係数（PIL と同じ正規化）
        val bounds = IntArray(dstSize * 2)
        val weights = arrayOfNulls<DoubleArray>(dstSize)
        for (d in 0 until dstSize) {
            val center = (d + 0.5) * scale
            var lo = floor(center - support).toInt()
            if (lo < 0) lo = 0
            var hi = ceil(center + support).toInt()
            if (hi > srcLen) hi = srcLen
            val w = DoubleArray(hi - lo)
            var total = 0.0
            for (i in lo until hi) {
                val weight = bicubicKernel((i + 0.5 - center) / filterScale)
                w[i - lo] = weight
                total += weight
            }
            if (total != 0.0) for (i in w.indices) w[i] /= total
            bounds[d * 2] = lo
            bounds[d * 2 + 1] = hi
            weights[d] = w
        }

        val out = IntArray(if (horizontal) dstSize * srcH else srcW * dstSize)
        for (line in 0 until lines) {
            for (d in 0 until dstSize) {
                val lo = bounds[d * 2]
                val hi = bounds[d * 2 + 1]
                val w = weights[d]!!
                var a = 0.0
                var r = 0.0
                var g = 0.0
                var b = 0.0
                for (i in lo until hi) {
                    val pixel = if (horizontal) src[line * srcW + i] else src[i * srcW + line]
                    val weight = w[i - lo]
                    a += ((pixel ushr 24) and 0xFF) * weight
                    r += ((pixel ushr 16) and 0xFF) * weight
                    g += ((pixel ushr 8) and 0xFF) * weight
                    b += (pixel and 0xFF) * weight
                }
                val packed = RgbaImage.pack(clip8(a), clip8(r), clip8(g), clip8(b))
                if (horizontal) out[line * dstSize + d] = packed else out[d * srcW + line] = packed
            }
        }
        return out
    }

    private fun clip8(value: Double): Int = min(255, max(0, value.roundToInt()))
}
