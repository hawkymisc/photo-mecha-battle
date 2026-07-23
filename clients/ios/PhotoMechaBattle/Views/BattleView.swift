import SwiftUI
import PhotoMechaCore

/// S07 バトル再生 / S08 結果・ログ（docs/11）。
/// サーバーの `log_entries` をターン順に演出再生する。勝敗・ダメージの再計算はしない
/// （docs/09 信頼モデル / AGENTS.md 不変条件 1）。
struct BattleView: View {
    @EnvironmentObject private var model: AppModel
    let battleId: String
    @State private var battle: BattleDetailResponse?
    @State private var errorMessage: String?
    @State private var revealedCount = 0

    var body: some View {
        Group {
            if let errorMessage {
                ErrorBox(message: errorMessage, retryLabel: "ホームへ") { model.popToHome() }
            } else if let battle {
                content(battle)
            } else {
                LoadingBox(label: "バトル結果を取得中…")
            }
        }
        .navigationTitle("バトル")
        .navigationBarBackButtonHidden(true)
        .task(id: battleId) { await load() }
    }

    @ViewBuilder
    private func content(_ battle: BattleDetailResponse) -> some View {
        let finished = revealedCount >= battle.logEntries.count
        VStack(alignment: .leading, spacing: 8) {
            Text(headline(battle, finished: finished))
                .font(.title2.bold())
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 6) {
                        ForEach(Array(battle.logEntries.prefix(revealedCount).enumerated()), id: \.offset) { index, entry in
                            logEntryCard(entry)
                                .id(index)
                        }
                    }
                }
                .onChange(of: revealedCount) { count in
                    if count > 0 {
                        withAnimation { proxy.scrollTo(count - 1, anchor: .bottom) }
                    }
                }
            }
            if finished {
                HStack {
                    Button("ホームへ") { model.popToHome() }
                        .buttonStyle(.bordered)
                        .frame(maxWidth: .infinity)
                    Button("再戦する") {
                        model.popToHome()
                        model.path.append(Route.formation)
                    }
                    .buttonStyle(.borderedProminent)
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .padding(16)
    }

    private func headline(_ battle: BattleDetailResponse, finished: Bool) -> String {
        guard finished else { return "バトル進行中…（\(battle.turns) ターン）" }
        switch battle.winnerTeamId {
        case "player": return "勝利！"
        case nil: return "引き分け"
        default: return "敗北…"
        }
    }

    @ViewBuilder
    private func logEntryCard(_ entry: BattleLogEntry) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("Turn \(entry.turn)  \(positionLabel(entry.actorPosition)) \(entry.actorName)")
                .font(.subheadline.bold())
            // docs/11 S08: 条件成立理由の表示（戦術改善につなげる）
            Text("条件「\(entry.conditionLabel)」が成立 → \(entry.action)")
                .font(.caption)
            ForEach(Array(entry.damageEvents.enumerated()), id: \.offset) { _, event in
                Text("→ \(event.targetName) に \(event.damage) ダメージ\(event.defeated ? "（撃破）" : "")")
                    .font(.caption)
            }
            if !entry.note.isEmpty {
                Text(entry.note).font(.caption)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(.secondary.opacity(0.1), in: RoundedRectangle(cornerRadius: 10))
    }

    private func load() async {
        errorMessage = nil
        do {
            let detail = try await model.apiClient.battleDetail(battleId: battleId)
            battle = detail
            revealedCount = 0
            // 演出再生: 0.8 秒ごとに 1 エントリずつ表示
            for i in 1...max(1, detail.logEntries.count) {
                try? await Task.sleep(nanoseconds: 800_000_000)
                revealedCount = i
            }
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
