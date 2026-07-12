import UIKit
import PhotoMechaCore

/// UIImage ↔ RgbaImage の変換（Android BitmapConverters と同役割）。
enum ImageConverters {

    /// UIImage を RGBA ピクセル配列へ変換する。
    /// CGBitmapContext は非プリマルチプライドを扱えないため premultipliedLast で描画し、
    /// 半透明画素のみ逆プリマルチプライする（撮影画像は全画素不透明なので通常は恒等）。
    static func toRgbaImage(_ image: UIImage) -> RgbaImage? {
        guard let cgImage = image.cgImage else { return nil }
        let width = cgImage.width
        let height = cgImage.height
        var raw = [UInt8](repeating: 0, count: width * height * 4)
        guard let context = CGContext(
            data: &raw,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: width * 4,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        ) else { return nil }
        context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
        var pixels = [UInt32](repeating: 0, count: width * height)
        for i in 0..<(width * height) {
            var r = Int(raw[i * 4])
            var g = Int(raw[i * 4 + 1])
            var b = Int(raw[i * 4 + 2])
            let a = Int(raw[i * 4 + 3])
            if a > 0, a < 255 {
                r = min(255, (r * 255 + a / 2) / a)
                g = min(255, (g * 255 + a / 2) / a)
                b = min(255, (b * 255 + a / 2) / a)
            }
            pixels[i] = RgbaImage.pack(a: a, r: r, g: g, b: b)
        }
        return RgbaImage(width: width, height: height, pixels: pixels)
    }

    /// RgbaImage を UIImage へ変換する（マスクプレビュー表示用）。
    static func toUIImage(_ image: RgbaImage) -> UIImage? {
        var raw = [UInt8](repeating: 0, count: image.width * image.height * 4)
        for i in 0..<(image.width * image.height) {
            raw[i * 4] = UInt8(image.red(i))
            raw[i * 4 + 1] = UInt8(image.green(i))
            raw[i * 4 + 2] = UInt8(image.blue(i))
            raw[i * 4 + 3] = UInt8(image.alpha(i))
        }
        guard let provider = CGDataProvider(data: Data(raw) as CFData),
              let cgImage = CGImage(
                  width: image.width,
                  height: image.height,
                  bitsPerComponent: 8,
                  bitsPerPixel: 32,
                  bytesPerRow: image.width * 4,
                  space: CGColorSpaceCreateDeviceRGB(),
                  bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.last.rawValue),
                  provider: provider,
                  decode: nil,
                  shouldInterpolate: false,
                  intent: .defaultIntent
              ) else { return nil }
        return UIImage(cgImage: cgImage)
    }

    /// RgbaImage を RGBA PNG バイト列へエンコードする（POST /mechs の crop パート）。
    static func toPngData(_ image: RgbaImage) -> Data? {
        toUIImage(image)?.pngData()
    }

    /// 元画像座標系の矩形でクロップする。
    static func crop(_ image: UIImage, rect: CGRect) -> UIImage? {
        guard let cgImage = image.cgImage,
              let cropped = cgImage.cropping(to: rect) else { return nil }
        return UIImage(cgImage: cropped)
    }
}
