package ai.miya.network

import ai.miya.domain.ChatProvider
import ai.miya.model.ChatRequest
import ai.miya.model.ChatResponse
import kotlinx.coroutines.flow.Flow

class ChatProviderImpl(
    private val apiClient: MiyaApiClient,
) : ChatProvider {

    override suspend fun sendMessage(request: ChatRequest): ChatResponse {
        return apiClient.sendMessage(request)
    }

    override fun streamChat(request: ChatRequest): Flow<String> {
        return apiClient.chatStream(request)
    }

    override suspend fun stopChat(): Boolean {
        return apiClient.stopChat()
    }
}
