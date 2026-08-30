package ai.miya.network

import ai.miya.domain.PersonaProvider
import ai.miya.model.Persona
import ai.miya.model.PersonaCurrentResponse
import ai.miya.model.SwitchPersonaResponse

class PersonaProviderImpl(
    private val apiClient: MiyaApiClient,
) : PersonaProvider {

    override suspend fun getList(): List<Persona> = apiClient.getPersonaList()

    override suspend fun getCurrent(): PersonaCurrentResponse = apiClient.getCurrentPersona()

    override suspend fun switch(personalityId: String): SwitchPersonaResponse {
        return apiClient.switchPersona(personalityId)
    }
}
