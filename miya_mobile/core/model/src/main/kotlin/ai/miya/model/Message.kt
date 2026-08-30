package ai.miya.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class ChatRequest(
    val message: String,
    @SerialName("session_id") val sessionId: String = "default",
    @SerialName("user_id") val userId: String? = null,
    @SerialName("usg_id") val usgId: String? = null,
    val platform: String = "mobile",
    @SerialName("image_data") val imageData: String? = null,
)

@Serializable
data class ChatResponse(
    val response: String,
    val timestamp: String? = null,
    val emotion: JsonElement? = null,
    val personality: JsonElement? = null,
    @SerialName("files") val files: List<FileItem>? = null,
    @SerialName("tools_used") val toolsUsed: JsonElement? = null,
    @SerialName("memory_retrieved") val memoryRetrieved: JsonElement? = null,
)

@Serializable
data class FileItem(
    val name: String? = null,
    val url: String? = null,
    val size: Long? = null,
    @SerialName("mime_type") val mimeType: String? = null,
    val base64: String? = null,
)

@Serializable
data class ChatSseEvent(
    @SerialName("session_id") val sessionId: String? = null,
    val plain: String? = null,
    val data: String? = null,
    val soul: String? = null,
    val personality: String? = null,
    val done: Boolean? = null,
    val error: String? = null,
    val message: String? = null,
)

@Serializable
data class SessionInfo(
    val id: String,
    val name: String? = null,
    @SerialName("display_name") val displayName: String? = null,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
    @SerialName("message_count") val messageCount: Int? = null,
    @SerialName("last_message") val lastMessage: String? = null,
)

@Serializable
data class NewSessionResponse(
    val id: String,
)

@Serializable
data class RenameSessionRequest(
    @SerialName("session_id") val sessionId: String,
    @SerialName("display_name") val displayName: String,
)

@Serializable
data class Message(
    val id: String? = null,
    val content: String = "",
    val role: String = "user",
    val timestamp: Long = 0L,
    @SerialName("image_data") val imageData: String? = null,
) {
    val isUser: Boolean get() = role == "user"
    val isMiya: Boolean get() = role == "assistant"
}
