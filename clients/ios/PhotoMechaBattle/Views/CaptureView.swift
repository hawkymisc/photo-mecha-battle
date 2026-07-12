import SwiftUI
import AVFoundation
import PhotoMechaCore

/// S02 撮影（docs/11 / docs/02 撮影 UX）。
/// AVFoundation プレビュー + 輝度ベースの明るさ警告。シャッターで UIImage を確保し S03 へ。
struct CaptureView: View {
    @EnvironmentObject private var model: AppModel
    @StateObject private var camera = CameraController()

    var body: some View {
        VStack {
            ZStack(alignment: .top) {
                CameraPreview(session: camera.session)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                if let warning = camera.brightnessWarning {
                    Text(warning)
                        .padding(8)
                        .background(.red.opacity(0.85), in: RoundedRectangle(cornerRadius: 8))
                        .foregroundStyle(.white)
                        .padding(.top, 12)
                }
            }
            if let error = camera.errorMessage {
                Text(error)
                    .foregroundStyle(.red)
                    .font(.footnote)
                    .padding(.horizontal)
            }
            Button {
                camera.capture { image in
                    guard let image else { return }
                    model.captureFlow.reset()
                    model.captureFlow.capturedImage = image
                    model.path.append(Route.select)
                }
            } label: {
                Text(camera.capturing ? "撮影中…" : "シャッター")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .disabled(!camera.ready || camera.capturing)
            .padding()
        }
        .navigationTitle("撮影")
        .onAppear { camera.start() }
        .onDisappear { camera.stop() }
    }
}

/// AVCaptureSession のラッパー。輝度サンプリング（docs/02 明るさ警告）付き。
@MainActor
final class CameraController: NSObject, ObservableObject {
    let session = AVCaptureSession()
    @Published var ready = false
    @Published var capturing = false
    @Published var brightnessWarning: String?
    @Published var errorMessage: String?

    private let photoOutput = AVCapturePhotoOutput()
    private let videoOutput = AVCaptureVideoDataOutput()
    private let queue = DispatchQueue(label: "com.photomecha.camera")
    private var captureCompletion: ((UIImage?) -> Void)?

    func start() {
        AVCaptureDevice.requestAccess(for: .video) { granted in
            Task { @MainActor in
                if granted {
                    self.configureAndRun()
                } else {
                    self.errorMessage = "カメラ権限が必要です。設定から許可してください。"
                }
            }
        }
    }

    func stop() {
        queue.async { [session] in
            if session.isRunning { session.stopRunning() }
        }
    }

    func capture(completion: @escaping (UIImage?) -> Void) {
        capturing = true
        captureCompletion = completion
        let settings = AVCapturePhotoSettings()
        photoOutput.capturePhoto(with: settings, delegate: self)
    }

    private func configureAndRun() {
        guard !ready else {
            queue.async { [session] in
                if !session.isRunning { session.startRunning() }
            }
            return
        }
        session.beginConfiguration()
        session.sessionPreset = .photo
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
              let input = try? AVCaptureDeviceInput(device: device),
              session.canAddInput(input) else {
            session.commitConfiguration()
            errorMessage = "カメラを初期化できませんでした。"
            return
        }
        session.addInput(input)
        if session.canAddOutput(photoOutput) { session.addOutput(photoOutput) }
        videoOutput.setSampleBufferDelegate(self, queue: queue)
        if session.canAddOutput(videoOutput) { session.addOutput(videoOutput) }
        session.commitConfiguration()
        ready = true
        queue.async { [session] in
            session.startRunning()
        }
    }
}

extension CameraController: AVCapturePhotoCaptureDelegate {
    nonisolated func photoOutput(
        _ output: AVCapturePhotoOutput,
        didFinishProcessingPhoto photo: AVCapturePhoto,
        error: Error?
    ) {
        let image = photo.fileDataRepresentation().flatMap(UIImage.init(data:))
        Task { @MainActor in
            self.capturing = false
            if let error {
                self.errorMessage = "撮影に失敗しました: \(error.localizedDescription)"
                self.captureCompletion?(nil)
            } else {
                self.captureCompletion?(image)
            }
            self.captureCompletion = nil
        }
    }
}

extension CameraController: AVCaptureVideoDataOutputSampleBufferDelegate {
    nonisolated func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        // docs/02: プレビュー中の明るさ警告（Y 平面の平均輝度ヒューリスティック）
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        CVPixelBufferLockBaseAddress(pixelBuffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(pixelBuffer, .readOnly) }
        guard let base = CVPixelBufferGetBaseAddressOfPlane(pixelBuffer, 0) else { return }
        let height = CVPixelBufferGetHeightOfPlane(pixelBuffer, 0)
        let stride = CVPixelBufferGetBytesPerRowOfPlane(pixelBuffer, 0)
        let pointer = base.assumingMemoryBound(to: UInt8.self)
        var sum = 0
        var count = 0
        var offset = 0
        let step = 16
        while offset < height * stride {
            sum += Int(pointer[offset])
            count += 1
            offset += step
        }
        let luma = count == 0 ? 128 : sum / count
        let warning: String?
        if luma < 50 {
            warning = "暗すぎます。明るい場所で撮影してください"
        } else if luma > 220 {
            warning = "明るすぎます。露出を調整してください"
        } else {
            warning = nil
        }
        Task { @MainActor in
            self.brightnessWarning = warning
        }
    }
}

/// AVCaptureVideoPreviewLayer の SwiftUI ラッパー。
struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession

    final class PreviewView: UIView {
        override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    }

    func makeUIView(context: Context) -> PreviewView {
        let view = PreviewView()
        view.previewLayer.session = session
        view.previewLayer.videoGravity = .resizeAspectFill
        return view
    }

    func updateUIView(_ uiView: PreviewView, context: Context) {}
}
