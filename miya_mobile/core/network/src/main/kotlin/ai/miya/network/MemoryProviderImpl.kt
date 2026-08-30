package ai.miya.network

import ai.miya.domain.MemoryProvider
import ai.miya.model.MemoryItem
import ai.miya.model.MemoryStats

class MemoryProviderImpl(
    private val apiClient: MiyaApiClient,
) : MemoryProvider {

    override suspend fun getStats(): MemoryStats = apiClient.getMemoryStats()

    override suspend fun search(query: String, limit: Int): List<MemoryItem> {
        return apiClient.searchMemory(query, limit)
    }

    override suspend fun getList(limit: Int): List<MemoryItem> {
        return apiClient.getMemoryList(limit)
    }
}
