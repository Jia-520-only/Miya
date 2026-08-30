package ai.miya.file

import ai.miya.domain.ServiceRegistry
import ai.miya.network.MiyaApiClient
import android.content.Context
import android.media.MediaPlayer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

class AudioPlayer(private val context: Context) {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var mediaPlayer: MediaPlayer? = null

    private val _playbackState = MutableStateFlow(PlaybackState.IDLE)
    val playbackState: StateFlow<PlaybackState> = _playbackState.asStateFlow()

    private val _currentSource = MutableStateFlow<String?>(null)
    val currentSource: StateFlow<String?> = _currentSource.asStateFlow()

    enum class PlaybackState { IDLE, LOADING, PLAYING, PAUSED, STOPPED, ERROR }

    fun playFile(file: File) {
        stop()
        scope.launch {
            try {
                _playbackState.value = PlaybackState.LOADING
                _currentSource.value = file.absolutePath
                withContext(Dispatchers.Main) {
                    val mp = MediaPlayer().apply {
                        setDataSource(file.absolutePath)
                        setOnPreparedListener {
                            _playbackState.value = PlaybackState.PLAYING
                            start()
                        }
                        setOnCompletionListener {
                            _playbackState.value = PlaybackState.STOPPED
                            release()
                        }
                        setOnErrorListener { _, _, _ ->
                            _playbackState.value = PlaybackState.ERROR
                            release(); true
                        }
                        prepareAsync()
                    }
                    mediaPlayer = mp
                }
            } catch (e: Exception) {
                _playbackState.value = PlaybackState.ERROR
            }
        }
    }

    suspend fun playTts(text: String, engine: String = "edge_tts") {
        stop()
        _playbackState.value = PlaybackState.LOADING
        try {
            val api = ServiceRegistry.get(MiyaApiClient::class.java)
                ?: throw Exception("API 客户端未就绪")
            val bytes = api.textToSpeech(text, engine = engine)
            if (bytes == null || bytes.isEmpty()) {
                _playbackState.value = PlaybackState.ERROR
                return
            }
            val fileManager = FileManager(context)
            val file = fileManager.saveBytes(bytes, FileCategory.AUDIO, fileName = "tts_${System.currentTimeMillis()}.mp3")
            playFile(file)
        } catch (e: Exception) {
            _playbackState.value = PlaybackState.ERROR
        }
    }

    fun pause() {
        mediaPlayer?.let {
            if (it.isPlaying) {
                it.pause()
                _playbackState.value = PlaybackState.PAUSED
            }
        }
    }

    fun resume() {
        mediaPlayer?.let {
            if (!it.isPlaying) {
                it.start()
                _playbackState.value = PlaybackState.PLAYING
            }
        }
    }

    fun stop() {
        mediaPlayer?.apply {
            if (isPlaying) stop()
            release()
        }
        mediaPlayer = null
        _playbackState.value = PlaybackState.STOPPED
        _currentSource.value = null
    }

    fun toggle() {
        when (_playbackState.value) {
            PlaybackState.PLAYING -> pause()
            PlaybackState.PAUSED -> resume()
            else -> {}
        }
    }

    fun destroy() {
        stop()
    }
}
