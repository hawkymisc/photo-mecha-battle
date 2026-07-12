import Foundation

/// プラットフォーム非依存の RGBA 画像コンテナ。
///
/// docs/09 クライアント厚め経路の features/1.0 移植はこの型の上で行い、
/// iOS (CGImage) / macOS テスト (ImageIO) から変換して使う。
/// pixels は 0xAARRGGBB のパック表現（Android core と同一）。
public struct RgbaImage: Sendable {
    /// サーバー実装 `canonicalize_rgba_crop` と同一の前景判定閾値。
    public static let maskForegroundThreshold = 128

    public let width: Int
    public let height: Int
    public let pixels: [UInt32]

    public init(width: Int, height: Int, pixels: [UInt32]) {
        precondition(pixels.count == width * height, "pixel buffer size mismatch")
        self.width = width
        self.height = height
        self.pixels = pixels
    }

    @inlinable public func alpha(_ index: Int) -> Int { Int((pixels[index] >> 24) & 0xFF) }
    @inlinable public func red(_ index: Int) -> Int { Int((pixels[index] >> 16) & 0xFF) }
    @inlinable public func green(_ index: Int) -> Int { Int((pixels[index] >> 8) & 0xFF) }
    @inlinable public func blue(_ index: Int) -> Int { Int(pixels[index] & 0xFF) }

    @inlinable public static func pack(a: Int, r: Int, g: Int, b: Int) -> UInt32 {
        (UInt32(a & 0xFF) << 24) | (UInt32(r & 0xFF) << 16) | (UInt32(g & 0xFF) << 8) | UInt32(b & 0xFF)
    }

    /// サーバー実装 `canonicalize_rgba_crop` の移植:
    /// alpha < 128 の画素は RGB もアルファもゼロ化、alpha >= 128 は 255 に二値化する。
    public func canonicalized() -> RgbaImage {
        var out = [UInt32](repeating: 0, count: pixels.count)
        for i in pixels.indices {
            if alpha(i) >= Self.maskForegroundThreshold {
                out[i] = (pixels[i] & 0x00FF_FFFF) | 0xFF00_0000
            }
        }
        return RgbaImage(width: width, height: height, pixels: out)
    }
}
