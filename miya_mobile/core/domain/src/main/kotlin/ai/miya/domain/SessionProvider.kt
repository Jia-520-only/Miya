package ai.miya.domain

import ai.miya.model.SessionInfo
import ai.miya.model.SystemStatus

interface SessionProvider {
    suspend fun getStatus(): SystemStatus
    suspend fun getSessions(): List<SessionInfo>
    suspend fun newSession(): String
    suspend fun deleteSession(sessionId: String)
    suspend fun renameSession(sessionId: String, name: String)
}
