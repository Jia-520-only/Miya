package ai.miya.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class Persona(
    val id: String,
    val name: String,
    val active: Boolean = false,
    @SerialName("display_name") val displayName: String? = null,
    val description: String? = null,
)

@Serializable
data class PersonaListResponse(
    val personalities: List<Persona> = emptyList(),
)

@Serializable
data class PersonaCurrentResponse(
    val id: String? = null,
    val name: String? = null,
    val active: Boolean? = null,
    @SerialName("display_name") val displayName: String? = null,
    val current: String? = null,
)

@Serializable
data class SwitchPersonaRequest(
    @SerialName("personality_id") val personalityId: String,
)

@Serializable
data class SwitchPersonaResponse(
    val success: Boolean = false,
    val current: String? = null,
    @SerialName("display_name") val displayName: String? = null,
)
