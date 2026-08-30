package ai.miya.feature.chat

import ai.miya.database.FileRecordEntity
import ai.miya.database.MessageEntity
import ai.miya.database.MiyaDatabase
import ai.miya.domain.AppEvent
import ai.miya.domain.AppEventBus
import ai.miya.domain.ChatProvider
import ai.miya.domain.ServiceRegistry
import ai.miya.domain.SessionProvider
import ai.miya.file.FileCategory
import ai.miya.file.FileDownloader
import ai.miya.file.FileManager
import ai.miya.file.FileRepository
import ai.miya.model.*
import ai.miya.network.MiyaApiClient
import android.app.Application
import android.content.Context
import android.graphics.BitmapFactory
import android.net.Uri
import android.provider.OpenableColumns
import android.util.Base64
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.io.ByteArrayOutputStream
import java.io.File

data class ChatUiState(
    val messages: List<ChatMessage> = emptyList(),
    val inputText: String = "",
    val isStreaming: Boolean = false,
    val streamedText: String = "",
    val sessions: List<SessionInfo> = emptyList(),
    val currentSessionId: String = "default",
    val error: String? = null,
    val showSessionPicker: Boolean = false,
    val showAttachmentPicker: Boolean = false,
    val showStickerPicker: Boolean = false,
    val imageCaption: String = "",
    val pendingImageUri: Uri? = null,
    val pendingFileUri: Uri? = null,
    val fileCaption: String = "",
    val quotedMessage: ChatMessage? = null,
    val poked: Boolean = false,
    val downloadTasks: List<FileDownloader.DownloadTask> = emptyList(),
)

data class ChatMessage(
    val id: String,
    val content: String,
    val role: String,
    val timestamp: Long,
    val imageBase64: String? = null,
    val imageUrl: String? = null,
    val fileLocalPath: String? = null,
    val thumbnailPath: String? = null,
    val fileName: String? = null,
    val fileSize: Long? = null,
    val fileMimeType: String? = null,
    val pendingFileUrl: String? = null,
    val quotedId: String? = null,
    val quotedContent: String? = null,
) {
    val isUser: Boolean get() = role == "user"
    val hasImage: Boolean get() = imageBase64 != null || imageUrl != null ||
        (fileLocalPath != null && fileMimeType?.startsWith("image/") == true)
    val imageSrc: String? get() = imageBase64 ?: imageUrl ?: fileLocalPath
    val hasFile: Boolean get() = fileName != null && imageBase64 == null && imageUrl == null
    val hasQuote: Boolean get() = quotedContent != null
    fun contentPreview(maxLen: Int = 50): String =
        if (content.length <= maxLen) content else content.take(maxLen) + "\u2026"
}

val COMMON_STICKERS = listOf(
    "\uD83D\uDE00" to "笑脸", "\uD83D\uDE02" to "笑哭", "\uD83D\uDE0D" to "喜欢", "\uD83D\uDE2D" to "大哭",
    "\uD83D\uDE21" to "生气", "\uD83D\uDE31" to "震惊", "\uD83D\uDE34" to "睡觉", "\uD83E\uDD14" to "思考",
    "\uD83D\uDC4D" to "赞", "\u2764\uFE0F" to "爱心", "\uD83C\uDF89" to "庆祝", "\uD83D\uDD25" to "火",
    "\uD83E\uDD7A" to "委屈", "\uD83D\uDE4F" to "祈祷", "\uD83D\uDCAA" to "加油", "\u2728" to "闪亮",
    "\uD83D\uDC31" to "猫猫", "\uD83D\uDC36" to "狗狗", "\uD83C\uDF38" to "花花", "\u2B50" to "星星",
    "\uD83C\uDF70" to "蛋糕", "\u2615" to "咖啡", "\uD83D\uDCF1" to "手机", "\uD83D\uDCBB" to "电脑",
)

