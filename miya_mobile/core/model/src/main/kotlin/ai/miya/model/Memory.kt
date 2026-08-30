package ai.miya.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class MemoryStats(
    @SerialName("total") val total: Int = 0,
    @SerialName("dialogue_count") val dialogueCount: Int = 0,
    @SerialName("short_term_count") val shortTermCount: Int = 0,
    @SerialName("long_term_count") val longTermCount: Int = 0,
    @SerialName("nodeCount") val nodeCount: Int = 0,
    @SerialName("edgeCount") val edgeCount: Int = 0,
    @SerialName("memorySize") val memorySize: String? = null,
)

@Serializable
data class MemoryItem(
    val id: String = "",
    val content: String = "",
    val level: String = "",
    val tags: List<String> = emptyList(),
    val priority: Double = 0.0,
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class MemoryListResponse(
    val results: List<MemoryItem> = emptyList(),
)
