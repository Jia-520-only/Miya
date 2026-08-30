package ai.miya.domain

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

object AppEventBus {
    private val _events = MutableSharedFlow<AppEvent>(extraBufferCapacity = 32)
    val events: SharedFlow<AppEvent> = _events.asSharedFlow()

    suspend fun emit(event: AppEvent) {
        _events.emit(event)
    }
}

sealed class AppEvent {
    data class ProactiveMessage(
        val text: String,
        val timestamp: Long = System.currentTimeMillis(),
    ) : AppEvent()
}
