package ai.miya.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class EmotionState(
    val dominant: String = "neutral",
    val intensity: Int = 50,
    val emotions: List<EmotionItem> = emptyList(),
    @SerialName("inner_thought") val innerThought: String? = null,
)

@Serializable
data class EmotionItem(
    val name: String,
    val intensity: Int,
)

@Serializable
data class EmotionResponse(
    @SerialName("dominant_emotion") val dominantEmotion: String = "neutral",
    val intensity: Int = 50,
    val emotions: List<EmotionItem> = emptyList(),
)

@Serializable
data class EmotionUpdate(
    val type: String = "miya_emotion",
    val data: EmotionPayload? = null,
)

@Serializable
data class EmotionPayload(
    val dominant: String,
    val intensity: Int,
    val previous: String? = null,
)

enum class MiyaEmotion(val displayName: String, val live2dKey: String) {
    HAPPY("开心", "happy"),
    SAD("悲伤", "sad"),
    ANGRY("愤怒", "angry"),
    SURPRISE("惊讶", "surprise"),
    NEUTRAL("平静", "neutral"),
    JOY("喜悦", "happy"),
    TRUST("信任", "neutral"),
    ANTICIPATION("期待", "surprise");

    companion object {
        fun fromDominant(dominant: String): MiyaEmotion {
            return entries.find {
                it.name.equals(dominant, ignoreCase = true) || it.displayName == dominant
            } ?: NEUTRAL
        }
    }
}
