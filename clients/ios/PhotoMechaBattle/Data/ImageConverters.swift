import UIKit
import PhotoMechaCore

/// UIImage ↔ RgbaImage の変換（Android BitmapConverters と同役割）。
enum ImageConverters {

    /// UIImage を非プリマルチプライドの RGBA ピクセル配列へ変換する。
    /// 特徴量抽出（features/1.0）は生の RGB 値に依存するため premultiply しない。
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
            bitmapInfo: CGImageAlphaInfo.last.rawValue
        ) else { return nil }
        context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
        var pixels = [UInt32](repeating: 0, count: width * height)
        for i in 0..<(width * height) {
            pixels[i] = RgbaImage.pack(
                a: Int(raw[i * 4 + 3]),
                r: Int(raw[i * 4]),
                g: Int(raw[i * 4 + 1]),
                b: Int(raw[i * 4 + 2])
            )
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
