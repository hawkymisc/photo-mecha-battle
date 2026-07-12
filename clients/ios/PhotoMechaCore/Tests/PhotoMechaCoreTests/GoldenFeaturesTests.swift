import XCTest
@testable import PhotoMechaCore
#if canImport(CoreGraphics)
import CoreGraphics
import ImageIO
#endif

/// tests/golden/ のゴールデンフィクスチャとの一致テスト（docs/11 merge ゲート）。
/// サーバー（Pillow）と同一の特徴量を ε=0.05 以内で再現できることを検証する。
final class GoldenFeaturesTests: XCTestCase {

    private struct GoldenManifest: Decodable {
        let algoVersion: String
        let formInferenceVersion: String
        let tolerance: Double
        let cases: [String: GoldenCase]

        enum CodingKeys: String, CodingKey {
            case algoVersion = "algo_version"
            case formInferenceVersion = "form_inference_version"
            case tolerance, cases
        }
    }

    private struct GoldenCase: Decodable {
        let image: String
        let backgroundMix: Double
        let infoScore: Double
        let features: [String: Double]

        enum CodingKeys: String, CodingKey {
            case image, features
            case backgroundMix = "background_mix"
            case infoScore = "info_score"
        }
    }

    private static func goldenDirectory() -> URL {
        if let env = ProcessInfo.processInfo.environment["PMB_GOLDEN_DIR"] {
            return URL(fileURLWithPath: env, isDirectory: true)
        }
        // clients/ios/PhotoMechaCore/Tests/PhotoMechaCoreTests/ → リポジトリルート/tests/golden
        return URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent() // PhotoMechaCoreTests
            .deletingLastPathComponent() // Tests
            .deletingLastPathComponent() // PhotoMechaCore
            .deletingLastPathComponent() // ios
            .deletingLastPathComponent() // clients
            .deletingLastPathComponent() // repo root
            .appendingPathComponent("tests/golden", isDirectory: true)
    }

    private func loadManifest() throws -> GoldenManifest {
        let url = Self.goldenDirectory().appendingPathComponent("golden_features.json")
        let data = try Data(contentsOf: url)
        return try JSONDecoder().decode(GoldenManifest.self, from: data)
    }

    #if canImport(CoreGraphics)
    /// PNG を ImageIO でデコードし、CGImage の生バッファを直接読む。
    /// CGBitmapContext は非プリマルチプライド RGBA を扱えないため描画は使わない。
    /// フォーマットが想定外の場合はスキップではなく fail させる（merge ゲートの空洞化防止）。
    private func loadRgbaPng(_ url: URL) throws -> RgbaImage {
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
              let cgImage = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
            XCTFail("PNG decode failed: \(url.path)")
            throw ApiError(kind: .invalid, statusCode: 0, reason: nil, message: "png decode")
        }
        let width = cgImage.width
        let height = cgImage.height
        XCTAssertEqual(cgImage.bitsPerComponent, 8, "unexpected bit depth")
        XCTAssertEqual(cgImage.bitsPerPixel, 32, "unexpected pixel size (expected RGBA8888)")
        let alphaInfo = cgImage.alphaInfo
        XCTAssertTrue(
            alphaInfo == .last || alphaInfo == .premultipliedLast,
            "unexpected alpha layout: \(alphaInfo.rawValue)"
        )
        guard let providerData = cgImage.dataProvider?.data as Data? else {
            XCTFail("no pixel data for \(url.path)")
            throw ApiError(kind: .invalid, statusCode: 0, reason: nil, message: "no pixel data")
        }
        let bytesPerRow = cgImage.bytesPerRow
        var pixels = [UInt32](repeating: 0, count: width * height)
        providerData.withUnsafeBytes { (raw: UnsafeRawBufferPointer) in
            for y in 0..<height {
                for x in 0..<width {
                    let offset = y * bytesPerRow + x * 4
                    var r = Int(raw[offset])
                    var g = Int(raw[offset + 1])
                    var b = Int(raw[offset + 2])
                    let a = Int(raw[offset + 3])
                    if alphaInfo == .premultipliedLast, a > 0, a < 255 {
                        // ゴールデン PNG のアルファは二値だが、念のため逆プリマルチプライ
                        r = min(255, (r * 255 + a / 2) / a)
                        g = min(255, (g * 255 + a / 2) / a)
                        b = min(255, (b * 255 + a / 2) / a)
                    }
                    pixels[y * width + x] = RgbaImage.pack(a: a, r: r, g: g, b: b)
                }
            }
        }
        return RgbaImage(width: width, height: height, pixels: pixels)
    }

    func testGoldenFeatureParity() throws {
        let manifest = try loadManifest()
        XCTAssertEqual(manifest.algoVersion, FeatureExtractor.algoVersion)

        for (name, golden) in manifest.cases {
            let pngURL = Self.goldenDirectory().appendingPathComponent(golden.image)
            let image = try loadRgbaPng(pngURL)
            let analysis = FeatureExtractor.analyze(image)

            XCTAssertEqual(
                analysis.backgroundMix, golden.backgroundMix,
                accuracy: manifest.tolerance,
                "background_mix mismatch for \(name)"
            )
            XCTAssertEqual(
                analysis.infoScore, golden.infoScore,
                accuracy: manifest.tolerance,
                "info_score mismatch for \(name)"
            )
            let actual = analysis.features.asDictionary()
            for (dimension, expected) in golden.features {
                let value = try XCTUnwrap(actual[dimension], "missing dimension \(dimension)")
                XCTAssertEqual(
                    value, expected,
                    accuracy: manifest.tolerance,
                    "\(dimension) mismatch for \(name)"
                )
            }
        }
    }
    #endif

    func testManifestVersionMatches() throws {
        let manifest = try loadManifest()
        XCTAssertEqual(manifest.algoVersion, FeatureExtractor.algoVersion)
        XCTAssertGreaterThan(manifest.cases.count, 0)
    }
}
