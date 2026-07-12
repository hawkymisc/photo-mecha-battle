import Foundation

/// PIL (Pillow) 互換の画像処理プリミティブ。
///
/// docs/11「features/1.0 のネイティブ移植仕様」の実装。サーバー正本
/// (vision/analysis.py) と同じ結果を ε=0.05 以内で再現しなければならない。
/// 検証は tests/golden/ のゴールデンフィクスチャで行う。
public enum PilCompat {

    /// PIL convert("L"): ITU-R 601-2 の固定小数点実装（ImagingConvert.c L24 準拠）。
    public static func grayscale(_ image: RgbaImage) -> [Int] {
        var out = [Int](repeating: 0, count: image.width * image.height)
        for i in out.indices {
            out[i] = (image.red(i) * 19595 + image.green(i) * 38470 + image.blue(i) * 7471 + 0x8000) >> 16
        }
        return out
    }

    /// PIL ImageFilter.FIND_EDGES: 3x3 カーネル (-1,...,8,...,-1)、除数 1、オフセット 0。
    /// 画像外周 1px は入力値をそのまま保持し、結果は 0..255 にクランプする。
    public static func findEdges(_ gray: [Int], width: Int, height: Int) -> [Int] {
        var out = gray
        guard width > 2, height > 2 else { return out }
        for y in 1..<(height - 1) {
            for x in 1..<(width - 1) {
                let i = y * width + x
                let sum = 8 * gray[i]
                    - gray[i - width - 1] - gray[i - width] - gray[i - width + 1]
                    - gray[i - 1] - gray[i + 1]
                    - gray[i + width - 1] - gray[i + width] - gray[i + width + 1]
                out[i] = min(255, max(0, sum))
            }
        }
        return out
    }

    /// PIL histogram(): L 値の 256 bin ヒストグラム。
    public static func histogram(_ gray: [Int]) -> [Int] {
        var bins = [Int](repeating: 0, count: 256)
        for value in gray { bins[value] += 1 }
        return bins
    }

    /// シャノンエントロピー（bit）。サーバー `_entropy_from_histogram` の分子部分。
    public static func shannonEntropy(_ histogram: [Int]) -> Double {
        let total = histogram.reduce(0, +)
        guard total > 0 else { return 0.0 }
        var entropy = 0.0
        for count in histogram where count > 0 {
            let p = Double(count) / Double(total)
            entropy -= p * (log(p) / log(2.0))
        }
        return entropy
    }

    /// PIL ImageStat.Stat.mean / var と同一定義（母分散）。
    public static func meanAndVariance(_ values: [Int]) -> (mean: Double, variance: Double) {
        guard !values.isEmpty else { return (0.0, 0.0) }
        var sum = 0.0
        var sum2 = 0.0
        for v in values {
            let d = Double(v)
            sum += d
            sum2 += d * d
        }
        let n = Double(values.count)
        let mean = sum / n
        return (mean, (sum2 - sum * sum / n) / n)
    }

    /// PIL の bicubic filter（a = -0.5、support = 2.0）
    private static func bicubicKernel(_ x: Double) -> Double {
        let ax = abs(x)
        let a = -0.5
        if ax < 1.0 {
            return ((a + 2.0) * ax - (a + 3.0)) * ax * ax + 1.0
        }
        if ax < 2.0 {
            return (((ax - 5.0) * ax + 8.0) * ax - 4.0) * a
        }
        return 0.0
    }

    /// PIL Image.resize(..., BICUBIC) 互換の 2 パス分離リサイズ。
    /// PIL 同様、水平パスの結果を 8bit に丸めてから垂直パスを行う。
    public static func resizeBicubic(_ image: RgbaImage, dstWidth: Int, dstHeight: Int) -> RgbaImage {
        let horizontal = resamplePass(
            src: image.pixels, srcW: image.width, srcH: image.height,
            dstSize: dstWidth, horizontal: true
        )
        let vertical = resamplePass(
            src: horizontal, srcW: dstWidth, srcH: image.height,
            dstSize: dstHeight, horizontal: false
        )
        return RgbaImage(width: dstWidth, height: dstHeight, pixels: vertical)
    }

    private static func resamplePass(
        src: [UInt32], srcW: Int, srcH: Int, dstSize: Int, horizontal: Bool
    ) -> [UInt32] {
        let srcLen = horizontal ? srcW : srcH
        let lines = horizontal ? srcH : srcW
        let scale = Double(srcLen) / Double(dstSize)
        let filterScale = max(scale, 1.0)
        let support = 2.0 * filterScale

        // 各出力位置の畳み込み係数（PIL と同じ正規化）
        var bounds = [Int](repeating: 0, count: dstSize * 2)
        var weights = [[Double]](repeating: [], count: dstSize)
        for d in 0..<dstSize {
            let center = (Double(d) + 0.5) * scale
            let lo = max(0, Int(floor(center - support)))
            let hi = min(srcLen, Int(ceil(center + support)))
            var w = [Double](repeating: 0.0, count: hi - lo)
            var total = 0.0
            for i in lo..<hi {
                let weight = bicubicKernel((Double(i) + 0.5 - center) / filterScale)
                w[i - lo] = weight
                total += weight
            }
            if total != 0.0 {
                for i in w.indices { w[i] /= total }
            }
            bounds[d * 2] = lo
            bounds[d * 2 + 1] = hi
            weights[d] = w
        }

        var out = [UInt32](repeating: 0, count: horizontal ? dstSize * srcH : srcW * dstSize)
        for line in 0..<lines {
            for d in 0..<dstSize {
                let lo = bounds[d * 2]
                let hi = bounds[d * 2 + 1]
                let w = weights[d]
                var a = 0.0, r = 0.0, g = 0.0, b = 0.0
                for i in lo..<hi {
                    let pixel = horizontal ? src[line * srcW + i] : src[i * srcW + line]
                    let weight = w[i - lo]
                    a += Double((pixel >> 24) & 0xFF) * weight
                    r += Double((pixel >> 16) & 0xFF) * weight
                    g += Double((pixel >> 8) & 0xFF) * weight
                    b += Double(pixel & 0xFF) * weight
                }
                let packed = RgbaImage.pack(a: clip8(a), r: clip8(r), g: clip8(g), b: clip8(b))
                if horizontal {
                    out[line * dstSize + d] = packed
                } else {
                    out[d * srcW + line] = packed
                }
            }
        }
        return out
    }

    private static func clip8(_ value: Double) -> Int {
        min(255, max(0, Int(value.rounded())))
    }
}
