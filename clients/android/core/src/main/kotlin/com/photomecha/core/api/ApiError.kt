package com.photomecha.core.api

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonPrimitive

/**
 * docs/11 エラー時遷移: API エラーをユーザー導線種別へマッピングする。
 *
 * | 種別 | 導線 |
 * |---|---|
 * | UNAUTHORIZED | トークン破棄 → 再登録 (S00) |
 * | DUPLICATE | 再撮影 (S02) |
 * | UNSAFE_CAPTURE | reason 別に再撮影 / 選択やり直し |
 * | CLIENT_OUTDATED | アプリ更新案内（feature_mismatch / unsupported_algo_version） |
 * | QUOTA_EXCEEDED | ホームへ（翌日回復の案内） |
 * | INVALID / NOT_FOUND / SERVER / NETWORK | リトライ導線 |
 */
enum class ApiErrorKind {
    UNAUTHORIZED,
    DUPLICATE,
    UNSAFE_CAPTURE,
    CLIENT_OUTDATED,
    QUOTA_EXCEEDED,
    INVALID,
    NOT_FOUND,
    SERVER,
    NETWORK,
}

class ApiException(
    val kind: ApiErrorKind,
    val statusCode: Int,
    val reason: String? = null,
    message: String,
    cause: Throwable? = null,
) : Exception(message, cause)

object ApiErrorMapper {
    private val json = Json { ignoreUnknownKeys = true }

    fun map(statusCode: Int, body: String?): ApiException {
        val detail = runCatching { json.decodeFromString<ErrorEnvelope>(body ?: "").detail }.getOrNull()
        val detailObject = detail as? JsonObject
        val errorCode = (detailObject?.get("error") as? JsonPrimitive)?.content
        val reason = (detailObject?.get("reason") as? JsonPrimitive)?.content
        val detailText = (detail as? JsonPrimitive)?.content ?: body.orEmpty()

        val kind = when {
            statusCode == 401 -> ApiErrorKind.UNAUTHORIZED
            statusCode == 404 -> ApiErrorKind.NOT_FOUND
            statusCode == 409 -> ApiErrorKind.DUPLICATE
            statusCode == 429 -> ApiErrorKind.QUOTA_EXCEEDED
            statusCode == 422 && errorCode == "unsafe_capture" -> ApiErrorKind.UNSAFE_CAPTURE
            statusCode == 422 && (errorCode == "feature_mismatch" || errorCode == "unsupported_algo_version") ->
                ApiErrorKind.CLIENT_OUTDATED
            statusCode == 400 || statusCode == 422 -> ApiErrorKind.INVALID
            statusCode >= 500 -> ApiErrorKind.SERVER
            else -> ApiErrorKind.SERVER
        }
        return ApiException(
            kind = kind,
            statusCode = statusCode,
            reason = reason ?: errorCode,
            message = "API error $statusCode: ${errorCode ?: detailText}",
        )
    }
}
