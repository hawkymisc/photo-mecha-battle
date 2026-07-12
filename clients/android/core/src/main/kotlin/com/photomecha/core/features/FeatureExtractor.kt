package com.photomecha.core.features

import com.photomecha.core.image.PilCompat
import com.photomecha.core.image.RgbaImage
import com.photomecha.core.image.canonicalize
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/** features/1.0 の 11 次元特徴量（サーバー features.py FeatureVector の移植）。 */
data class FeatureVector(
    val visualEntropy: Double,
    val edgeComplexity: Double,
    val colorDiversity: Double,
    val shapeComplexity: Double,
    val semanticRarity: Double,
    val captureQuality: Double,
    val sizeBalance: Double,
    val area: Double,
    val elongation: Double,
    val roundness: Double,
    val symmetry: Double,
) {
    fun asMap(): Map<String, Double> = mapOf(
        "visual_entropy" to visualEntropy,
        "edge_complexity" to edgeComplexity,
        "color_diversity" to colorDiversity,
        "shape_complexity" to shapeComplexity,
        "semantic_rarity" to semanticRarity,
        "capture_quality" to captureQuality,
        "size_balance" to sizeBalance,
        "area" to area,
        "elongation" to elongation,
        "roundness" to roundness,
        "symmetry" to symmetry,
    )
}

data class CropAnalysis(
    val features: FeatureVector,
    val canonical: RgbaImage,
    val backgroundMix: Double,
    val foregroundRatio: Double,
    val infoScore: Double,
)

/**
 * サーバー正本 vision/analysis.py の features/1.0 移植。
 *
 * ゴールデンフィクスチャ（tests/golden/）との一致（ε=0.05）が merge ゲート。
 */
object FeatureExtractor {

    const val ALGO_VERSION = "features/1.0"

    // docs/03 情報量スコアの重み（mech_stats.py INFO_SCORE_WEIGHTS）
    private val INFO_SCORE_WEIGHTS = mapOf(
        "visual_entropy" to 0.25,
        "edge_complexity" to 0.20,
        "color_diversity" to 0.15,
        "shape_complexity" to 0.15,
        "semantic_rarity" to 0.10,
        "capture_quality" to 0.10,
        "size_balance" to 0.05,
    )

    fun analyze(crop: RgbaImage): CropAnalysis {
        val canonical = crop.canonicalize()
        val total = max(1, canonical.width * canonical.height)
        var foreground = 0
        for (i in canonical.pixels.indices) {
            if (canonical.alpha(i) >= RgbaImage.MASK_FOREGROUND_THRESHOLD) foreground++
        }
        val foregroundRatio = foreground.toDouble() / total
        val backgroundMix = (1.0 - foregroundRatio).coerceIn(0.0, 1.0)
        val features = extractFeatures(canonical)
        return CropAnalysis(
            features = features,
            canonical = canonical,
            backgroundMix = backgroundMix,
            foregroundRatio = foregroundRatio,
            infoScore = infoScore(features),
        )
    }

    fun infoScore(features: FeatureVector): Double {
        val values = features.asMap()
        return INFO_SCORE_WEIGHTS.entries.sumOf { (key, weight) -> weight * values.getValue(key) }
    }

    private fun extractFeatures(canonical: RgbaImage): FeatureVector {
        val width = canonical.width
        val height = canonical.height
        val gray = PilCompat.grayscale(canonical)
        val edges = PilCompat.findEdges(gray, width, height)

        val visualEntropy = min(1.0, PilCompat.shannonEntropy(PilCompat.histogram(gray)) / 8.0)
        val edgeComplexity = edgeDensity(edges)
        val colorDiversity = colorDiversity(canonical)
        val shape = shapeMetrics(canonical)
        val captureQuality = min(estimateBrightness(gray), estimateBlur(edges))

        return FeatureVector(
            visualEntropy = visualEntropy,
            edgeComplexity = edgeComplexity,
            colorDiversity = colorDiversity,
            shapeComplexity = min(1.0, (shape.elongation + (1.0 - shape.roundness)) / 2.0),
            semanticRarity = min(1.0, colorDiversity * 0.7 + edgeComplexity * 0.3),
            captureQuality = captureQuality,
            sizeBalance = shape.sizeBalance,
            area = shape.areaRatio,
            elongation = shape.elongation,
            roundness = shape.roundness,
            symmetry = shape.symmetry,
        )
    }

    /** vision/analysis.py `_edge_density`。 */
    private fun edgeDensity(edges: IntArray): Double {
        val edgePixels = edges.count { it > 40 }
        return min(1.0, edgePixels.toDouble() / max(1, edges.size) * 8.0)
    }

    /** vision/analysis.py `_color_diversity`（64x64 バイキュービック縮小 → ユニーク色数 / 256）。 */
    private fun colorDiversity(canonical: RgbaImage): Double {
        val sample = PilCompat.resizeBicubic(canonical, 64, 64)
        val colors = HashSet<Int>()
        for (pixel in sample.pixels) colors.add(pixel and 0x00FFFFFF)
        return min(1.0, colors.size / 256.0)
    }

    /** vision/analysis.py `estimate_brightness`。 */
    private fun estimateBrightness(gray: IntArray): Double {
        val (mean, _) = PilCompat.meanAndVariance(gray)
        val normalized = mean / 255.0
        return when {
            normalized < 0.2 -> normalized / 0.2 * 0.5
            normalized > 0.85 -> max(0.0, 1.0 - (normalized - 0.85) / 0.15)
            else -> 1.0
        }
    }

    /** vision/analysis.py `estimate_blur`（FIND_EDGES の分散 / 2000）。 */
    private fun estimateBlur(edges: IntArray): Double {
        val (_, variance) = PilCompat.meanAndVariance(edges)
        return (variance / 2000.0).coerceIn(0.0, 1.0)
    }

    private data class ShapeMetrics(
        val areaRatio: Double,
        val elongation: Double,
        val roundness: Double,
        val symmetry: Double,
        val sizeBalance: Double,
    )

    /** vision/analysis.py `_shape_metrics`（マスク bbox ベース）。 */
    private fun shapeMetrics(canonical: RgbaImage): ShapeMetrics {
        var left = canonical.width
        var top = canonical.height
        var right = 0
        var bottom = 0
        var found = false
        for (y in 0 until canonical.height) {
            for (x in 0 until canonical.width) {
                if (canonical.alpha(y * canonical.width + x) > 0) {
                    found = true
                    if (x < left) left = x
                    if (y < top) top = y
                    if (x >= right) right = x + 1
                    if (y >= bottom) bottom = y + 1
                }
            }
        }
        if (!found) {
            // PIL getbbox() が None のとき全面 bbox にフォールバック（サーバーと同じ）
            left = 0; top = 0; right = canonical.width; bottom = canonical.height
        }
        val bboxWidth = right - left
        val bboxHeight = bottom - top
        val areaRatio = (bboxWidth.toDouble() * bboxHeight) / max(1, canonical.width * canonical.height)
        val elongation = min(
            1.0,
            max(bboxWidth, bboxHeight).toDouble() / max(1, min(bboxWidth, bboxHeight)) / 3.0,
        )
        val roundness = 1.0 - elongation * 0.5
        val symmetry = 1.0 - abs(bboxWidth - bboxHeight).toDouble() / max(1, bboxWidth + bboxHeight)
        val sizeBalance = (1.0 - abs(areaRatio - 0.35) / 0.35).coerceIn(0.0, 1.0)
        return ShapeMetrics(areaRatio, elongation, roundness, symmetry, sizeBalance)
    }
}
