package ai.miya.domain

import kotlinx.coroutines.flow.Flow

interface PreferenceProvider {
    val themeColorArgb: Flow<Long?>
    val backgroundFilePath: Flow<String?>
    val serverHost: Flow<String?>
    val serverPort: Flow<String?>

    suspend fun setThemeColorArgb(argb: Long)
    suspend fun setBackgroundFilePath(path: String?)
    suspend fun setServerHost(host: String)
    suspend fun setServerPort(port: String)
}
