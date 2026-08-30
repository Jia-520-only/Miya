package ai.miya.network

import ai.miya.domain.ConnectionMode
import ai.miya.domain.ConnectionState
import ai.miya.domain.ConnectionStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

class MiyaConnectionManager {

    private val _state = MutableStateFlow(
        ConnectionState(
            baseUrl = "http://localhost:8000",
            wsUrl = "ws://localhost:9800",
        )
    )
    val state: StateFlow<ConnectionState> = _state

    val isConnected: Boolean
        get() = _state.value.status == ConnectionStatus.CONNECTED

    fun currentBaseUrl(): String = _state.value.baseUrl
    fun currentWsUrl(): String = _state.value.wsUrl

    fun connectLan(host: String = "localhost", port: Int = 8000) {
        _state.value = ConnectionState(
            mode = ConnectionMode.LAN,
            status = ConnectionStatus.CONNECTING,
            baseUrl = "http://$host:$port",
            wsUrl = "ws://$host:9800/api/v1/ws",
        )
    }

    fun connectRemote(host: String, port: Int = 8000) {
        _state.value = ConnectionState(
            mode = ConnectionMode.REMOTE,
            status = ConnectionStatus.CONNECTING,
            baseUrl = "http://$host:$port",
            wsUrl = "ws://$host:9800/api/v1/ws",
        )
    }

    fun markConnected() {
        _state.value = _state.value.copy(status = ConnectionStatus.CONNECTED, error = null)
    }

    fun markDisconnected() {
        _state.value = _state.value.copy(status = ConnectionStatus.DISCONNECTED)
    }

    fun markError(error: String) {
        _state.value = _state.value.copy(status = ConnectionStatus.ERROR, error = error)
    }
}
