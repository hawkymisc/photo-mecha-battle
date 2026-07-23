import SwiftUI
import PhotoMechaCore

/// S01 ホーム / ハンガー（docs/11）。メカ一覧・クォータ表示・撮影/編成導線。
struct HomeView: View {
    @EnvironmentObject private var model: AppModel
    @State private var mechs: [MechSummary]?
    @State private var quotas: QuotasResponse?
    @State private var errorMessage: String?
    @State private var reloadKey = 0

    var body: some View {
        Group {
            if let errorMessage {
                ErrorBox(message: errorMessage) { reloadKey += 1 }
            } else if let mechs {
                content(mechs: mechs)
            } else {
                LoadingBox(label: "ハンガーを読み込み中…")
            }
        }
        .navigationTitle("ハンガー（\(model.tokenStore.pilotName ?? "")）")
        .task(id: reloadKey) { await load() }
    }

    @ViewBuilder
    private func content(mechs: [MechSummary]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            if let quotas {
                Text("本日の残り生成枠: 撮影 \(quotas.captures.remaining) / メカ \(quotas.mechs.remaining)")
                    .font(.footnote)
                    .padding(.horizontal)
            }
            if mechs.isEmpty {
                Spacer()
                Text("まだメカがいません。撮影から最初のメカを生成しましょう。")
                    .frame(maxWidth: .infinity)
                    .multilineTextAlignment(.center)
                    .padding()
                Spacer()
            } else {
                List(mechs) { mech in
                    Button {
                        model.path.append(Route.mechDetail(mech.id))
                    } label: {
                        HStack {
                            AsyncImage(url: model.apiClient.mediaURL(path: mech.artUrl)) { image in
                                image.resizable().scaledToFit()
                            } placeholder: {
                                Color.secondary.opacity(0.2)
                            }
                            .frame(width: 56, height: 56)
                            VStack(alignment: .leading) {
                                Text(mech.name).font(.headline)
                                Text("\(formLabel(mech.form))  HP \(mech.stats["hp"] ?? 0)  ATK \(mech.stats["attack"] ?? mech.stats["atk"] ?? 0)")
                                    .font(.caption)
                            }
                        }
                    }
                    .buttonStyle(.plain)
                }
                .listStyle(.plain)
            }
            let needed = max(0, 3 - mechs.count)
            if needed > 0 {
                Text("出撃にはメカが 3 体必要です（あと \(needed) 体）")
                    .font(.footnote)
                    .padding(.horizontal)
            }
            HStack {
                Button {
                    model.captureFlow.reset()
                    model.path.append(Route.capture)
                } label: {
                    Text("撮影する").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                Button {
                    model.path.append(Route.formation)
                } label: {
                    Text("出撃編成").frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .disabled(mechs.count < 3)
            }
            .padding()
        }
    }

    private func load() async {
        errorMessage = nil
        do {
            mechs = try await model.apiClient.listMechs().mechs
            quotas = try await model.apiClient.quotas()
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
