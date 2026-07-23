import UIKit
import PhotoMechaCore

/// 撮影 → オブジェクト選択 → 分析・命名（S02→S03→S04）の画面間作業状態。
/// ナビゲーション引数で UIImage を渡せないため AppModel スコープで保持する。
@MainActor
final class CaptureFlowState: ObservableObject {
    @Published var capturedImage: UIImage?
    @Published var maskedCrop: UIImage?
    var analysis: CropAnalysis?
    var bbox: [Double]?

    func reset() {
        capturedImage = nil
        maskedCrop = nil
        analysis = nil
        bbox = nil
    }
}
