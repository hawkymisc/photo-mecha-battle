package com.photomecha.core.api

import org.junit.Assert.assertEquals
import org.junit.Test

/** docs/11 エラー時遷移: ステータス + detail 構造 → 導線種別のマッピングを固定する。 */
class ApiErrorMapperTest {

    @Test
    fun unauthorizedMapsToReRegistration() {
        val error = ApiErrorMapper.map(401, """{"detail": "invalid token"}""")
        assertEquals(ApiErrorKind.UNAUTHORIZED, error.kind)
    }

    @Test
    fun duplicateCaptureMapsToRecapture() {
        val error = ApiErrorMapper.map(409, """{"detail": "duplicate capture"}""")
        assertEquals(ApiErrorKind.DUPLICATE, error.kind)
    }

    @Test
    fun unsafeCaptureCarriesReason() {
        val body = """{"detail": {"error": "unsafe_capture", "reason": "face_detected", "action": "recapture"}}"""
        val error = ApiErrorMapper.map(422, body)
        assertEquals(ApiErrorKind.UNSAFE_CAPTURE, error.kind)
        assertEquals("face_detected", error.reason)
    }

    @Test
    fun featureMismatchMapsToClientOutdated() {
        val body = """{"detail": {"error": "feature_mismatch", "dimension": "elongation",
            "client": 0.9, "server": 0.7, "tolerance": 0.05}}"""
        val error = ApiErrorMapper.map(422, body)
        assertEquals(ApiErrorKind.CLIENT_OUTDATED, error.kind)
    }

    @Test
    fun unsupportedAlgoVersionMapsToClientOutdated() {
        val body = """{"detail": {"error": "unsupported_algo_version", "sent": "features/0.9",
            "supported": ["features/1.0"]}}"""
        val error = ApiErrorMapper.map(422, body)
        assertEquals(ApiErrorKind.CLIENT_OUTDATED, error.kind)
    }

    @Test
    fun quotaExceededMapsToQuota() {
        val error = ApiErrorMapper.map(429, """{"detail": "mechs quota exceeded"}""")
        assertEquals(ApiErrorKind.QUOTA_EXCEEDED, error.kind)
    }

    @Test
    fun plainValidationErrorMapsToInvalid() {
        val error = ApiErrorMapper.map(422, """{"detail": "invalid payload: broken"}""")
        assertEquals(ApiErrorKind.INVALID, error.kind)
    }

    @Test
    fun serverErrorMapsToServer() {
        val error = ApiErrorMapper.map(500, "internal error")
        assertEquals(ApiErrorKind.SERVER, error.kind)
    }
}
