import SwiftUI
import PhotoMechaCore

/// docs/11 エラー時遷移: ApiError → ユーザー向け文言。
extension ApiError {
    var userMessage: String {
        switch kind {
        case .unauthorized:
            return "セッションが切れました。もう一度登録してください。"
        case .duplicate:
            return "同じ写真は使えません。別の被写体を撮影してください。"
        case .unsafeCapture:
            switch reason {
            case "face_detected":
                return "顔が写っている写真は使えません。別の被写体を撮影してください。"
            case "crop_too_small":
                return "切り抜きが小さすぎます。被写体に近づいて撮り直してください。"
            case "empty_mask":
                return "被写体を検出できませんでした。選択をやり直してください。"
            case "solid_color_crop":
                return "単色の被写体は使えません。別の被写体を選んでください。"
            default:
                return "この写真は使用できません。撮り直してください。"
            }
        case .clientOutdated:
            return "アプリの更新が必要です。最新版にアップデートしてください。"
        case .quotaExceeded:
            return "本日の生成回数の上限に達しました。明日また試してください。"
        case .notFound:
            return "データが見つかりませんでした。"
        case .invalid:
            return "入力内容に問題があります。やり直してください。"
        case .server:
            return "サーバーエラーが発生しました。しばらくして再試行してください。"
        case .network:
            return "通信に失敗しました。ネットワークを確認して再試行してください。"
        }
    }
}

/// メカ型の表示ラベル（docs/03）。
func formLabel(_ form: String) -> String {
    switch form {
    case "bird": return "鳥形"
    case "human": return "人型"
    case "beast": return "獣型"
    default: return form
    }
}

/// 位置の表示ラベル（docs/05）。
func positionLabel(_ position: String) -> String {
    switch position {
    case "front": return "前衛"
    case "middle": return "中衛"
    case "back": return "後衛"
    default: return position
    }
}

struct LoadingBox: View {
    let label: String

    var body: some View {
        VStack(spacing: 16) {
            ProgressView()
            Text(label)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(24)
    }
}

struct ErrorBox: View {
    let message: String
    var retryLabel: String = "再試行"
    var onRetry: (() -> Void)?

    var body: some View {
        VStack(spacing: 16) {
            Text(message)
                .multilineTextAlignment(.center)
            if let onRetry {
                Button(retryLabel, action: onRetry)
                    .buttonStyle(.borderedProminent)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(24)
    }
}
