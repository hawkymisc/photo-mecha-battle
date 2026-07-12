import XCTest
@testable import PhotoMechaCore
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// URLProtocol スタブで ApiClient の契約（multipart 形式・ログパース・エラー変換）を検証する。
final class ApiClientTests: XCTestCase {

    final class StubURLProtocol: URLProtocol {
        static var handler: ((URLRequest) -> (Int, Data))?
        static var lastRequest: URLRequest?
        static var lastBody: Data?

        override class func canInit(with request: URLRequest) -> Bool { true }
        override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

        override func startLoading() {
            Self.lastRequest = request
            Self.lastBody = request.httpBody ?? request.httpBodyStream.map { stream in
                stream.open()
                defer { stream.close() }
                var data = Data()
                let bufferSize = 64 * 1024
                var buffer = [UInt8](repeating: 0, count: bufferSize)
                while stream.hasBytesAvailable {
                    let read = stream.read(&buffer, maxLength: bufferSize)
                    if read <= 0 { break }
                    data.append(buffer, count: read)
                }
                return data
            }
            guard let (status, body) = Self.handler?(request) else {
                client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
                return
            }
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: status,
                httpVersion: "HTTP/1.1",
                headerFields: ["Content-Type": "application/json"]
            )!
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: body)
            client?.urlProtocolDidFinishLoading(self)
        }

        override func stopLoading() {}
    }

    private func makeClient() -> ApiClient {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubURLProtocol.self]
        return ApiClient(
            baseURL: URL(string: "http://stub.local")!,
            tokenProvider: { "test-token" },
            session: URLSession(configuration: config)
        )
    }

    override func tearDown() {
        StubURLProtocol.handler = nil
        StubURLProtocol.lastRequest = nil
        StubURLProtocol.lastBody = nil
        super.tearDown()
    }

    func testCreateMechDirectSendsMultipart() async throws {
        StubURLProtocol.handler = { _ in
            (200, Data(#"{"id": "m1", "name": "Test", "form": "beast", "stats": {"hp": 100}}"#.utf8))
        }
        let client = makeClient()
        let payload = MechDirectPayload(
            name: "Test",
            algoVersion: FeatureExtractor.algoVersion,
            bbox: [0.1, 0.1, 0.9, 0.9],
            features: ["visual_entropy": 0.5]
        )
        let pngBytes = Data([0x89, 0x50, 0x4E, 0x47])
        let response = try await client.createMechDirect(payload: payload, cropPng: pngBytes)

        XCTAssertEqual(response.id, "m1")
        let request = try XCTUnwrap(StubURLProtocol.lastRequest)
        XCTAssertEqual(request.url?.path, "/mechs")
        XCTAssertEqual(request.value(forHTTPHeaderField: "X-User-Token"), "test-token")
        let contentType = try XCTUnwrap(request.value(forHTTPHeaderField: "Content-Type"))
        XCTAssertTrue(contentType.hasPrefix("multipart/form-data; boundary="))

        let body = try XCTUnwrap(StubURLProtocol.lastBody)
        let bodyString = String(decoding: body, as: UTF8.self)
        XCTAssertTrue(bodyString.contains("name=\"payload\""))
        XCTAssertTrue(bodyString.contains("name=\"crop\""))
        XCTAssertTrue(bodyString.contains("\"algo_version\":\"features\\/1.0\"")
            || bodyString.contains("\"algo_version\":\"features/1.0\""))
    }

    func testBattleDetailParsesLogEntries() async throws {
        StubURLProtocol.handler = { _ in
            (200, Data("""
            {
                "id": "b1", "seed": 42, "winner_team_id": "player", "turns": 3, "log": "x",
                "log_entries": [
                    {
                        "turn": 1, "actor_team": "player", "actor_position": "front",
                        "actor_name": "Alpha", "condition_label": "基本行動", "action": "normal_attack",
                        "damage_events": [
                            {"target_id": "e1", "target_name": "CPU前衛", "damage": 12, "defeated": false}
                        ]
                    }
                ]
            }
            """.utf8))
        }
        let client = makeClient()
        let battle = try await client.battleDetail(battleId: "b1")
        XCTAssertEqual(battle.winnerTeamId, "player")
        XCTAssertEqual(battle.logEntries.count, 1)
        XCTAssertEqual(battle.logEntries[0].damageEvents[0].damage, 12)
        XCTAssertEqual(battle.logEntries[0].note, "")
    }

    func testQuotaErrorMapsToApiError() async throws {
        StubURLProtocol.handler = { _ in
            (429, Data(#"{"detail": {"error": "quota_exceeded", "reason": "captures"}}"#.utf8))
        }
        let client = makeClient()
        do {
            _ = try await client.quotas()
            XCTFail("expected ApiError")
        } catch let error as ApiError {
            XCTAssertEqual(error.kind, .quotaExceeded)
            XCTAssertEqual(error.reason, "captures")
        }
    }
}
