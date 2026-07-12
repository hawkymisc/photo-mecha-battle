import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Photo Mecha Battle API クライアント（docs/11 Phase 1 経路）。
///
/// バトルはサーバー権威（docs/09 信頼モデル）。このクラスはサーバー応答を
/// そのまま返すだけで、勝敗・ダメージ・ステータスを再計算しない。
public final class ApiClient: Sendable {
    public let baseURL: URL
    private let tokenProvider: @Sendable () -> String?
    private let session: URLSession

    public init(
        baseURL: URL,
        tokenProvider: @escaping @Sendable () -> String?,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.tokenProvider = tokenProvider
        self.session = session
    }

    public func register(name: String) async throws -> RegisterResponse {
        try await post(path: "/auth/register", body: RegisterRequest(name: name))
    }

    public func quotas() async throws -> QuotasResponse {
        try await get(path: "/users/quotas")
    }

    public func listMechs() async throws -> MechListResponse {
        try await get(path: "/mechs")
    }

    public func mechDetail(mechId: String) async throws -> MechResponse {
        try await get(path: "/mechs/\(mechId)")
    }

    public func tacticPresets() async throws -> TacticPresetsResponse {
        try await get(path: "/tactic-presets")
    }

    /// docs/09 主経路: multipart（payload JSON + crop RGBA PNG）でのメカ直登録。
    public func createMechDirect(payload: MechDirectPayload, cropPng: Data) async throws -> MechResponse {
        let boundary = "pmb-\(UUID().uuidString)"
        var request = makeRequest(path: "/mechs")
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let payloadJson = try JSONEncoder().encode(payload)
        var body = Data()
        body.append(Data("--\(boundary)\r\n".utf8))
        body.append(Data("Content-Disposition: form-data; name=\"payload\"\r\n\r\n".utf8))
        body.append(payloadJson)
        body.append(Data("\r\n--\(boundary)\r\n".utf8))
        body.append(Data("Content-Disposition: form-data; name=\"crop\"; filename=\"crop.png\"\r\n".utf8))
        body.append(Data("Content-Type: image/png\r\n\r\n".utf8))
        body.append(cropPng)
        body.append(Data("\r\n--\(boundary)--\r\n".utf8))
        request.httpBody = body
        return try await execute(request)
    }

    public func createDemoBattle(request: BattleCreateRequest) async throws -> BattleCreateResponse {
        try await post(path: "/battles", body: request)
    }

    public func battleDetail(battleId: String) async throws -> BattleDetailResponse {
        try await get(path: "/battles/\(battleId)")
    }

    public func mediaURL(path: String?) -> URL? {
        guard let path else { return nil }
        return URL(string: path, relativeTo: baseURL)?.absoluteURL
    }

    private func get<T: Decodable>(path: String) async throws -> T {
        var request = makeRequest(path: path)
        request.httpMethod = "GET"
        return try await execute(request)
    }

    private func post<T: Decodable, B: Encodable>(path: String, body: B) async throws -> T {
        var request = makeRequest(path: path)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        return try await execute(request)
    }

    private func makeRequest(path: String) -> URLRequest {
        var request = URLRequest(url: URL(string: path, relativeTo: baseURL)!.absoluteURL)
        if let token = tokenProvider() {
            request.setValue(token, forHTTPHeaderField: "X-User-Token")
        }
        return request
    }

    private func execute<T: Decodable>(_ request: URLRequest) async throws -> T {
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw ApiError(
                kind: .network,
                statusCode: 0,
                reason: nil,
                message: "network error: \(error.localizedDescription)"
            )
        }
        guard let http = response as? HTTPURLResponse else {
            throw ApiError(kind: .network, statusCode: 0, reason: nil, message: "non-HTTP response")
        }
        guard (200..<300).contains(http.statusCode) else {
            throw ApiErrorMapper.map(statusCode: http.statusCode, body: data)
        }
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw ApiError(
                kind: .server,
                statusCode: http.statusCode,
                reason: nil,
                message: "decode error: \(error)"
            )
        }
    }
}
