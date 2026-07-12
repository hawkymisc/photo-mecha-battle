import SwiftUI
import PhotoMechaCore

/// S03 オブジェクト選択（docs/11 / docs/02）。
/// 撮影画像上を矩形ドラッグで指定 → 簡易マスク生成 → プレビュー確認。
struct SelectObjectView: View {
    @EnvironmentObject private var model: AppModel
    @State private var dragStart: CGPoint?
    @State private var dragEnd: CGPoint?
    @State private var viewSize: CGSize = .zero
    @State private var maskPreview: UIImage?
    @State private var emptyMaskWarning = false
    @State private var busy = false

    var body: some View {
        guard let source = model.captureFlow.capturedImage else {
            return AnyView(
                ErrorBox(message: "撮影画像がありません。撮影からやり直してください。", retryLabel: "撮影へ戻る") {
                    model.path.removeLast()
                }
            )
        }
        return AnyView(content(source: source))
    }

    @ViewBuilder
    private func content(source: UIImage) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("被写体を囲んでください")
                .font(.headline)
            Text("ドラッグで矩形を指定 → マスクを確認して確定")
                .font(.caption)
            GeometryReader { geometry in
                let displayed = maskPreview ?? source
                Image(uiImage: displayed)
                    .resizable()
                    .scaledToFit()
                    .overlay(selectionOverlay)
                    .gesture(
                        DragGesture(minimumDistance: 4)
                            .onChanged { value in
                                if dragStart == nil || maskPreview != nil {
                                    maskPreview = nil
                                    emptyMaskWarning = false
                                    dragStart = value.startLocation
                                }
                                dragEnd = value.location
                            }
                    )
                    .onAppear { viewSize = geometry.size }
                    .onChange(of: geometry.size) { viewSize = $0 }
            }
            if emptyMaskWarning {
                Text("被写体を検出できませんでした。範囲を選び直してください。")
                    .foregroundStyle(.red)
                    .font(.footnote)
            }
            HStack {
                Button("撮り直す") {
                    model.path.removeLast()
                }
                .buttonStyle(.bordered)
                .frame(maxWidth: .infinity)
                if maskPreview == nil {
                    Button(busy ? "生成中…" : "マスク生成") {
                        generateMask(source: source)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(dragStart == nil || dragEnd == nil || busy)
                    .frame(maxWidth: .infinity)
                } else {
                    Button("この抽出で進む") {
                        model.path.append(Route.analyze)
                    }
                    .buttonStyle(.borderedProminent)
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .padding(16)
        .navigationTitle("オブジェクト選択")
    }

    @ViewBuilder
    private var selectionOverlay: some View {
        if let start = dragStart, let end = dragEnd, maskPreview == nil {
            let rect = CGRect(
                x: min(start.x, end.x),
                y: min(start.y, end.y),
                width: abs(end.x - start.x),
                height: abs(end.y - start.y)
            )
            Rectangle()
                .path(in: rect)
                .stroke(Color.yellow, lineWidth: 2)
        }
    }

    private func generateMask(source: UIImage) {
        guard let start = dragStart, let end = dragEnd,
              viewSize.width > 0, viewSize.height > 0,
              let cgImage = source.cgImage else { return }

        // scaledToFit の表示領域を実画像座標へ換算する
        let imageWidth = CGFloat(cgImage.width)
        let imageHeight = CGFloat(cgImage.height)
        let fitScale = min(viewSize.width / imageWidth, viewSize.height / imageHeight)
        let displayWidth = imageWidth * fitScale
        let displayHeight = imageHeight * fitScale
        let offsetX = (viewSize.width - displayWidth) / 2
        let offsetY = (viewSize.height - displayHeight) / 2

        func toImageX(_ x: CGFloat) -> CGFloat { ((x - offsetX) / fitScale).clamped(0, imageWidth) }
        func toImageY(_ y: CGFloat) -> CGFloat { ((y - offsetY) / fitScale).clamped(0, imageHeight) }

        let left = min(toImageX(start.x), toImageX(end.x))
        let top = min(toImageY(start.y), toImageY(end.y))
        let right = max(toImageX(start.x), toImageX(end.x))
        let bottom = max(toImageY(start.y), toImageY(end.y))
        guard right - left >= 1, bottom - top >= 1 else { return }

        let cropRect = CGRect(x: left, y: top, width: right - left, height: bottom - top)
        guard let cropped = ImageConverters.crop(source, rect: cropRect),
              let rgba = ImageConverters.toRgbaImage(cropped) else {
            emptyMaskWarning = true
            return
        }
        let bbox = [
            Double(left / imageWidth),
            Double(top / imageHeight),
            Double(right / imageWidth),
            Double(bottom / imageHeight),
        ]

        busy = true
        Task {
            defer { busy = false }
            // 画像処理は重いので main actor から逃がす（ANR/フリーズ防止、Android 実測に準拠）
            let analysis = await Task.detached(priority: .userInitiated) {
                FeatureExtractor.analyze(Segmentation.maskByCornerDistance(rgba))
            }.value
            if analysis.foregroundRatio <= 0.0 {
                emptyMaskWarning = true
                return
            }
            model.captureFlow.analysis = analysis
            model.captureFlow.bbox = bbox
            model.captureFlow.maskedCrop = ImageConverters.toUIImage(analysis.canonical)
            maskPreview = model.captureFlow.maskedCrop
        }
    }
}

private extension CGFloat {
    func clamped(_ lower: CGFloat, _ upper: CGFloat) -> CGFloat {
        Swift.min(Swift.max(self, lower), upper)
    }
}
