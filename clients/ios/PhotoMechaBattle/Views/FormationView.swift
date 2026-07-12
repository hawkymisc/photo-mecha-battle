import SwiftUI
import PhotoMechaCore

private let positions = ["front", "middle", "back"]

/// S06 出撃編成（docs/11）。前衛・中衛・後衛にメカとプリセット戦術を割り当て、
/// CPU デモ戦（POST /battles）を開始する。
struct FormationView: View {
    @EnvironmentObject private var model: AppModel
    @State private var mechs: [MechSummary]?
    @State private var presets: [TacticPreset]?
    @State private var errorMessage: String?
    @State private var selectedMech: [String: MechSummary] = [:]
    @State private var selectedPreset: [String: TacticPreset] = [:]
    @State private var busy = false
    @State private var reloadKey = 0

    var body: some View {
        Group {
            if let errorMessage {
                ErrorBox(message: errorMessage) { reloadKey += 1 }
            } else if let mechs, let presets {
                content(mechs: mechs, presets: presets)
            } else {
                LoadingBox(label: "編成データを取得中…")
            }
        }
        .navigationTitle("出撃編成")
        .task(id: reloadKey) { await load() }
    }

    @ViewBuilder
    private func content(mechs: [MechSummary], presets: [TacticPreset]) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 8) {
                Text("3 つの位置にメカと戦術プリセットを割り当ててください")
                    .font(.caption)
                ForEach(positions, id: \.self) { position in
                    slotCard(position: position, mechs: mechs, presets: presets)
                }
                let ready = positions.allSatisfy {
                    selectedMech[$0] != nil && selectedPreset[$0] != nil
                }
                Button {
                    startBattle()
                } label: {
                    Text(busy ? "出撃中…" : "CPU 戦に出撃")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(!ready || busy)
                .padding(.top, 16)
            }
            .padding(16)
        }
    }

    @ViewBuilder
    private func slotCard(position: String, mechs: [MechSummary], presets: [TacticPreset]) -> some View {
        // 他ポジションで選択済みのメカは候補から外す
        let available = mechs.filter { candidate in
            !selectedMech.contains { key, value in key != position && value.id == candidate.id }
        }
        VStack(alignment: .leading, spacing: 6) {
            Text(positionLabel(position)).font(.headline)
            Menu {
                ForEach(available) { mech in
                    Button("\(mech.name)（\(formLabel(mech.form))）") {
                        selectedMech[position] = mech
                    }
                }
            } label: {
                Text(selectedMech[position].map { "\($0.name)（\(formLabel($0.form))）" } ?? "メカを選択")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            Menu {
                ForEach(presets) { preset in
                    Button(preset.label) {
                        selectedPreset[position] = preset
                    }
                }
            } label: {
                Text(selectedPreset[position]?.label ?? "戦術プリセットを選択")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
        }
        .padding(12)
        .background(.secondary.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
    }

    private func load() async {
        errorMessage = nil
        do {
            mechs = try await model.apiClient.listMechs().mechs
            presets = try await model.apiClient.tacticPresets().presets
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

    private func startBattle() {
        busy = true
        Task {
            defer { busy = false }
            do {
                let request = BattleCreateRequest(
                    teamName: model.tokenStore.pilotName ?? "Player",
                    slots: positions.map { position in
                        BattleSlotRequest(
                            mechId: selectedMech[position]!.id,
                            position: position,
                            preset: selectedPreset[position]!.id
                        )
                    },
                    // CPU デモ戦のみクライアント seed 可（ランク戦はサーバー生成、docs/09）
                    seed: Int.random(in: 0..<Int(Int32.max))
                )
                let battle = try await model.apiClient.createDemoBattle(request: request)
                model.path.append(Route.battle(battle.id))
            } catch let error as ApiError {
                if error.kind == .unauthorized {
                    model.handleUnauthorized()
                } else {
                    errorMessage = error.userMessage
                }
            } catch {
                errorMessage = "出撃に失敗しました: \(error.localizedDescription)"
            }
        }
    }
}
