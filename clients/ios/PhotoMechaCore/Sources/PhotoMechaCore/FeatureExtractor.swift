import Foundation

/// features/1.0 の 11 次元特徴量（サーバー features.py FeatureVector の移植）。
public struct FeatureVector: Sendable, Equatable {
    public let visualEntropy: Double
    public let edgeComplexity: Double
    public let colorDiversity: Double
    public let shapeComplexity: Double
    public let semanticRarity: Double
    public let captureQuality: Double
    public let sizeBalance: Double
    public let area: Double
    public let elongation: Double
    public let roundness: Double
    public let symmetry: Double

    public func asDictionary() -> [String: Double] {
        [
            "visual_entropy": visualEntropy,
            "edge_complexity": edgeComplexity,
            "color_diversity": colorDiversity,
            "shape_complexity": shapeComplexity,
            "semantic_rarity": semanticRarity,
            "capture_quality": captureQuality,
            "size_balance": sizeBalance,
            "area": area,
            "elongation": elongation,
            "roundness": roundness,
            "symmetry": symmetry,
        ]
    }
}

public struct CropAnalysis: Sendable {
    public let features: FeatureVector
    public let canonical: RgbaImage
    public let backgroundMix: Double
    public let foregroundRatio: Double
    public let infoScore: Double
}

/// サーバー正本 vision/analysis.py の features/1.0 移植。
///
/// ゴールデンフィクスチャ（tests/golden/）との一致（ε=0.05）が merge ゲート。
public enum FeatureExtractor {

    public static let algoVersion = "features/1.0"

    // docs/03 情報量スコアの重み（mech_stats.py INFO_SCORE_WEIGHTS）
    private static let infoScoreWeights: [(key: String, weight: Double)] = [
        ("visual_entropy", 0.25),
        ("edge_complexity", 0.20),
        ("color_diversity", 0.15),
        ("shape_complexity", 0.15),
        ("semantic_rarity", 0.10),
        ("capture_quality", 0.10),
        ("size_balance", 0.05),
    ]

    public static func analyze(_ crop: RgbaImage) -> CropAnalysis {
        let canonical = crop.canonicalized()
        let total = max(1, canonical.width * canonical.height)
        var foreground = 0
        for i in canonical.pixels.indices where canonical.alpha(i) >= RgbaImage.maskForegroundThreshold {
            foreground += 1
        }
        let foregroundRatio = Double(foreground) / Double(total)
        let backgroundMix = min(1.0, max(0.0, 1.0 - foregroundRatio))
        let features = extractFeatures(canonical)
        return CropAnalysis(
            features: features,
            canonical: canonical,
            backgroundMix: backgroundMix,
            foregroundRatio: foregroundRatio,
            infoScore: infoScore(features)
        )
    }

    public static func infoScore(_ features: FeatureVector) -> Double {
        let values = features.asDictionary()
        return infoScoreWeights.reduce(0.0) { acc, entry in
            acc + entry.weight * (values[entry.key] ?? 0.0)
        }
    }

    private static func extractFeatures(_ canonical: RgbaImage) -> FeatureVector {
        let gray = PilCompat.grayscale(canonical)
        let edges = PilCompat.findEdges(gray, width: canonical.width, height: canonical.height)

        let visualEntropy = min(1.0, PilCompat.shannonEntropy(PilCompat.histogram(gray)) / 8.0)
        let edgeComplexity = edgeDensity(edges)
        let colorDiversity = colorDiversity(canonical)
        let shape = shapeMetrics(canonical)
        let captureQuality = min(estimateBrightness(gray), estimateBlur(edges))

        return FeatureVector(
            visualEntropy: visualEntropy,
            edgeComplexity: edgeComplexity,
            colorDiversity: colorDiversity,
            shapeComplexity: min(1.0, (shape.elongation + (1.0 - shape.roundness)) / 2.0),
            semanticRarity: min(1.0, colorDiversity * 0.7 + edgeComplexity * 0.3),
            captureQuality: captureQuality,
            sizeBalance: shape.sizeBalance,
            area: shape.areaRatio,
            elongation: shape.elongation,
            roundness: shape.roundness,
            symmetry: shape.symmetry
        )
    }

    /// vision/analysis.py `_edge_density`。
    private static func edgeDensity(_ edges: [Int]) -> Double {
        let edgePixels = edges.lazy.filter { $0 > 40 }.count
        return min(1.0, Double(edgePixels) / Double(max(1, edges.count)) * 8.0)
    }

    /// vision/analysis.py `_color_diversity`（64x64 バイキュービック縮小 → ユニーク色数 / 256）。
    private static func colorDiversity(_ canonical: RgbaImage) -> Double {
        let sample = PilCompat.resizeBicubic(canonical, dstWidth: 64, dstHeight: 64)
        var colors = Set<UInt32>()
        for pixel in sample.pixels { colors.insert(pixel & 0x00FF_FFFF) }
        return min(1.0, Double(colors.count) / 256.0)
    }

    /// vision/analysis.py `estimate_brightness`。
    private static func estimateBrightness(_ gray: [Int]) -> Double {
        let (mean, _) = PilCompat.meanAndVariance(gray)
        let normalized = mean / 255.0
        if normalized < 0.2 { return normalized / 0.2 * 0.5 }
        if normalized > 0.85 { return max(0.0, 1.0 - (normalized - 0.85) / 0.15) }
        return 1.0
    }

    /// vision/analysis.py `estimate_blur`（FIND_EDGES の分散 / 2000）。
    private static func estimateBlur(_ edges: [Int]) -> Double {
        let (_, variance) = PilCompat.meanAndVariance(edges)
        return min(1.0, max(0.0, variance / 2000.0))
    }

    private struct ShapeMetrics {
        let areaRatio: Double
        let elongation: Double
        let roundness: Double
        let symmetry: Double
        let sizeBalance: Double
    }

    /// vision/analysis.py `_shape_metrics`（マスク bbox ベース）。
    private static func shapeMetrics(_ canonical: RgbaImage) -> ShapeMetrics {
        var left = canonical.width
        var top = canonical.height
        var right = 0
        var bottom = 0
        var found = false
        for y in 0..<canonical.height {
            for x in 0..<canonical.width where canonical.alpha(y * canonical.width + x) > 0 {
                found = true
                if x < left { left = x }
                if y < top { top = y }
                if x >= right { right = x + 1 }
                if y >= bottom { bottom = y + 1 }
            }
        }
        if !found {
            // PIL getbbox() が None のとき全面 bbox にフォールバック（サーバーと同じ）
            left = 0
            top = 0
            right = canonical.width
            bottom = canonical.height
        }
        let bboxWidth = right - left
        let bboxHeight = bottom - top
        let areaRatio = Double(bboxWidth * bboxHeight) / Double(max(1, canonical.width * canonical.height))
        let elongation = min(
            1.0,
            Double(max(bboxWidth, bboxHeight)) / Double(max(1, min(bboxWidth, bboxHeight))) / 3.0
        )
        let roundness = 1.0 - elongation * 0.5
        let symmetry = 1.0 - Double(abs(bboxWidth - bboxHeight)) / Double(max(1, bboxWidth + bboxHeight))
        let sizeBalance = min(1.0, max(0.0, 1.0 - abs(areaRatio - 0.35) / 0.35))
        return ShapeMetrics(
            areaRatio: areaRatio,
            elongation: elongation,
            roundness: roundness,
            symmetry: symmetry,
            sizeBalance: sizeBalance
        )
    }
}
