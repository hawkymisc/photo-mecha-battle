import SwiftUI
import PhotoMechaCore

/// S05 メカ詳細（docs/11）。サーバー確定の型・ステータス・アートを表示する。
struct MechDetailView: View {
    @EnvironmentObject private var model: AppModel
    let mechId: String
    @State private var mech: MechResponse?
    @State private var errorMessage: String?

    var body: some View {
        Group {
            if let errorMessage {
                ErrorBox(message: errorMessage, retryLabel: "ホームへ") { model.popToHome() }
            } else if let mech {
                content(mech)
            } else {
                LoadingBox(label: "メカ情報を取得中…")
            }
        }
        .navigationTitle("メカ詳細")
        .task(id: mechId) { await load() }
    }

    @ViewBuilder
    private func content(_ mech: MechResponse) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 8) {
                Text(mech.name).font(.title.bold())
                Text(formLabel(mech.form)).font(.headline)
                AsyncImage(url: model.apiClient.mediaURL(path: mech.artUrl)) { image in
                    image.resizable().scaledToFit()
                } placeholder: {
                    Color.secondary.opacity(0.2)
                }
                .frame(maxWidth: .infinity, maxHeight: 240)
                if let infoScore = mech.infoScore {
                    Text(String(format: "情報量スコア: %.2f", infoScore))
                        .font(.body)
                }
                Text("ステータス")
                    .font(.subheadline.bold())
                    .padding(.top, 8)
                ForEach(mech.stats.sorted(by: { $0.key < $1.key }), id: \.key) { stat, value in
                    Text("\(stat.uppercased()): \(value)")
                        .font(.body)
                }
                Button {
                    model.popToHome()
                } label: {
                    Text("ハンガーへ戻る").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .padding(.top, 16)
            }
            .padding(16)
        }
    }

    private func load() async {
        errorMessage = nil
        do {
            mech = try await model.apiClient.mechDetail(mechId: mechId)
        } catch let error as ApiError {
            if error.kind == .unauthorized {
                model.handleUnauthorized()
            } else {
                errorMessage = error.userMessage
            }
        } catch {
            errorMessage = "読み込みに失敗しました: \(error.localizedDescription)"
        }
    }
}
