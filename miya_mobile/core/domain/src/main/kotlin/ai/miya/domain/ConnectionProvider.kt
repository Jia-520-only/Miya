package ai.miya.domain

import kotlinx.coroutines.flow.StateFlow

enum class ConnectionMode { LAN, REMOTE }

enum class ConnectionStatus { DISCONNECTED, CONNECTING, CONNECTED, ERROR }

data class ConnectionState(
    val mode: ConnectionMode = ConnectionMode.LAN,
    val status: ConnectionStatus = ConnectionStatus.DISCONNECTED,
    val baseUrl: String = "http://localhost:8000",
    val wsUrl: String = "ws://localhost:9800",
    val error: String? = null,
)

interface ConnectionProvider {
    val state: StateFlow<ConnectionState>
    val isConnected: Boolean
    fun connectLan(host: String = "localhost", port: Int = 8000)
    fun connectRemote(host: String, port: Int = 8000)
    fun disconnect()
}
