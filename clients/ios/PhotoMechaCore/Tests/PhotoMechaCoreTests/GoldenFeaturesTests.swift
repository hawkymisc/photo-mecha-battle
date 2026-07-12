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
        let cases: [GoldenCase]

        enum CodingKeys: String, CodingKey {
            case algoVersion = "algo_version"
            case formInferenceVersion = "form_inference_version"
            case tolerance, cases
        }
    }

    private struct GoldenCase: Decodable {
        let name: String
        let file: String
        let backgroundMix: Double
        let infoScore: Double
        let features: [String: Double]

        enum CodingKeys: String, CodingKey {
            case name, file, features
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
    private func loadRgbaPng(_ url: URL) throws -> RgbaImage {
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
              let cgImage = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
            throw XCTSkip("PNG decode unavailable: \(url.path)")
        }
        let width = cgImage.width
        let height = cgImage.height
        var raw = [UInt8](repeating: 0, count: width * height * 4)
        let colorSpace = CGColorSpaceCreateDeviceRGB()
        // 非プリマルチプライドの RGBA8888 で描画（特徴量は生の RGB 値に依存）
        guard let context = CGContext(
            data: &raw,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: width * 4,
            space: colorSpace,
            bitmapInfo: CGImageAlphaInfo.last.rawValue
        ) else {
            throw XCTSkip("CGContext creation failed")
        }
        context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
        var pixels = [UInt32](repeating: 0, count: width * height)
        for i in 0..<(width * height) {
            let r = Int(raw[i * 4])
            let g = Int(raw[i * 4 + 1])
            let b = Int(raw[i * 4 + 2])
            let a = Int(raw[i * 4 + 3])
            pixels[i] = RgbaImage.pack(a: a, r: r, g: g, b: b)
        }
        return RgbaImage(width: width, height: height, pixels: pixels)
    }

    func testGoldenFeatureParity() throws {
        let manifest = try loadManifest()
        XCTAssertEqual(manifest.algoVersion, FeatureExtractor.algoVersion)

        for golden in manifest.cases {
            let pngURL = Self.goldenDirectory().appendingPathComponent(golden.file)
            let image = try loadRgbaPng(pngURL)
            let analysis = FeatureExtractor.analyze(image)

            XCTAssertEqual(
                analysis.backgroundMix, golden.backgroundMix,
                accuracy: manifest.tolerance,
                "background_mix mismatch for \(golden.name)"
            )
            XCTAssertEqual(
                analysis.infoScore, golden.infoScore,
                accuracy: manifest.tolerance,
                "info_score mismatch for \(golden.name)"
            )
            let actual = analysis.features.asDictionary()
            for (dimension, expected) in golden.features {
                let value = try XCTUnwrap(actual[dimension], "missing dimension \(dimension)")
                XCTAssertEqual(
                    value, expected,
                    accuracy: manifest.tolerance,
                    "\(dimension) mismatch for \(golden.name)"
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
