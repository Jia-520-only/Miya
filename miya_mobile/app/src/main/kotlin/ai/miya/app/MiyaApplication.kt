package ai.miya.app

import ai.miya.domain.*
import ai.miya.file.AudioPlayer
import ai.miya.file.FileDownloader
import ai.miya.file.FileManager
import ai.miya.file.FileRepository
import ai.miya.network.*
import ai.miya.uicommon.theme.restoreFromPreferences
import android.app.Application
import coil.ImageLoader
import coil.ImageLoaderFactory
import coil.disk.DiskCache
import coil.memory.MemoryCache
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class MiyaApplication : Application(), ImageLoaderFactory {

    companion object {
        lateinit var instance: MiyaApplication
            private set
    }

    override fun onCreate() {
        super.onCreate()
        instance = this
        ForegroundDetector.init(this)
        registerServices()
        restorePersistedState()
    }

    override fun newImageLoader(): ImageLoader {
        return ImageLoader.Builder(this)
            .memoryCache {
                MemoryCache.Builder(this)
                    .maxSizePercent(0.20)
                    .build()
            }
            .diskCache {
                DiskCache.Builder()
                    .directory(cacheDir.resolve("coil_cache"))
                    .maxSizeBytes(250L * 1024 * 1024)
                    .build()
            }
            .build()
    }

    private fun registerServices() {
        val connectionManager = MiyaConnectionManager()
        val apiClient = MiyaApiClient()
        val webSocket = MiyaWebSocket()
        val preferenceProvider = PreferenceProviderImpl(this)
        val fileManager = FileManager(this)
        val fileDownloader = FileDownloader(this, apiClient, fileManager)
        val fileRepository = FileRepository(this)
        val audioPlayer = AudioPlayer(this)

        ServiceRegistry.registerSingleton(MiyaApiClient::class.java) {
            apiClient
        }

        ServiceRegistry.registerSingleton(MiyaWebSocket::class.java) {
            webSocket
        }

        ServiceRegistry.registerSingleton(WebSocketProvider::class.java) {
            WebSocketProviderImpl(webSocket)
        }

        ServiceRegistry.registerSingleton(ConnectionProvider::class.java) {
            ConnectionProviderImpl(connectionManager, apiClient, webSocket)
        }

        ServiceRegistry.registerSingleton(ChatProvider::class.java) {
            ChatProviderImpl(apiClient)
        }

        ServiceRegistry.registerSingleton(SessionProvider::class.java) {
            SessionProviderImpl(apiClient)
        }

        ServiceRegistry.registerSingleton(MemoryProvider::class.java) {
            MemoryProviderImpl(apiClient)
        }

        ServiceRegistry.registerSingleton(PersonaProvider::class.java) {
            PersonaProviderImpl(apiClient)
        }

        ServiceRegistry.registerSingleton(PreferenceProvider::class.java) {
            preferenceProvider
        }

        ServiceRegistry.registerSingleton(FileManager::class.java) {
            fileManager
        }

        ServiceRegistry.registerSingleton(FileDownloader::class.java) {
            fileDownloader
        }

        ServiceRegistry.registerSingleton(FileRepository::class.java) {
            fileRepository
        }

        ServiceRegistry.registerSingleton(AudioPlayer::class.java) {
            audioPlayer
        }

        ServiceRegistry.markInitialized()
    }

    private fun restorePersistedState() {
        restoreFromPreferences(this)
        autoConnect()
    }

    private fun autoConnect() {
        val connectionManager = ServiceRegistry.get(MiyaConnectionManager::class.java) ?: return
        val apiClient = ServiceRegistry.get(MiyaApiClient::class.java) ?: return
        val webSocket = ServiceRegistry.get(MiyaWebSocket::class.java) ?: return
        val pref = ServiceRegistry.get(PreferenceProvider::class.java) ?: return

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val host = pref.serverHost.first() ?: return@launch
                val port = pref.serverPort.first()?.toIntOrNull() ?: 8000
                if (host.isEmpty()) return@launch

                apiClient.updateBaseUrl("http://$host:$port")
                val healthy = apiClient.health()
                if (healthy) {
                    connectionManager.connectLan(host, port)
                    connectionManager.markConnected()
                    webSocket.updateUrl("ws://$host:9800/api/v1/ws")
                    webSocket.connect()
                }
            } catch (_: Exception) {
                connectionManager.markDisconnected()
            }
        }
    }
}
