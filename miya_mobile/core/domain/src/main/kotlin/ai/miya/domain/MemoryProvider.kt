package ai.miya.domain

import ai.miya.model.MemoryItem
import ai.miya.model.MemoryStats

interface MemoryProvider {
    suspend fun getStats(): MemoryStats
    suspend fun search(query: String, limit: Int = 20): List<MemoryItem>
    suspend fun getList(limit: Int = 50): List<MemoryItem>
}
