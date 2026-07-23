package com.photomecha.core.api

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** ApiClient のリクエスト形式（docs/09 主経路の multipart 契約）と応答パースを固定する。 */
class ApiClientTest {

    private lateinit var server: MockWebServer
    private lateinit var client: ApiClient

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        client = ApiClient(server.url("/").toString(), tokenProvider = { "test-token" })
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun createMechDirectSendsMultipartWithPayloadAndCrop() = runBlocking {
        server.enqueue(
            MockResponse().setBody(
                """{"id": "m1", "object_id": "o1", "name": "テストメカ", "form": "bird",
                   "form_inference_version": "form_inference/1.0",
                   "stats": {"hp": 80, "atk": 60, "defense": 35, "spd": 90, "tec": 75, "en": 80, "luck": 7},
                   "art_url": "/media/art/m1.png",
                   "features": {"visual_entropy": 0.1}, "info_score": 0.25,
                   "algo_version": "features/1.0"}""",
            ),
        )
        val payload = MechDirectPayload(
            name = "テストメカ",
            algoVersion = "features/1.0",
            bbox = listOf(0.1, 0.2, 0.8, 0.9),
            features = mapOf("visual_entropy" to 0.1),
        )
        val response = client.createMechDirect(payload, byteArrayOf(1, 2, 3))

        assertEquals("m1", response.id)
        assertEquals("bird", response.form)
        val recorded = server.takeRequest()
        assertEquals("POST", recorded.method)
        assertEquals("/mechs", recorded.path)
        assertEquals("test-token", recorded.getHeader("X-User-Token"))
        assertTrue(recorded.getHeader("Content-Type")!!.startsWith("multipart/form-data"))
        val body = recorded.body.readUtf8()
        assertTrue(body.contains("name=\"payload\""))
        assertTrue(body.contains("name=\"crop\""))
        assertTrue(body.contains("\"algo_version\":\"features/1.0\""))
    }

    @Test
    fun battleDetailParsesStructuredLogEntries() = runBlocking {
        server.enqueue(
            MockResponse().setBody(
                """{"id": "b1", "seed": 42, "winner_team_id": "player", "turns": 2,
                   "log": "Turn 1 ...",
                   "log_entries": [
                     {"turn": 1, "actor_team": "player", "actor_position": "front",
                      "actor_name": "テストメカ", "condition_label": "常に", "action": "attack_nearest",
                      "damage_events": [
                        {"target_id": "cpu-front", "target_name": "CPU前衛", "damage": 12, "defeated": false}
                      ], "note": ""}
                   ]}""",
            ),
        )
        val detail = client.battleDetail("b1")
        assertEquals("player", detail.winnerTeamId)
        assertEquals(1, detail.logEntries.size)
        val entry = detail.logEntries.first()
        assertEquals(1, entry.turn)
        assertEquals("front", entry.actorPosition)
        assertEquals("常に", entry.conditionLabel)
        assertEquals(12, entry.damageEvents.first().damage)
    }

    @Test
    fun errorResponsesRaiseMappedException() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(429).setBody("""{"detail": "mechs quota exceeded"}"""))
        val error = try {
            client.listMechs()
            null
        } catch (e: ApiException) {
            e
        }
        assertEquals(ApiErrorKind.QUOTA_EXCEEDED, error!!.kind)
    }
}
