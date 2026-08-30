package ai.miya.network

import ai.miya.domain.SessionProvider
import ai.miya.model.SessionInfo
import ai.miya.model.SystemStatus

class SessionProviderImpl(
    private val apiClient: MiyaApiClient,
) : SessionProvider {

    override suspend fun getStatus(): SystemStatus = apiClient.systemStatus()

    override suspend fun getSessions(): List<SessionInfo> = apiClient.listSessions()

    override suspend fun newSession(): String = apiClient.newSession().id

    override suspend fun deleteSession(sessionId: String) {
        apiClient.deleteSession(sessionId)
    }

    override suspend fun renameSession(sessionId: String, name: String) {
        apiClient.updateSessionName(sessionId, name)
    }
}
