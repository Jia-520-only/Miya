package ai.miya.network

import ai.miya.model.*
import io.ktor.client.*
import io.ktor.client.call.*
import io.ktor.client.plugins.*
import io.ktor.client.plugins.contentnegotiation.*
import io.ktor.client.plugins.logging.*
import io.ktor.client.request.*
import io.ktor.client.statement.*
import io.ktor.http.*
import io.ktor.serialization.kotlinx.json.*
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.serialization.json.Json

class MiyaApiClient(
    baseUrl: String = "http://localhost:8000",
) {
    @Volatile
    var baseUrl: String = baseUrl
        private set

    fun updateBaseUrl(newBaseUrl: String) {
        baseUrl = newBaseUrl
    }

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        encodeDefaults = true
    }

    private val client = HttpClient {
        install(ContentNegotiation) {
            json(this@MiyaApiClient.json)
        }
        install(Logging) {
            level = LogLevel.HEADERS
        }
        install(HttpTimeout) {
            requestTimeoutMillis = 120_000
            connectTimeoutMillis = 10_000
        }
        defaultRequest {
            contentType(ContentType.Application.Json)
        }
    }

    private fun apiUrl(path: String): String = "$baseUrl$path"

    // ── 健康检查 ──

    suspend fun health(): Boolean {
        return try {
            client.get(apiUrl("/health")).status == HttpStatusCode.OK
        } catch (_: Exception) {
            false
        }
    }

    // ── 系统状态 ──

    suspend fun systemStatus(): SystemStatus {
        return client.get(apiUrl("/api/status")).body()
    }

    // ── 情感 ──

    suspend fun getEmotion(): EmotionResponse {
        return client.get(apiUrl("/api/emotion")).body()
    }

    // ── 聊天 (非流式) ──

    suspend fun sendMessage(request: ChatRequest): ChatResponse {
        val response = client.post(apiUrl("/api/chat")) {
            setBody(request)
        }
        return response.body()
    }

    // ── 聊天 (JSON 非流式，兼容旧接口名) ──

    fun chatStream(request: ChatRequest): Flow<String> = flow {
        val result: ChatResponse = client.post(apiUrl("/api/chat")) {
            setBody(request)
        }.body()
        emit(result.response)
    }

    suspend fun stopChat(): Boolean {
        return try {
            client.post(apiUrl("/api/chat/stop"))
            true
        } catch (_: Exception) {
            false
        }
    }

    // ── 会话管理 ──

    suspend fun listSessions(): List<SessionInfo> {
        return try {
            client.get(apiUrl("/api/chat/sessions")).body()
        } catch (_: Exception) {
            emptyList()
        }
    }

    suspend fun newSession(): NewSessionResponse {
        return client.get(apiUrl("/api/chat/new_session")).body()
    }

    suspend fun deleteSession(sessionId: String) {
        client.get(apiUrl("/api/chat/delete_session?session_id=$sessionId"))
    }

    suspend fun updateSessionName(sessionId: String, name: String) {
        client.post(apiUrl("/api/chat/update_session_display_name")) {
            setBody(RenameSessionRequest(sessionId, name))
        }
    }

    // ── 记忆 ──

    suspend fun getMemoryStats(): MemoryStats {
        return client.get(apiUrl("/api/memory/stats")).body()
    }

    suspend fun searchMemory(query: String, limit: Int = 20): List<MemoryItem> {
        return try {
            val response: MemoryListResponse = client.get(
                apiUrl("/api/memory/search?query=$query&limit=$limit")
            ).body()
            response.results
        } catch (_: Exception) {
            emptyList()
        }
    }

    suspend fun getMemoryList(limit: Int = 50): List<MemoryItem> {
        return try {
            val response: MemoryListResponse = client.get(
                apiUrl("/api/memory/list?limit=$limit")
            ).body()
            response.results
        } catch (_: Exception) {
            emptyList()
        }
    }

    // ── 人格 ──

    suspend fun getPersonaList(): List<Persona> {
        return try {
            val response: PersonaListResponse = client.get(
                apiUrl("/api/persona/list")
            ).body()
            response.personalities
        } catch (_: Exception) {
            emptyList()
        }
    }

    suspend fun getCurrentPersona(): PersonaCurrentResponse {
        return client.get(apiUrl("/api/persona/current")).body()
    }

    suspend fun switchPersona(personalityId: String): SwitchPersonaResponse {
        return client.post(apiUrl("/api/persona/switch")) {
            setBody(SwitchPersonaRequest(personalityId))
        }.body()
    }

    // ── TTS ──

    suspend fun textToSpeech(
        text: String,
        voice: String? = null,
        speed: Float = 1.0f,
        engine: String = "edge_tts",
    ): ByteArray? {
        return try {
            val response = client.post(apiUrl("/tts/speech")) {
                setBody(mapOf(
                    "input" to text,
                    "voice" to voice,
                    "speed" to speed,
                    "engine" to engine,
                    "response_format" to "mp3",
                ))
            }
            response.body<ByteArray>()
        } catch (_: Exception) {
            null
        }
    }

    // ── 模型 ──

    suspend fun getModelList(): List<Map<String, String>> {
        return try {
            client.get(apiUrl("/api/models/list")).body()
        } catch (_: Exception) {
            emptyList()
        }
    }

    // ── Emoji ──

    suspend fun getEmojiList(): EmojiListResponse {
        return try {
            client.get(apiUrl("/api/emoji/list")).body()
        } catch (_: Exception) {
            EmojiListResponse()
        }
    }

    // ── Proactive Messages ──

    suspend fun getPendingMessages(userId: String): List<Map<String, String>> {
        return try {
            val resp: PendingMessageResponse = client.get(apiUrl("/api/chat/pending/$userId")).body()
            resp.messages
        } catch (_: Exception) {
            emptyList()
        }
    }

    // ── FCM Token ──

    suspend fun registerFcmToken(token: String) {
        try {
            client.post(apiUrl("/api/chat/register_fcm_token")) {
                setBody(mapOf("token" to token, "platform" to "android"))
            }
        } catch (_: Exception) {}
    }

    // ── Session Messages (History Sync) ──

    suspend fun getSessionMessages(sessionId: String): List<SessionHistoryItem> {
        return try {
            val resp: SessionHistoryResponse = client.get(
                apiUrl("/api/chat/get_session?session_id=$sessionId")
            ).body()
            resp.data?.history ?: emptyList()
        } catch (_: Exception) {
            emptyList()
        }
    }

    // ── 地球online ──

    suspend fun earthSummary(): EarthSummary {
        return try {
            client.get(apiUrl("/api/earth/summary")).body()
        } catch (_: Exception) {
            EarthSummary()
        }
    }

    suspend fun earthPlayer(): EarthPlayer {
        return try {
            client.get(apiUrl("/api/earth/player")).body()
        } catch (_: Exception) {
            EarthPlayer()
        }
    }

    /** 服务器可达性探测: 失败时抛出异常 (供离线检测) */
    suspend fun earthPing(): Boolean {
        return try {
            client.get(apiUrl("/api/earth/player")).status.value in 200..299
        } catch (_: Exception) {
            false
        }
    }

    suspend fun earthTemplates(): EarthTemplates {
        return try {
            client.get(apiUrl("/api/earth/templates")).body()
        } catch (_: Exception) {
            EarthTemplates()
        }
    }

    suspend fun earthListItems(): List<EarthItem> {
        return try {
            client.get(apiUrl("/api/earth/items")).body()
        } catch (_: Exception) {
            emptyList()
        }
    }

    suspend fun earthCreateItem(data: Map<String, Any?>): EarthItem {
        return client.post(apiUrl("/api/earth/items")) { setBody(data) }.body()
    }

    suspend fun earthUpdateItem(itemId: Int, data: Map<String, Any?>): EarthItem {
        return client.put(apiUrl("/api/earth/items/$itemId")) { setBody(data) }.body()
    }

    /** 上传地球online 图片（物品照片/角色头像），itemId 非空时绑定到物品 */
    suspend fun earthUploadItemImage(fileName: String, bytes: ByteArray, mimeType: String, itemId: Int? = null): EarthUploadResponse {
        return try {
            val url = if (itemId != null) "${apiUrl("/api/earth/items/upload")}?item_id=$itemId" else apiUrl("/api/earth/items/upload")
            client.post(url) {
                setBody(io.ktor.client.request.forms.MultiPartFormDataContent(
                    io.ktor.client.request.forms.formData {
                        append("file", bytes, io.ktor.http.Headers.build {
                            append(io.ktor.http.HttpHeaders.ContentDisposition, "filename=\"$fileName\"")
                            append(io.ktor.http.HttpHeaders.ContentType, mimeType)
                        })
                    }
                ))
            }.body()
        } catch (_: Exception) {
            EarthUploadResponse()
        }
    }

    suspend fun earthDeleteItem(itemId: Int): Boolean {
        return try {
            client.delete(apiUrl("/api/earth/items/$itemId"))
            true
        } catch (_: Exception) {
            false
        }
    }

    suspend fun earthListQuests(): List<EarthQuest> {
        return try {
            client.get(apiUrl("/api/earth/quests")).body()
        } catch (_: Exception) {
            emptyList()
        }
    }

    suspend fun earthCreateQuest(data: Map<String, Any?>): EarthQuest {
        return client.post(apiUrl("/api/earth/quests")) { setBody(data) }.body()
    }

    suspend fun earthCompleteQuest(questId: Int): EarthQuestCompleteResponse {
        return try {
            client.post(apiUrl("/api/earth/quests/$questId/complete")).body()
        } catch (_: Exception) {
            EarthQuestCompleteResponse()
        }
    }

    suspend fun earthAcceptQuest(questId: Int): EarthQuest {
        return try {
            client.post(apiUrl("/api/earth/quests/$questId/accept")).body<EarthActionResponse>().quest ?: EarthQuest()
        } catch (_: Exception) {
            EarthQuest()
        }
    }

    suspend fun earthFailQuest(questId: Int): EarthQuestCompleteResponse {
        return try {
            client.post(apiUrl("/api/earth/quests/$questId/fail")).body()
        } catch (_: Exception) {
            EarthQuestCompleteResponse()
        }
    }

    suspend fun earthCancelQuest(questId: Int): Boolean {
        return try {
            client.post(apiUrl("/api/earth/quests/$questId/cancel"))
            true
        } catch (_: Exception) {
            false
        }
    }

    suspend fun earthCheckOverdue(): Int {
        return try {
            val resp: EarthActionResponse = client.post(apiUrl("/api/earth/quests/check-overdue")).body()
            resp.failed
        } catch (_: Exception) {
            0
        }
    }

    suspend fun earthListCharacters(): List<EarthCharacter> {
        return try {
            client.get(apiUrl("/api/earth/characters")).body()
        } catch (_: Exception) {
            emptyList()
        }
    }

    suspend fun earthCreateCharacter(data: Map<String, Any?>): EarthCharacter {
        return client.post(apiUrl("/api/earth/characters")) { setBody(data) }.body()
    }

    suspend fun earthUpdateCharacter(characterId: Int, data: Map<String, Any?>): EarthCharacter {
        return client.put(apiUrl("/api/earth/characters/$characterId")) { setBody(data) }.body()
    }

    suspend fun earthAddAffinity(characterId: Int, delta: Int, reason: String): EarthCharacter {
        return client.post(apiUrl("/api/earth/characters/$characterId/affinity")) {
            setBody(mapOf("delta" to delta, "reason" to reason))
        }.body()
    }

    suspend fun earthDeleteCharacter(characterId: Int): Boolean {
        return try {
            client.delete(apiUrl("/api/earth/characters/$characterId"))
            true
        } catch (_: Exception) {
            false
        }
    }

    suspend fun earthListStory(): List<EarthStory> {
        return try {
            client.get(apiUrl("/api/earth/story")).body()
        } catch (_: Exception) {
            emptyList()
        }
    }

    suspend fun earthCreateStory(data: Map<String, Any?>): EarthStory {
        return client.post(apiUrl("/api/earth/story")) { setBody(data) }.body()
    }

    fun earthImageUrl(path: String): String {
        if (path.isEmpty()) return ""
        if (path.startsWith("http")) return path
        return "$baseUrl$path"
    }

    // ── File Download ──

    suspend fun downloadFile(fileUrl: String): ByteArray? {
        return try {
            val url = if (fileUrl.startsWith("http")) fileUrl else apiUrl(fileUrl)
            client.get(url).body<ByteArray>()
        } catch (_: Exception) {
            null
        }
    }

    // ── File Upload ──

    suspend fun uploadFile(fileName: String, bytes: ByteArray, mimeType: String): Map<String, String> {
        return try {
            client.post(apiUrl("/api/chat/upload")) {
                setBody(io.ktor.client.request.forms.MultiPartFormDataContent(
                    io.ktor.client.request.forms.formData {
                        append("file", bytes, io.ktor.http.Headers.build {
                            append(io.ktor.http.HttpHeaders.ContentDisposition, "filename=\"$fileName\"")
                            append(io.ktor.http.HttpHeaders.ContentType, mimeType)
                        })
                    }
                ))
            }.body()
        } catch (_: Exception) {
            mapOf("success" to "false", "preview" to "上传失败")
        }
    }

    fun close() {
        client.close()
    }
}

@kotlinx.serialization.Serializable
data class EmojiFileItem(
    val name: String = "",
    val url: String = "",
)

@kotlinx.serialization.Serializable
data class EmojiCategory(
    val name: String = "",
    val files: List<EmojiFileItem> = emptyList(),
)

@kotlinx.serialization.Serializable
data class EmojiListResponse(
    val categories: List<EmojiCategory> = emptyList(),
)

@kotlinx.serialization.Serializable
data class PendingMessageResponse(
    val messages: List<Map<String, String>> = emptyList(),
)

@kotlinx.serialization.Serializable
data class SessionHistoryItem(
    val role: String = "",
    val content: String = "",
    val timestamp: String = "",
)

@kotlinx.serialization.Serializable
data class SessionHistoryData(
    @kotlinx.serialization.SerialName("session_id") val sessionId: String = "",
    val history: List<SessionHistoryItem> = emptyList(),
)

@kotlinx.serialization.Serializable
data class SessionHistoryResponse(
    val success: Boolean = false,
    val data: SessionHistoryData? = null,
)
