import SwiftUI
import PhotoMechaCore

/// docs/11 画面遷移。単一スタック・タブなし。
enum Route: Hashable {
    case home
    case capture
    case select
    case analyze
    case mechDetail(String)
    case formation
    case battle(String)
}

/// アプリ全体の依存とナビゲーション状態（docs/11 共通アーキテクチャ）。
@MainActor
final class AppModel: ObservableObject {
    let tokenStore = TokenStore()
    let captureFlow = CaptureFlowState()
    let apiClient: ApiClient

    @Published var path = NavigationPath()
    @Published var registered: Bool

    init() {
        let baseURLString = ProcessInfo.processInfo.environment["PMB_API_BASE_URL"]
            ?? "http://127.0.0.1:8000"
        let store = tokenStore
        apiClient = ApiClient(
            baseURL: URL(string: baseURLString)!,
            tokenProvider: { store.token }
        )
        registered = tokenStore.token != nil
    }

    /// docs/11 エラー時遷移: 401 はトークン破棄 → S00 へ。
    func handleUnauthorized() {
        tokenStore.clear()
        path = NavigationPath()
        registered = false
    }

    func popToHome() {
        path = NavigationPath()
    }
}

@main
struct PhotoMechaBattleApp: App {
    @StateObject private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(model)
        }
    }
}

struct RootView: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        if !model.registered {
            RegisterView()
        } else {
            NavigationStack(path: $model.path) {
                HomeView()
                    .navigationDestination(for: Route.self) { route in
                        switch route {
                        case .home:
                            HomeView()
                        case .capture:
                            CaptureView()
                        case .select:
                            SelectObjectView()
                        case .analyze:
                            AnalyzeView()
                        case .mechDetail(let mechId):
                            MechDetailView(mechId: mechId)
                        case .formation:
                            FormationView()
                        case .battle(let battleId):
                            BattleView(battleId: battleId)
                        }
                    }
            }
        }
    }
}
