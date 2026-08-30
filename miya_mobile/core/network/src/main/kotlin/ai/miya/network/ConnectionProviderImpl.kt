package ai.miya.network

import ai.miya.domain.ConnectionProvider
import ai.miya.domain.ConnectionState
import ai.miya.domain.ConnectionStatus
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class ConnectionProviderImpl(
    private val connectionManager: MiyaConnectionManager,
    private val apiClient: MiyaApiClient,
    private val webSocket: MiyaWebSocket,
) : ConnectionProvider {

    override val state: StateFlow<ConnectionState> = connectionManager.state
    override val isConnected: Boolean get() = connectionManager.isConnected

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun connectLan(host: String, port: Int) {
        connectionManager.connectLan(host, port)
        val url = "http://$host:$port"
        apiClient.updateBaseUrl(url)
        scope.launch {
            try {
                val healthy = apiClient.health()
                if (healthy) {
                    connectionManager.markConnected()
                    connectWebSocket(host, port)
                } else {
                    connectionManager.markError("服务器无响应")
                }
            } catch (e: Exception) {
                connectionManager.markError("连接失败: ${e.message}")
            }
        }
    }

    override fun connectRemote(host: String, port: Int) {
        connectionManager.connectRemote(host, port)
        val url = "http://$host:$port"
        apiClient.updateBaseUrl(url)
        scope.launch {
            try {
                val healthy = apiClient.health()
                if (healthy) {
                    connectionManager.markConnected()
                    connectWebSocket(host, port)
                } else {
                    connectionManager.markError("服务器无响应")
                }
            } catch (e: Exception) {
                connectionManager.markError("连接失败: ${e.message}")
            }
        }
    }

    override fun disconnect() {
        webSocket.disconnect()
        connectionManager.markDisconnected()
    }

    private fun connectWebSocket(host: String, port: Int) {
        val wsPort = if (port == 8000) 9800 else port
        val url = "ws://$host:$wsPort/api/v1/ws"
        webSocket.updateUrl(url)
        webSocket.connect()
    }

    fun getApiClient(): MiyaApiClient = apiClient
}
