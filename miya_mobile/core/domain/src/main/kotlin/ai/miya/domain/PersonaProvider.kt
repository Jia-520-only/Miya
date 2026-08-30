package ai.miya.domain

import ai.miya.model.Persona
import ai.miya.model.PersonaCurrentResponse
import ai.miya.model.SwitchPersonaResponse

interface PersonaProvider {
    suspend fun getList(): List<Persona>
    suspend fun getCurrent(): PersonaCurrentResponse
    suspend fun switch(personalityId: String): SwitchPersonaResponse
}
