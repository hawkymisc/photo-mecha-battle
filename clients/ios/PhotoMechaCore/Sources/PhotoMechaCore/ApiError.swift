import Foundation

/// docs/11 エラー時遷移: API エラーをユーザー導線種別へマッピングする。
///
/// | 種別 | 導線 |
/// |---|---|
/// | unauthorized | トークン破棄 → 再登録 (S00) |
/// | duplicate | 再撮影 (S02) |
/// | unsafeCapture | reason 別に再撮影 / 選択やり直し |
/// | clientOutdated | アプリ更新案内（feature_mismatch / unsupported_algo_version） |
/// | quotaExceeded | ホームへ（翌日回復の案内） |
/// | invalid / notFound / server / network | リトライ導線 |
public enum ApiErrorKind: Sendable, Equatable {
    case unauthorized
    case duplicate
    case unsafeCapture
    case clientOutdated
    case quotaExceeded
    case invalid
    case notFound
    case server
    case network
}

public struct ApiError: Error, Sendable {
    public let kind: ApiErrorKind
    public let statusCode: Int
    public let reason: String?
    public let message: String

    public init(kind: ApiErrorKind, statusCode: Int, reason: String?, message: String) {
        self.kind = kind
        self.statusCode = statusCode
        self.reason = reason
        self.message = message
    }
}

public enum ApiErrorMapper {

    private struct ErrorEnvelope: Decodable {
        let detail: Detail?

        enum Detail: Decodable {
            case text(String)
            case object(error: String?, reason: String?)

            init(from decoder: Decoder) throws {
                if let container = try? decoder.singleValueContainer(),
                   let text = try? container.decode(String.self) {
                    self = .text(text)
                    return
                }
                let container = try decoder.container(keyedBy: CodingKeys.self)
                self = .object(
                    error: try container.decodeIfPresent(String.self, forKey: .error),
                    reason: try container.decodeIfPresent(String.self, forKey: .reason)
                )
            }

            enum CodingKeys: String, CodingKey {
                case error, reason
            }
        }
    }

    public static func map(statusCode: Int, body: Data?) -> ApiError {
        var errorCode: String?
        var reason: String?
        var detailText = ""
        if let body {
            detailText = String(data: body, encoding: .utf8) ?? ""
            if let envelope = try? JSONDecoder().decode(ErrorEnvelope.self, from: body) {
                switch envelope.detail {
                case .object(let error, let objectReason):
                    errorCode = error
                    reason = objectReason
                case .text(let text):
                    detailText = text
                case nil:
                    break
                }
            }
        }

        let kind: ApiErrorKind
        switch (statusCode, errorCode) {
        case (401, _): kind = .unauthorized
        case (404, _): kind = .notFound
        case (409, _): kind = .duplicate
        case (429, _): kind = .quotaExceeded
        case (422, "unsafe_capture"): kind = .unsafeCapture
        case (422, "feature_mismatch"), (422, "unsupported_algo_version"): kind = .clientOutdated
        case (400, _), (422, _): kind = .invalid
        default: kind = .server
        }
        return ApiError(
            kind: kind,
            statusCode: statusCode,
            reason: reason ?? errorCode,
            message: "API error \(statusCode): \(errorCode ?? detailText)"
        )
    }
}
