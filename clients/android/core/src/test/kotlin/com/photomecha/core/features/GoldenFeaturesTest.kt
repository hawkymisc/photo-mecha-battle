package com.photomecha.core.features

import com.photomecha.core.image.RgbaImage
import java.awt.image.BufferedImage
import java.io.File
import javax.imageio.ImageIO
import kotlin.math.abs
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.double
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * features/1.0 移植のゴールデンフィクスチャ一致テスト（merge ゲート、docs/11）。
 *
 * サーバー（PIL 実装）が生成した tests/golden/ の PNG + 期待値 JSON に対し、
 * Kotlin 移植が ε=0.05（docs/09 のサーバー許容差分）以内で一致することを検証する。
 */
class GoldenFeaturesTest {

    private val goldenDir = File(
        System.getProperty("pmb.golden.dir")
            ?: error("pmb.golden.dir system property not set (see core/build.gradle.kts)"),
    )
    private val manifest: JsonObject =
        Json.parseToJsonElement(goldenDir.resolve("golden_features.json").readText()).jsonObject

    private fun loadImage(name: String): RgbaImage {
        val buffered = ImageIO.read(goldenDir.resolve(name))
        val converted = BufferedImage(buffered.width, buffered.height, BufferedImage.TYPE_INT_ARGB)
        converted.graphics.drawImage(buffered, 0, 0, null)
        val pixels = IntArray(buffered.width * buffered.height)
        converted.getRGB(0, 0, buffered.width, buffered.height, pixels, 0, buffered.width)
        return RgbaImage(buffered.width, buffered.height, pixels)
    }

    @Test
    fun algoVersionMatchesManifest() {
        assertEquals(manifest["algo_version"]!!.jsonPrimitive.content, FeatureExtractor.ALGO_VERSION)
    }

    @Test
    fun allGoldenCasesMatchWithinTolerance() {
        val tolerance = manifest["tolerance"]!!.jsonPrimitive.double
        val cases = manifest["cases"]!!.jsonObject
        assertTrue("golden cases must not be empty", cases.isNotEmpty())
        for ((caseName, caseElement) in cases) {
            val case = caseElement.jsonObject
            val image = loadImage(case["image"]!!.jsonPrimitive.content)
            val analysis = FeatureExtractor.analyze(image)

            val expectedBackgroundMix = case["background_mix"]!!.jsonPrimitive.double
            assertTrue(
                "$caseName background_mix: expected=$expectedBackgroundMix actual=${analysis.backgroundMix}",
                abs(analysis.backgroundMix - expectedBackgroundMix) <= tolerance,
            )

            val actualFeatures = analysis.features.asMap()
            for ((dimension, expectedElement) in case["features"]!!.jsonObject) {
                val expected = expectedElement.jsonPrimitive.double
                val actual = actualFeatures.getValue(dimension)
                assertTrue(
                    "$caseName $dimension: expected=$expected actual=$actual (tolerance=$tolerance)",
                    abs(actual - expected) <= tolerance,
                )
            }

            val expectedInfoScore = case["info_score"]!!.jsonPrimitive.double
            assertTrue(
                "$caseName info_score: expected=$expectedInfoScore actual=${analysis.infoScore}",
                abs(analysis.infoScore - expectedInfoScore) <= tolerance,
            )
        }
    }
}
