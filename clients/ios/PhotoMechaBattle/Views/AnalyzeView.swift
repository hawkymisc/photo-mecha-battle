import SwiftUI
import PhotoMechaCore

/// S04 分析・命名（docs/11）。
/// 特徴量プレビュー（情報量スコア）を表示し、`POST /mechs` 直登録（docs/09 主経路）を行う。
/// 表示値はプレビューであり、確定値は常にサーバー応答（docs/09 信頼モデル）。
struct AnalyzeView: View {
    @EnvironmentObject private var model: AppModel
    @State private var name = ""
    @State private var busy = false
    @State private var error: ApiError?
    @State private var genericErrorMessage: String?

    var body: some View {
        guard let analysis = model.captureFlow.analysis,
              let maskedCrop = model.captureFlow.maskedCrop else {
            return AnyView(
                ErrorBox(message: "抽出データがありません。選択からやり直してください。", retryLabel: "選択へ戻る") {
                    model.path.removeLast()
                }
            )
        }
        return AnyView(content(analysis: analysis, maskedCrop: maskedCrop))
    }

    @ViewBuilder
    private func content(analysis: CropAnalysis, maskedCrop: UIImage) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 8) {
                Text("分析結果（プレビュー）").font(.headline)
                Text("確定値はサーバーが決定します").font(.caption)
                Image(uiImage: maskedCrop)
                    .resizable()
                    .scaledToFit()
                    .frame(maxWidth: .infinity, maxHeight: 220)
                Text(String(format: "情報量スコア: %.2f", analysis.infoScore))
                    .font(.subheadline.bold())
                ProgressView(value: min(max(analysis.infoScore, 0), 1))
                ForEach(analysis.features.asDictionary().sorted(by: { $0.key < $1.key }), id: \.key) { key, value in
                    Text(String(format: "%@: %.3f", key, value))
                        .font(.caption)
                }
                TextField("メカの名前", text: $name)
                    .textFieldStyle(.roundedBorder)
                    .padding(.top, 12)
                if let error {
                    Text(error.userMessage)
                        .foregroundStyle(.red)
                        .font(.footnote)
                    errorRecoveryButton(error)
                }
                if let genericErrorMessage {
                    Text(genericErrorMessage)
                        .foregroundStyle(.red)
                        .font(.footnote)
                }
                Button {
                    createMech(analysis: analysis)
                } label: {
                    Text(busy ? "生成中…" : "メカを生成する")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || busy)
                .padding(.top, 12)
            }
            .padding(16)
        }
        .navigationTitle("分析・命名")
    }

    @ViewBuilder
    private func errorRecoveryButton(_ error: ApiError) -> some View {
        switch error.kind {
        case .duplicate, .unsafeCapture:
            if error.reason == "empty_mask" || error.reason == "solid_color_crop" {
                Button("選択をやり直す") { model.path.removeLast() }
                    .buttonStyle(.bordered)
            } else {
                Button("撮り直す") { model.path.removeLast(2) }
                    .buttonStyle(.bordered)
            }
        case .quotaExceeded:
            // docs/11: 429 は翌日回復の案内とともにホームへ戻す
            Button("ホームへ戻る") { model.popToHome() }
                .buttonStyle(.bordered)
        default:
            EmptyView()
        }
    }

    private func createMech(analysis: CropAnalysis) {
        busy = true
        error = nil
        genericErrorMessage = nil
        Task {
            defer { busy = false }
            do {
                guard let pngBytes = ImageConverters.toPngData(analysis.canonical) else {
                    genericErrorMessage = "画像のエンコードに失敗しました。選択からやり直してください。"
                    return
                }
                let payload = MechDirectPayload(
                    name: name.trimmingCharacters(in: .whitespaces),
                    algoVersion: FeatureExtractor.algoVersion,
                    bbox: model.captureFlow.bbox,
                    features: analysis.features.asDictionary()
                )
                let response = try await model.apiClient.createMechDirect(payload: payload, cropPng: pngBytes)
                model.captureFlow.reset()
                model.popToHome()
                model.path.append(Route.mechDetail(response.id))
            } catch let apiError as ApiError {
                if apiError.kind == .unauthorized {
                    model.handleUnauthorized()
                } else {
                    error = apiError
                }
            } catch {
                genericErrorMessage = "生成に失敗しました: \(error.localizedDescription)"
            }
        }
    }
}
