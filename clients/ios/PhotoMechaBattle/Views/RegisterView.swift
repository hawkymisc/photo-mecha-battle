import SwiftUI
import PhotoMechaCore

/// S00 パイロット登録（docs/11）。
struct RegisterView: View {
    @EnvironmentObject private var model: AppModel
    @State private var name = ""
    @State private var busy = false
    @State private var errorMessage: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Spacer()
            Text("Photo Mecha Battle")
                .font(.largeTitle.bold())
            Text("パイロット名を入力して出撃準備")
                .font(.subheadline)
            TextField("パイロット名", text: $name)
                .textFieldStyle(.roundedBorder)
            if let errorMessage {
                Text(errorMessage)
                    .foregroundStyle(.red)
                    .font(.footnote)
            }
            Button {
                register()
            } label: {
                Text(busy ? "登録中…" : "登録して始める")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || busy)
            Spacer()
        }
        .padding(24)
    }

    private func register() {
        busy = true
        errorMessage = nil
        Task {
            defer { busy = false }
            do {
                let response = try await model.apiClient.register(
                    name: name.trimmingCharacters(in: .whitespaces)
                )
                try model.tokenStore.save(token: response.token, pilotName: response.name)
                model.registered = true
            } catch let error as ApiError {
                errorMessage = error.userMessage
            } catch let error as KeychainWriteError {
                errorMessage = "セッションを保存できませんでした（Keychain エラー \(error.status)）。端末を再起動して再試行してください。"
            } catch {
                errorMessage = "登録に失敗しました: \(error.localizedDescription)"
            }
        }
    }
}