internal fun formatFileSize(size: Long): String = when {
    size < 1024 -> "${size}B"
    size < 1024 * 1024 -> "${size / 1024}KB"
    size < 1024 * 1024 * 1024 -> "${"%.1f".format(size.toFloat() / (1024 * 1024))}MB"
    else -> "${"%.2f".format(size.toFloat() / (1024 * 1024 * 1024))}GB"
}

class ChatViewModel(application: Application) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    private val db by lazy { MiyaDatabase.getInstance(getApplication()) }
    private val messageDao by lazy { db.messageDao() }
    private val fileManager by lazy { FileManager(getApplication()) }
    private val fileDownloader by lazy { ServiceRegistry.getOrThrow(FileDownloader::class.java) }
    private val fileRepository by lazy { FileRepository(getApplication()) }

    init {
        observeDownloadTasks()
        observeDownloadEvents()
        subscribeToProactiveMessages()
    }

    fun init() { loadSessions() }

    private fun observeDownloadTasks() {
        viewModelScope.launch {
            fileDownloader.tasks.collect { tasks ->
                _state.update { it.copy(downloadTasks = tasks) }
            }
        }
    }

    private fun observeDownloadEvents() {
        viewModelScope.launch {
            fileDownloader.downloadEvents.collect { event ->
                when (event) {
                    is FileDownloader.DownloadEvent.Completed -> {
                        if (event.messageId != null) {
                            _state.update { state ->
                                val updatedMessages = state.messages.map { msg ->
                                    if (msg.id == event.messageId) {
                                        msg.copy(fileLocalPath = event.localPath, fileSize = event.fileSize)
                                    } else msg
                                }
                                state.copy(messages = updatedMessages)
                            }
                        }
                    }
                    else -> {}
                }
            }
        }
    }

    private fun subscribeToProactiveMessages() {
        viewModelScope.launch {
            AppEventBus.events.collect { event ->
                if (event is AppEvent.ProactiveMessage) {
                    val aiMsg = ChatMessage(
                        "p_${event.timestamp}", event.text, "assistant", event.timestamp
                    )
                    _state.update { it.copy(messages = it.messages + aiMsg) }
                    saveToDb(aiMsg)
                }
            }
        }
    }

    fun loadSessions() {
        viewModelScope.launch {
            try { _state.update { it.copy(sessions = ServiceRegistry.getOrThrow(SessionProvider::class.java).getSessions()) } } catch (_: Exception) {}
        }
    }

    fun selectSession(id: String) {
        _state.update { it.copy(currentSessionId = id, messages = emptyList(), showSessionPicker = false, quotedMessage = null) }
        loadMessages(id)
    }

    private fun loadMessages(sessionId: String) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                var entities = messageDao.getMessages(sessionId)

                if (entities.isEmpty()) {
                    val api = ServiceRegistry.get(MiyaApiClient::class.java)
                    if (api != null) {
                        val historyItems = api.getSessionMessages(sessionId)
                        if (historyItems.isNotEmpty()) {
                            val now = System.currentTimeMillis()
                            historyItems.forEachIndexed { index, item ->
                                val msgEntity = MessageEntity(
                                    id = "s_${sessionId}_${index}_${now}",
                                    sessionId = sessionId,
                                    content = item.content,
                                    role = item.role,
                                    timestamp = now + index,
                                )
                                try { messageDao.insert(msgEntity) } catch (_: Exception) {}
                            }
                            entities = messageDao.getMessages(sessionId)
                        }
                    }
                }

                val messages = entities.map { e ->
                    ChatMessage(
                        e.id, e.content, e.role, e.timestamp,
                        imageBase64 = e.imageBase64,
                        fileLocalPath = e.fileLocalPath,
                        thumbnailPath = e.thumbnailPath,
                        fileName = e.fileName,
                        fileSize = e.fileSize,
                        fileMimeType = e.fileMimeType,
                    )
                }
                _state.update { it.copy(messages = messages) }
            } catch (_: Exception) {}
        }
    }

    fun newSession() {
        viewModelScope.launch {
            try {
                val id = ServiceRegistry.getOrThrow(SessionProvider::class.java).newSession()
                _state.update { it.copy(currentSessionId = id, messages = emptyList(), streamedText = "", showSessionPicker = false, quotedMessage = null) }
                loadSessions()
            } catch (e: Exception) { _state.update { it.copy(error = "创建失败: ${e.message}") } }
        }
    }

    fun deleteSession(id: String) {
        viewModelScope.launch {
            try {
                ServiceRegistry.getOrThrow(SessionProvider::class.java).deleteSession(id)
                messageDao.deleteBySession(id)
                loadSessions()
                if (_state.value.currentSessionId == id) _state.update { it.copy(currentSessionId = "default", messages = emptyList()) }
            } catch (_: Exception) {}
        }
    }

    fun deleteMessage(id: String) {
        _state.update { it.copy(messages = it.messages.filter { m -> m.id != id }) }
        viewModelScope.launch { try { messageDao.deleteById(id) } catch (_: Exception) {} }
    }

    fun onInputChange(text: String) { _state.update { it.copy(inputText = text, error = null) } }
    fun toggleSessionPicker() { _state.update { it.copy(showSessionPicker = !it.showSessionPicker) } }
    fun toggleAttachmentPicker() { _state.update { it.copy(showAttachmentPicker = !it.showAttachmentPicker, showStickerPicker = false) } }
    fun toggleStickerPicker() { _state.update { it.copy(showStickerPicker = !it.showStickerPicker, showAttachmentPicker = false) } }
    fun clearError() { _state.update { it.copy(error = null) } }

    fun setQuotedMessage(msg: ChatMessage?) { _state.update { it.copy(quotedMessage = msg) } }
    fun clearQuote() { _state.update { it.copy(quotedMessage = null) } }

    fun setPendingImage(uri: Uri) { _state.update { it.copy(pendingImageUri = uri, imageCaption = "", showAttachmentPicker = false) } }
    fun onImageCaptionChange(text: String) { _state.update { it.copy(imageCaption = text) } }
    fun cancelImageCaption() { _state.update { it.copy(pendingImageUri = null, imageCaption = "") } }
    fun confirmImageSend(context: Context) {
        val uri = _state.value.pendingImageUri ?: return
        sendWithImage(context, uri, _state.value.imageCaption.ifEmpty { null })
    }

    fun setPendingFile(uri: Uri) { _state.update { it.copy(pendingFileUri = uri, fileCaption = _state.value.inputText, showAttachmentPicker = false) } }
    fun onFileCaptionChange(text: String) { _state.update { it.copy(fileCaption = text) } }
    fun cancelFileCaption() { _state.update { it.copy(pendingFileUri = null, fileCaption = "") } }
    fun confirmFileSend(context: Context) {
        val uri = _state.value.pendingFileUri ?: return
        sendWithFile(context, uri, _state.value.fileCaption.ifEmpty { null })
    }

    fun sendPoke() {
        if (_state.value.isStreaming) return
        val msg = ChatMessage("u_${System.currentTimeMillis()}", "拍了拍弥娅", "user", System.currentTimeMillis())
        _state.update { it.copy(messages = it.messages + msg, poked = true) }
        saveToDb(msg)
        doStream(ChatRequest(message = "/poke", sessionId = _state.value.currentSessionId, platform = "mobile"))
    }

    fun sendSticker(emoji: String) {
        if (_state.value.isStreaming) return
        val msg = ChatMessage("u_${System.currentTimeMillis()}", emoji, "user", System.currentTimeMillis())
        _state.update { it.copy(messages = it.messages + msg, inputText = "", showStickerPicker = false) }
        saveToDb(msg)
        doStream(ChatRequest(message = emoji, sessionId = _state.value.currentSessionId, platform = "mobile"))
    }

    fun sendDrawCommand() {
        val text = _state.value.inputText.trim()
        if (text.isEmpty() || _state.value.isStreaming) return
        val drawText = if (text.startsWith("/draw")) text else "/draw $text"
        val msg = ChatMessage("u_${System.currentTimeMillis()}", text, "user", System.currentTimeMillis())
        _state.update { it.copy(messages = it.messages + msg, inputText = "", isStreaming = true, streamedText = "", error = null) }
        saveToDb(msg)
        doStream(ChatRequest(message = drawText, sessionId = _state.value.currentSessionId, platform = "mobile"))
    }

    fun sendMessage() {
        val text = _state.value.inputText.trim()
        if (text.isEmpty() || _state.value.isStreaming) return
        if (text.startsWith("/draw") || text.startsWith("/画")) { sendDrawCommand(); return }
        val quoted = _state.value.quotedMessage
        val quotedText = if (quoted != null) "「引用: ${quoted.contentPreview(80)}」\n" else ""
        val fullText = quotedText + text
        val msg = ChatMessage("u_${System.currentTimeMillis()}", text, "user", System.currentTimeMillis(),
            quotedId = quoted?.id, quotedContent = quoted?.contentPreview(80))
        _state.update { it.copy(messages = it.messages + msg, inputText = "", isStreaming = true, streamedText = "", error = null, quotedMessage = null) }
        saveToDb(msg)
        doStream(ChatRequest(message = fullText, sessionId = _state.value.currentSessionId, platform = "mobile"))
    }

    fun sendWithImage(context: Context, uri: Uri, caption: String? = null) {
        if (_state.value.isStreaming) return
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val rawBytes = readBytes(context, uri)
                val mime = context.contentResolver.getType(uri) ?: "image/jpeg"
                val name = getFileName(context, uri) ?: "图片"
                val originalSize = rawBytes.size.toLong()

                val compressed = compressImage(rawBytes)
                val localFile = fileManager.saveBytes(compressed, FileCategory.IMAGES, _state.value.currentSessionId, "img_${System.currentTimeMillis()}.jpg")

                val base64 = "data:image/jpeg;base64,${Base64.encodeToString(compressed, Base64.NO_WRAP)}"
                val text = caption ?: _state.value.inputText.ifEmpty { "请查看图片" }
                val msg = ChatMessage(
                    "u_${System.currentTimeMillis()}", text, "user", System.currentTimeMillis(),
                    imageBase64 = base64,
                    fileLocalPath = localFile.absolutePath,
                    thumbnailPath = null,
                    fileName = name,
                    fileSize = originalSize,
                    fileMimeType = mime,
                )
                _state.update { it.copy(
                    messages = it.messages + msg, inputText = "", isStreaming = true, streamedText = "",
                    showAttachmentPicker = false, pendingImageUri = null, imageCaption = "",
                ) }
                saveToDb(msg)
                doStream(ChatRequest(message = text, sessionId = _state.value.currentSessionId, platform = "mobile", imageData = base64))
            } catch (e: Exception) { _state.update { it.copy(error = "图片发送失败: ${e.message}") } }
        }
    }

    private fun compressImage(bytes: ByteArray): ByteArray {
        return try {
            val opts = BitmapFactory.Options()
            opts.inJustDecodeBounds = true
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opts)
            opts.inJustDecodeBounds = false
            opts.inSampleSize = maxOf(1, maxOf(opts.outWidth, opts.outHeight) / 1024)
            val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opts) ?: return bytes
            val bos = ByteArrayOutputStream()
            bmp.compress(android.graphics.Bitmap.CompressFormat.JPEG, 70, bos)
            bmp.recycle()
            bos.toByteArray()
        } catch (_: Exception) { bytes }
    }

    fun sendWithFile(context: Context, uri: Uri, caption: String? = null) {
        if (_state.value.isStreaming) return
        val text = caption ?: _state.value.inputText.ifEmpty { "请查看文件: ${getFileName(context, uri) ?: "文件"}" }
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val name = getFileName(context, uri) ?: "文件"
                val mime = context.contentResolver.getType(uri) ?: "application/octet-stream"
                val size = getFileSize(context, uri)

                val localFile = fileManager.copyFromUri(uri, FileCategory.DOCUMENTS, _state.value.currentSessionId, name)

                val isTextFile = mime.startsWith("text/") ||
                    mime in listOf("application/json", "application/xml", "application/javascript", "application/x-yaml")
                val fileContent: String
                if (isTextFile) {
                    val bytes = readBytes(context, uri)
                    fileContent = "\n\n--- $name ---\n${String(bytes, Charsets.UTF_8).take(4000)}"
                } else {
                    val api = ServiceRegistry.get(MiyaApiClient::class.java)
                    val uploadResult = if (api != null) {
                        val uploadBytes = readBytes(context, uri)
                        api.uploadFile(name, uploadBytes, mime)
                    } else mapOf("success" to "false", "preview" to "上传失败")
                    val serverPath = uploadResult["path"] ?: name
                    fileContent = "\n[已上传: $name → $serverPath]\n[文件信息: $mime, ${formatFileSize(size ?: 0L)}]"
                }

                val fullText = "$text$fileContent"
                val msg = ChatMessage(
                    "u_${System.currentTimeMillis()}", text, "user", System.currentTimeMillis(),
                    fileLocalPath = localFile?.absolutePath,
                    fileName = name,
                    fileSize = size,
                    fileMimeType = mime,
                )
                _state.update { it.copy(
                    messages = it.messages + msg, inputText = "", isStreaming = true, streamedText = "",
                    showAttachmentPicker = false, pendingFileUri = null, fileCaption = "",
                ) }
                saveToDb(msg)
                doStream(ChatRequest(message = fullText, sessionId = _state.value.currentSessionId, platform = "mobile"))
            } catch (e: Exception) { _state.update { it.copy(error = "文件发送失败: ${e.message}") } }
        }
    }

    fun downloadMiyaFile(messageId: String, url: String, fileName: String, mimeType: String) {
        fileDownloader.download(
            url = url,
            fileName = fileName,
            category = FileCategory.fromMime(mimeType),
            sessionId = _state.value.currentSessionId,
            mimeType = mimeType,
        )
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val record = FileRecordEntity(
                    id = "fr_${System.currentTimeMillis()}",
                    messageId = messageId,
                    sessionId = _state.value.currentSessionId,
                    localPath = "",
                    fileName = fileName,
                    fileSize = 0L,
                    mimeType = mimeType,
                    remoteUrl = url,
                )
                fileRepository.saveFileRecord(record)
            } catch (_: Exception) {}
        }
    }

    private fun doStream(request: ChatRequest) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val cp = ServiceRegistry.getOrThrow(ChatProvider::class.java)
                _state.update { it.copy(isStreaming = true, streamedText = "..." ) }

                val chatResponse = cp.sendMessage(request)
                val rawText = chatResponse.response
                val responseText = rawText.stripFileMarkdown().cleanAiContent()
                val imgUrl = extractImageUrl(rawText)
                val sessionId = _state.value.currentSessionId

                val textMsg = ChatMessage(
                    "a_${System.currentTimeMillis()}", responseText, "assistant", System.currentTimeMillis(),
                    imageUrl = imgUrl,
                )
                val newMessages = mutableListOf(textMsg)

                val files = chatResponse.files
                if (files != null) {
                    for (file in files) {
                        if (file.base64 == null) continue
                        try {
                            val bytes = android.util.Base64.decode(file.base64, android.util.Base64.DEFAULT)
                            val name = file.name ?: "file"
                            val mime = file.mimeType ?: "application/octet-stream"
                            val localFile = fileManager.saveBytes(bytes, FileCategory.DOWNLOADS, sessionId, name)

                            val fileMsg = ChatMessage(
                                "f_${System.currentTimeMillis()}", "", "assistant", System.currentTimeMillis(),
                                fileName = name,
                                fileSize = bytes.size.toLong(),
                                fileMimeType = mime,
                                fileLocalPath = localFile.absolutePath,
                            )
                            newMessages.add(fileMsg)
                        } catch (_: Exception) {}
                    }
                }

                withContext(Dispatchers.Main) {
                    _state.update { it.copy(messages = it.messages + newMessages, isStreaming = false, streamedText = "") }
                }
                newMessages.forEach { saveToDb(it) }
            } catch (_: CancellationException) { _state.update { it.copy(isStreaming = false, streamedText = "") } }
            catch (e: Exception) { _state.update { it.copy(isStreaming = false, streamedText = "", error = "发送失败: ${e.message}") } }
        }
    }

    private fun saveToDb(msg: ChatMessage) {
        viewModelScope.launch {
            try {
                messageDao.insert(MessageEntity(
                    id = msg.id, sessionId = _state.value.currentSessionId,
                    content = msg.content, role = msg.role, timestamp = msg.timestamp,
                    imageBase64 = msg.imageBase64,
                    fileLocalPath = msg.fileLocalPath,
                    thumbnailPath = msg.thumbnailPath,
                    fileName = msg.fileName,
                    fileSize = msg.fileSize,
                    fileMimeType = msg.fileMimeType,
                ))
            } catch (_: Exception) {}
        }
    }

    fun stopStreaming() {
        viewModelScope.launch { try { ServiceRegistry.getOrThrow(ChatProvider::class.java).stopChat() } catch (_: Exception) {} }
        _state.update { it.copy(isStreaming = false) }
    }

    private fun getFileName(c: Context, u: Uri) = try { c.contentResolver.query(u, null, null, null, null)?.use { cur -> val i = cur.getColumnIndex(OpenableColumns.DISPLAY_NAME); if (cur.moveToFirst() && i >= 0) cur.getString(i) else null } } catch (_: Exception) { null }
    private fun getFileSize(c: Context, u: Uri) = try { c.contentResolver.query(u, null, null, null, null)?.use { cur -> val i = cur.getColumnIndex(OpenableColumns.SIZE); if (cur.moveToFirst() && i >= 0) cur.getLong(i) else 0L } } catch (_: Exception) { 0L }
    private fun readBytes(c: Context, u: Uri) = c.contentResolver.openInputStream(u)?.use { it.readBytes() } ?: ByteArray(0)

    private fun String.cleanAiContent() = this
        .replace(Regex("<think>.*?</think>", RegexOption.DOT_MATCHES_ALL), "")
        .replace(Regex("\n{3,}"), "\n\n").trim()

    private fun String.stripFileMarkdown() = this
        .replace(Regex("""📄 \[[^\]]+\]\([^\s)]+\)\n*"""), "")
        .replace(Regex("""\n*\[[^\]]+\]\(/api/files/[^\s)]+\)"""), "")
        .trim()

    companion object {
        fun extractImageUrl(text: String): String? {
            val md = Regex("!\\[.*?\\]\\((https?://[^\\s)]+\\.(?:png|jpg|jpeg|gif|webp)(?:\\?[^\\s)]*)?)\\)")
                .find(text)?.groupValues?.getOrNull(1)
            if (md != null) return md
            val direct = Regex("(https?://[^\\s]+\\.(?:png|jpg|jpeg|gif|webp)(?:\\?[^\\s]*)?)")
                .find(text)?.groupValues?.getOrNull(1)
            return direct
        }

        fun extractFileUrl(text: String): String? {
            return Regex("""📄 \[([^\]]+)\]\((https?://[^\s)]+)\)""")
                .find(text)?.groupValues?.getOrNull(2)
                ?: Regex("""\[文件下载\]\((https?://[^\s)]+)\)""")
                .find(text)?.groupValues?.getOrNull(1)
        }

        fun extractFileName(text: String): String? {
            return Regex("""📄 \[([^\]]+)\]\(https?://[^\s)]+\)""")
                .find(text)?.groupValues?.getOrNull(1)
        }
    }
}
