package ai.miya.network

import ai.miya.domain.WsEvent
import ai.miya.domain.WebSocketProvider
import kotlinx.coroutines.flow.SharedFlow

class WebSocketProviderImpl(
    private val webSocket: MiyaWebSocket,
) : WebSocketProvider {

    override val events: SharedFlow<WsEvent> = webSocket.events
    override val isConnected: Boolean get() = webSocket.isConnected

    override fun connect() = webSocket.connect()
    override fun disconnect() = webSocket.disconnect()
}
