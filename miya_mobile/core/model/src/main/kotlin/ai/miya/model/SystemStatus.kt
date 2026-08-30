package ai.miya.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class SystemStatus(
    val status: String? = null,
    val version: String? = null,
    val uptime: String? = null,
    val running: Boolean = false,
    val personality: String? = null,
    val name: String? = null,
    val platforms: Int = 0,
    @SerialName("platforms_active") val platformsActive: Int = 0,
    @SerialName("providers_loaded") val providersLoaded: Int? = null,
    val emotion: EmotionState? = null,
    val memory: MemoryStats? = null,
)

@Serializable
data class HealthResponse(
    val status: String = "unknown",
)

data class AppSettings(
    val serverHost: String = "localhost",
    val serverPort: Int = 8000,
    val isDarkTheme: Boolean = true,
    val lastPersonaId: String? = null,
)
