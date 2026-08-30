package ai.miya.network

import ai.miya.domain.PreferenceProvider
import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "miya_settings")

class PreferenceProviderImpl(private val context: Context) : PreferenceProvider {

    private companion object {
        val KEY_THEME_COLOR = longPreferencesKey("theme_color_argb")
        val KEY_BACKGROUND_PATH = stringPreferencesKey("background_file_path")
        val KEY_SERVER_HOST = stringPreferencesKey("server_host")
        val KEY_SERVER_PORT = stringPreferencesKey("server_port")
    }

    override val themeColorArgb: Flow<Long?> = context.dataStore.data.map { it[KEY_THEME_COLOR] }
    override val backgroundFilePath: Flow<String?> = context.dataStore.data.map { it[KEY_BACKGROUND_PATH] }
    override val serverHost: Flow<String?> = context.dataStore.data.map { it[KEY_SERVER_HOST] }
    override val serverPort: Flow<String?> = context.dataStore.data.map { it[KEY_SERVER_PORT] }

    override suspend fun setThemeColorArgb(argb: Long) {
        context.dataStore.edit { it[KEY_THEME_COLOR] = argb }
    }

    override suspend fun setBackgroundFilePath(path: String?) {
        context.dataStore.edit { prefs ->
            if (path != null) prefs[KEY_BACKGROUND_PATH] = path else prefs.remove(KEY_BACKGROUND_PATH)
        }
    }

    override suspend fun setServerHost(host: String) {
        context.dataStore.edit { it[KEY_SERVER_HOST] = host }
    }

    override suspend fun setServerPort(port: String) {
        context.dataStore.edit { it[KEY_SERVER_PORT] = port }
    }
}
