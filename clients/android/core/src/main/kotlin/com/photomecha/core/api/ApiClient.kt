package com.photomecha.core.api

import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Photo Mecha Battle API クライアント（docs/11 Phase 1 経路）。
 *
 * バトルはサーバー権威（docs/09 信頼モデル）。このクラスはサーバー応答を
 * そのまま返すだけで、勝敗・ダメージ・ステータスを再計算しない。
 */
class ApiClient(
    val baseUrl: String,
    private val tokenProvider: () -> String?,
    private val httpClient: OkHttpClient = OkHttpClient(),
) {
    private val json = Json { ignoreUnknownKeys = true }
    private val jsonMediaType = "application/json".toMediaType()
    private val pngMediaType = "image/png".toMediaType()

    suspend fun register(name: String): RegisterResponse =
        post("/auth/register", json.encodeToString(RegisterRequest.serializer(), RegisterRequest(name)))

    suspend fun quotas(): QuotasResponse = get("/users/quotas")

    suspend fun listMechs(): MechListResponse = get("/mechs")

    suspend fun mechDetail(mechId: String): MechResponse = get("/mechs/$mechId")

    suspend fun tacticPresets(): TacticPresetsResponse = get("/tactic-presets")

    /** docs/09 主経路: multipart（payload JSON + crop RGBA PNG）でのメカ直登録。 */
    suspend fun createMechDirect(payload: MechDirectPayload, cropPng: ByteArray): MechResponse {
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("payload", json.encodeToString(MechDirectPayload.serializer(), payload))
            .addFormDataPart("crop", "crop.png", cropPng.toRequestBody(pngMediaType))
            .build()
        val request = requestBuilder("/mechs").post(body).build()
        return execute(request)
    }

    suspend fun createDemoBattle(request: BattleCreateRequest): BattleCreateResponse =
        post("/battles", json.encodeToString(BattleCreateRequest.serializer(), request))

    suspend fun battleDetail(battleId: String): BattleDetailResponse = get("/battles/$battleId")

    fun mediaUrl(path: String?): String? = path?.let { baseUrl.trimEnd('/') + it }

    private suspend inline fun <reified T> get(path: String): T =
        execute(requestBuilder(path).get().build())

    private suspend inline fun <reified T> post(path: String, bodyJson: String): T =
        execute(requestBuilder(path).post(bodyJson.toRequestBody(jsonMediaType)).build())

    private fun requestBuilder(path: String): Request.Builder {
        val builder = Request.Builder().url(baseUrl.trimEnd('/') + path)
        tokenProvider()?.let { builder.header("X-User-Token", it) }
        return builder
    }

    private suspend inline fun <reified T> execute(request: Request): T = withContext(Dispatchers.IO) {
        val response = try {
            httpClient.newCall(request).await()
        } catch (e: IOException) {
            throw ApiException(ApiErrorKind.NETWORK, 0, null, "network error: ${e.message}", e)
        }
        response.use {
            val bodyText = it.body?.string()
            if (!it.isSuccessful) throw ApiErrorMapper.map(it.code, bodyText)
            json.decodeFromString<T>(bodyText ?: error("empty response body"))
        }
    }
}

private suspend fun Call.await(): Response = suspendCancellableCoroutine { continuation ->
    enqueue(object : Callback {
        override fun onFailure(call: Call, e: IOException) {
            continuation.resumeWithException(e)
        }

        override fun onResponse(call: Call, response: Response) {
            continuation.resume(response)
        }
    })
    continuation.invokeOnCancellation {
        runCatching { cancel() }.onFailure {
            // キャンセル競合時の二重 cancel は無害（OkHttp 仕様）
        }
    }
}
