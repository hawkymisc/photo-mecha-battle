import Foundation

/// docs/11 S03 オブジェクト選択の MVP 簡易マスク生成。
///
/// サーバー vision/segmentation.py `segment_bbox` と同型のヒューリスティック:
/// 左上コーナー画素との RGB マンハッタン距離 > 55 を前景とする。
/// 将来のオンデバイス ML 差し替えはこの関数のインターフェース内に閉じる。
public enum Segmentation {

    public static let foregroundDistanceThreshold = 55

    /// crop 領域の RGBA 画像に二値アルファ（前景 255 / 背景 0）を付与して返す。
    public static func maskByCornerDistance(_ crop: RgbaImage) -> RgbaImage {
        let cornerR = crop.red(0)
        let cornerG = crop.green(0)
        let cornerB = crop.blue(0)
        var out = [UInt32](repeating: 0, count: crop.pixels.count)
        for i in crop.pixels.indices {
            let distance = abs(crop.red(i) - cornerR)
                + abs(crop.green(i) - cornerG)
                + abs(crop.blue(i) - cornerB)
            if distance > Self.foregroundDistanceThreshold {
                out[i] = (crop.pixels[i] & 0x00FF_FFFF) | 0xFF00_0000
            }
        }
        return RgbaImage(width: crop.width, height: crop.height, pixels: out)
    }
}
