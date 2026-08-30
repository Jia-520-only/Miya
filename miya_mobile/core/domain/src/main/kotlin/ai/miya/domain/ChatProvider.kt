package ai.miya.domain

import ai.miya.model.ChatRequest
import ai.miya.model.ChatResponse
import kotlinx.coroutines.flow.Flow

interface ChatProvider {
    suspend fun sendMessage(request: ChatRequest): ChatResponse
    fun streamChat(request: ChatRequest): Flow<String>
    suspend fun stopChat(): Boolean
}
