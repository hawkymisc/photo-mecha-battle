package com.photomecha.core.api

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class RegisterRequest(val name: String)

@Serializable
data class RegisterResponse(
    @SerialName("user_id") val userId: String,
    val name: String,
    val token: String,
    val rating: Int,
)

@Serializable
data class QuotaEntry(val used: Int, val limit: Int, val remaining: Int)

@Serializable
data class QuotasResponse(val captures: QuotaEntry, val mechs: QuotaEntry)

@Serializable
data class MechDirectPayload(
    val name: String,
    @SerialName("algo_version") val algoVersion: String,
    val bbox: List<Double>? = null,
    val features: Map<String, Double>,
)

@Serializable
data class MechResponse(
    val id: String,
    @SerialName("object_id") val objectId: String? = null,
    val name: String,
    val form: String,
    val stats: Map<String, Int>,
    @SerialName("art_url") val artUrl: String? = null,
    val features: Map<String, Double>? = null,
    @SerialName("info_score") val infoScore: Double? = null,
)

@Serializable
data class MechListResponse(val mechs: List<MechSummary>)

@Serializable
data class MechSummary(
    val id: String,
    val name: String,
    val form: String,
    val stats: Map<String, Int>,
    @SerialName("art_url") val artUrl: String? = null,
)

@Serializable
data class TacticPreset(val id: String, val name: String, val label: String)

@Serializable
data class TacticPresetsResponse(val presets: List<TacticPreset>)

@Serializable
data class BattleSlotRequest(
    @SerialName("mech_id") val mechId: String,
    val position: String,
    val preset: String,
)

@Serializable
data class BattleCreateRequest(
    @SerialName("team_name") val teamName: String,
    val slots: List<BattleSlotRequest>,
    val seed: Int,
)

@Serializable
data class BattleCreateResponse(
    val id: String,
    val seed: Long,
    @SerialName("winner_team_id") val winnerTeamId: String? = null,
    val turns: Int,
    val log: String,
)

@Serializable
data class DamageEvent(
    @SerialName("target_id") val targetId: String,
    @SerialName("target_name") val targetName: String,
    val damage: Int,
    val defeated: Boolean,
)

@Serializable
data class BattleLogEntry(
    val turn: Int,
    @SerialName("actor_team") val actorTeam: String,
    @SerialName("actor_position") val actorPosition: String,
    @SerialName("actor_name") val actorName: String,
    @SerialName("condition_label") val conditionLabel: String,
    val action: String,
    @SerialName("damage_events") val damageEvents: List<DamageEvent> = emptyList(),
    val note: String = "",
)

@Serializable
data class BattleDetailResponse(
    val id: String,
    val seed: Long,
    @SerialName("winner_team_id") val winnerTeamId: String? = null,
    val turns: Int,
    val log: String,
    @SerialName("log_entries") val logEntries: List<BattleLogEntry> = emptyList(),
)

@Serializable
data class ErrorEnvelope(val detail: JsonElement? = null)
