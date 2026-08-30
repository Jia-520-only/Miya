package ai.miya.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class EarthAttr(
    val key: String = "",
    val label: String = "",
    val value: Int = 0,
    val max: Int = 100,
)

@Serializable
data class EarthPlayer(
    val id: Int = 1,
    val level: Int = 1,
    val exp: Int = 0,
    val currency: Int = 100,
    @SerialName("total_completed") val totalCompleted: Int = 0,
    @SerialName("total_failed") val totalFailed: Int = 0,
    val name: String = "开拓者",
    val title: String = "",
    @SerialName("avatar_path") val avatarPath: String = "",
    val bio: String = "",
    val attrs: List<EarthAttr> = emptyList(),
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
)

@Serializable
data class EarthItem(
    val id: Int = 0,
    val name: String = "",
    val category: String = "other",
    val rarity: String = "common",
    val quantity: Int = 1,
    val description: String = "",
    @SerialName("image_path") val imagePath: String = "",
    val status: String = "normal",
    val markdown: String = "",
    val fields: Map<String, JsonElement> = emptyMap(),
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class EarthQuest(
    val id: Int = 0,
    val title: String = "",
    val description: String = "",
    @SerialName("quest_type") val questType: String = "branch",
    @SerialName("must_complete") val mustComplete: Boolean = false,
    val status: String = "pending",
    @SerialName("reward_currency") val rewardCurrency: Int = 0,
    @SerialName("reward_exp") val rewardExp: Int = 0,
    @SerialName("penalty_currency") val penaltyCurrency: Int = 0,
    val deadline: String = "",
    val source: String = "manual",
    val difficulty: Int = 1,
    val fields: Map<String, JsonElement> = emptyMap(),
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("completed_at") val completedAt: String? = null,
)

@Serializable
data class EarthCharacter(
    val id: Int = 0,
    val name: String = "",
    val nickname: String = "",
    val relationship: String = "friend",
    val affinity: Int = 0,
    @SerialName("avatar_path") val avatarPath: String = "",
    val notes: String = "",
    val birthday: String = "",
    val markdown: String = "",
    val fields: Map<String, JsonElement> = emptyMap(),
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class EarthStory(
    val id: Int = 0,
    val title: String = "",
    val content: String = "",
    @SerialName("event_type") val eventType: String = "life",
    @SerialName("character_id") val characterId: Int? = null,
    @SerialName("item_id") val itemId: Int? = null,
    @SerialName("happened_at") val happenedAt: String = "",
    val fields: Map<String, JsonElement> = emptyMap(),
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class EarthSummary(
    val player: EarthPlayer = EarthPlayer(),
    val stats: EarthStats = EarthStats(),
)

@Serializable
data class EarthStats(
    @SerialName("active_quests") val activeQuests: Int = 0,
    val items: Int = 0,
    val characters: Int = 0,
    val stories: Int = 0,
)

@Serializable
data class EarthQuestCompleteResponse(
    val success: Boolean = false,
    val player: EarthPlayer? = null,
    val reward: EarthReward? = null,
)

@Serializable
data class EarthReward(
    val currency: Int = 0,
    val exp: Int = 0,
)

@Serializable
data class EarthAffinityLog(
    val id: Int = 0,
    @SerialName("character_id") val characterId: Int = 0,
    val delta: Int = 0,
    val reason: String = "",
    @SerialName("created_at") val createdAt: String = "",
)

@Serializable
data class EarthUploadResponse(
    val success: Boolean = false,
    @SerialName("image_path") val imagePath: String = "",
    val url: String = "",
)

@Serializable
data class EarthActionResponse(
    val success: Boolean = false,
    val player: EarthPlayer? = null,
    val quest: EarthQuest? = null,
    val failed: Int = 0,
)

// ── 模板 ──

@Serializable
data class EarthTemplateField(
    val key: String = "",
    val label: String = "",
    val placeholder: String? = null,
)

@Serializable
data class EarthEntityTemplate(
    val label: String = "",
    val fields: List<EarthTemplateField> = emptyList(),
)

@Serializable
data class EarthQuestTemplate(
    val id: String = "",
    val label: String = "",
    @SerialName("reward_currency") val rewardCurrency: Int = 10,
    @SerialName("reward_exp") val rewardExp: Int = 15,
    @SerialName("penalty_currency") val penaltyCurrency: Int = 20,
    val difficulty: Int = 1,
    val fields: List<EarthTemplateField> = emptyList(),
)

@Serializable
data class EarthAffinityLevel(
    val min: Int = 0,
    val max: Int = 100,
    val label: String = "",
    val color: String = "#9e9e9e",
)

@Serializable
data class EarthTemplates(
    val items: Map<String, EarthEntityTemplate> = emptyMap(),
    val characters: Map<String, EarthEntityTemplate> = emptyMap(),
    val quests: List<EarthQuestTemplate> = emptyList(),
    @SerialName("affinity_levels") val affinityLevels: List<EarthAffinityLevel> = emptyList(),
)