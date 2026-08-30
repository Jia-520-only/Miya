package ai.miya.network

import ai.miya.domain.WsEvent
import io.ktor.client.*
import io.ktor.client.plugins.websocket.*
import io.ktor.websocket.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.serialization.json.*

class MiyaWebSocket(private var wsUrl: String = "ws://localhost:9800/api/v1/ws") {

    private val json = Json { ignoreUnknownKeys = true; isLenient = true }
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var session: WebSocketSession? = null
    private var reconnectJob: Job? = null

    private val _events = MutableSharedFlow<WsEvent>(extraBufferCapacity = 64)
    val events: SharedFlow<WsEvent> = _events.asSharedFlow()

    val isConnected: Boolean get() = session != null

    fun updateUrl(newUrl: String) {
        wsUrl = newUrl
    }

    fun connect() {
        disconnect()
        scope.launch {
            var retryDelay = 1000L
            val maxDelay = 30_000L

            while (isActive) {
                try {
                    val client = HttpClient { install(WebSockets) }
                    client.webSocket(wsUrl) {
                        session = this
                        _events.emit(WsEvent.Connected)
                        retryDelay = 1000L

                        for (frame in incoming) {
                            when (frame) {
                                is Frame.Text -> {
                                    val text = frame.readText()
                                    processMessage(text)
                                }
                                else -> {}
                            }
                        }
                    }
                } catch (e: CancellationException) {
                    break
                } catch (e: Exception) {
                    _events.emit(WsEvent.Disconnected)
                } finally {
                    session = null
                }

                delay(retryDelay)
                retryDelay = (retryDelay * 2).coerceAtMost(maxDelay)
            }
        }
    }

    fun disconnect() {
        reconnectJob?.cancel()
        reconnectJob = null
        scope.launch {
            session?.close()
            session = null
            _events.emit(WsEvent.Disconnected)
        }
    }

    private suspend fun processMessage(text: String) {
        try {
            val data = json.decodeFromString<JsonObject>(text)
            when (val type = data["type"]?.jsonPrimitive?.content) {
                "miya_emotion" -> {
                    val payload = data["data"]?.jsonObject
                    val dominant = payload?.get("dominant")?.jsonPrimitive?.content ?: "neutral"
                    val intensity = payload?.get("intensity")?.jsonPrimitive?.intOrNull ?: 50
                    _events.emit(WsEvent.EmotionChanged(dominant, intensity))
                }
                "memory_stored" -> {
                    val payload = data["data"]?.jsonObject
                    val memId = payload?.get("memory_id")?.jsonPrimitive?.content ?: ""
                    val preview = payload?.get("content_preview")?.jsonPrimitive?.content ?: ""
                    _events.emit(WsEvent.MemoryStored(memId, preview))
                }
                "platform_message" -> {
                    val payload = data["data"]?.jsonObject
                    val platform = payload?.get("platform")?.jsonPrimitive?.content ?: "unknown"
                    val userId = payload?.get("user_id")?.jsonPrimitive?.content ?: ""
                    val content = payload?.get("content")?.jsonPrimitive?.content ?: ""
                    _events.emit(WsEvent.PlatformMessage(platform, userId, content))
                }
                "platform_status" -> {
                    val payload = data["data"]?.jsonObject
                    val platform = payload?.get("platform")?.jsonPrimitive?.content ?: "unknown"
                    val status = payload?.get("status")?.jsonPrimitive?.content ?: "offline"
                    _events.emit(WsEvent.PlatformStatusChanged(platform, status))
                }
                "notification" -> {
                    val payload = data["data"]?.jsonObject
                    val title = payload?.get("title")?.jsonPrimitive?.content ?: "弥娅"
                    val body = payload?.get("body")?.jsonPrimitive?.content ?: ""
                    _events.emit(WsEvent.Notification(title, body))
                }
            }
        } catch (_: Exception) {
            // skip malformed messages
        }
    }
}
