package ai.miya.domain

import ai.miya.model.EmotionUpdate
import kotlinx.coroutines.flow.SharedFlow

sealed class WsEvent {
    data class EmotionChanged(val dominant: String, val intensity: Int) : WsEvent()
    data class MemoryStored(val memoryId: String, val preview: String) : WsEvent()
    data class PlatformMessage(val platform: String, val userId: String, val content: String) : WsEvent()
    data class PlatformStatusChanged(val platform: String, val status: String) : WsEvent()
    data class Notification(val title: String, val body: String) : WsEvent()
    data class Error(val message: String) : WsEvent()
    data object Connected : WsEvent()
    data object Disconnected : WsEvent()
}

interface WebSocketProvider {
    val events: SharedFlow<WsEvent>
    val isConnected: Boolean
    fun connect()
    fun disconnect()
}
