import XCTest
@testable import PhotoMechaCore

/// docs/11 エラー時遷移マッピングのテスト（Android ApiErrorMapperTest と同一ケース）。
final class ApiErrorMapperTests: XCTestCase {

    private func body(_ json: String) -> Data { Data(json.utf8) }

    func testUnauthorized() {
        let error = ApiErrorMapper.map(statusCode: 401, body: body(#"{"detail": "invalid token"}"#))
        XCTAssertEqual(error.kind, .unauthorized)
        XCTAssertEqual(error.statusCode, 401)
    }

    func testDuplicate() {
        let error = ApiErrorMapper.map(
            statusCode: 409,
            body: body(#"{"detail": {"error": "duplicate_capture"}}"#)
        )
        XCTAssertEqual(error.kind, .duplicate)
    }

    func testQuotaExceeded() {
        let error = ApiErrorMapper.map(
            statusCode: 429,
            body: body(#"{"detail": {"error": "quota_exceeded", "reason": "mechs"}}"#)
        )
        XCTAssertEqual(error.kind, .quotaExceeded)
        XCTAssertEqual(error.reason, "mechs")
    }

    func testUnsafeCaptureWithReason() {
        let error = ApiErrorMapper.map(
            statusCode: 422,
            body: body(#"{"detail": {"error": "unsafe_capture", "reason": "face_detected"}}"#)
        )
        XCTAssertEqual(error.kind, .unsafeCapture)
        XCTAssertEqual(error.reason, "face_detected")
    }

    func testFeatureMismatchIsClientOutdated() {
        let error = ApiErrorMapper.map(
            statusCode: 422,
            body: body(#"{"detail": {"error": "feature_mismatch"}}"#)
        )
        XCTAssertEqual(error.kind, .clientOutdated)
    }

    func testUnsupportedAlgoVersionIsClientOutdated() {
        let error = ApiErrorMapper.map(
            statusCode: 422,
            body: body(#"{"detail": {"error": "unsupported_algo_version"}}"#)
        )
        XCTAssertEqual(error.kind, .clientOutdated)
    }

    func testGenericUnprocessableIsInvalid() {
        let error = ApiErrorMapper.map(statusCode: 422, body: body(#"{"detail": "invalid bbox"}"#))
        XCTAssertEqual(error.kind, .invalid)
    }

    func testNotFound() {
        let error = ApiErrorMapper.map(statusCode: 404, body: nil)
        XCTAssertEqual(error.kind, .notFound)
    }

    func testServerError() {
        let error = ApiErrorMapper.map(statusCode: 500, body: body("internal"))
        XCTAssertEqual(error.kind, .server)
    }

    func testMalformedBodyFallsBack() {
        let error = ApiErrorMapper.map(statusCode: 422, body: body("not-json"))
        XCTAssertEqual(error.kind, .invalid)
    }
}
