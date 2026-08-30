package ai.miya.file

import ai.miya.database.FileRecordEntity
import ai.miya.database.MiyaDatabase
import ai.miya.network.MiyaApiClient
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.io.File
import java.io.FileOutputStream
import java.io.BufferedOutputStream
import java.io.BufferedInputStream
import java.net.URL
import java.net.HttpURLConnection

class FileDownloader(
    private val context: Context,
    private val apiClient: MiyaApiClient,
    private val fileManager: FileManager,
) {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val _tasks = MutableStateFlow<List<DownloadTask>>(emptyList())
    val tasks: StateFlow<List<DownloadTask>> = _tasks.asStateFlow()

    private val activeJobs = mutableMapOf<String, Job>()

    private val _downloadEvents = MutableSharedFlow<DownloadEvent>(extraBufferCapacity = 16)
    val downloadEvents: SharedFlow<DownloadEvent> = _downloadEvents.asSharedFlow()

    sealed class DownloadEvent {
        data class Completed(val taskId: String, val messageId: String?, val localPath: String, val fileSize: Long) : DownloadEvent()
        data class Failed(val taskId: String, val error: String) : DownloadEvent()
    }

    data class DownloadTask(
        val id: String = java.util.UUID.randomUUID().toString(),
        val url: String,
        val fileName: String,
        val category: FileCategory,
        val sessionId: String? = null,
        val mimeType: String = "application/octet-stream",
        val messageId: String? = null,
    ) {
        private val _progress = MutableStateFlow(0f)
        val progress: StateFlow<Float> = _progress.asStateFlow()

        private val _status = MutableStateFlow(DownloadStatus.PENDING)
        val status: StateFlow<DownloadStatus> = _status.asStateFlow()

        val _outputFile = MutableStateFlow<File?>(null)
        val outputFile: StateFlow<File?> = _outputFile.asStateFlow()

        internal fun setProgress(p: Float) { _progress.value = p.coerceIn(0f, 1f) }
        internal fun setStatus(s: DownloadStatus) { _status.value = s }
        internal fun setOutputFile(f: File) { _outputFile.value = f }
    }

    enum class DownloadStatus { PENDING, DOWNLOADING, COMPLETED, FAILED }

    fun download(
        url: String,
        fileName: String,
        category: FileCategory = FileCategory.DOWNLOADS,
        sessionId: String? = null,
        mimeType: String = "application/octet-stream",
        messageId: String? = null,
    ): DownloadTask {
        val task = DownloadTask(
            url = url, fileName = fileName, category = category,
            sessionId = sessionId, mimeType = mimeType, messageId = messageId,
        )
        _tasks.update { it + task }

        val job = scope.launch {
            try {
                task.setStatus(DownloadStatus.DOWNLOADING)
                showDownloadNotification(task, "下载中: $fileName")

                val result = downloadStreamToFile(url, fileName, category, sessionId ?: "default")
                if (result == null) {
                    task.setStatus(DownloadStatus.FAILED)
                    showDownloadNotification(task, "下载失败: $fileName")
                    _downloadEvents.emit(DownloadEvent.Failed(task.id, "下载失败"))
                    return@launch
                }

                val (file, fileSize) = result
                task.setProgress(1f)
                task.setOutputFile(file)
                task.setStatus(DownloadStatus.COMPLETED)

                showDownloadNotification(task, "下载完成: $fileName")

                updateFileRecord(task, file.absolutePath, fileSize)
                _downloadEvents.emit(DownloadEvent.Completed(task.id, messageId, file.absolutePath, fileSize))
            } catch (_: CancellationException) {
                task.setStatus(DownloadStatus.FAILED)
            } catch (e: Exception) {
                task.setStatus(DownloadStatus.FAILED)
                showDownloadNotification(task, "下载失败: ${e.message}")
                scope.launch {
                    _downloadEvents.emit(DownloadEvent.Failed(task.id, e.message ?: "未知错误"))
                }
            } finally {
                activeJobs.remove(task.id)
            }
        }
        activeJobs[task.id] = job
        return task
    }

    private suspend fun downloadStreamToFile(
        url: String,
        fileName: String,
        category: FileCategory,
        sessionId: String,
    ): Pair<File, Long>? = withContext(Dispatchers.IO) {
        try {
            val fullUrl = if (url.startsWith("http")) url else "${apiClient.baseUrl}$url"
            val conn = URL(fullUrl).openConnection() as HttpURLConnection
            conn.connectTimeout = 15000
            conn.readTimeout = 60000
            conn.instanceFollowRedirects = true

            val contentLength = conn.contentLengthLong
            val totalSize = if (contentLength > 0) contentLength else -1L

            val tempFile = fileManager.createTempFile(sessionId, fileName)
            conn.inputStream.use { input ->
                BufferedInputStream(input).use { bis ->
                    BufferedOutputStream(FileOutputStream(tempFile)).use { bos ->
                        val buffer = ByteArray(8192)
                        var bytesRead: Int
                        var totalRead = 0L
                        while (bis.read(buffer).also { bytesRead = it } != -1) {
                            bos.write(buffer, 0, bytesRead)
                            totalRead += bytesRead
                            if (totalSize > 0) {
                                val progress = (totalRead.toFloat() / totalSize.toFloat()).coerceIn(0f, 1f)
                                _tasks.value.find { it.id == fileName }?.setProgress(progress)
                            }
                        }
                    }
                }
            }
            conn.disconnect()

            val finalFile = fileManager.moveToCategory(tempFile, category, sessionId, fileName)
            Pair(finalFile, finalFile.length())
        } catch (_: Exception) {
            null
        }
    }

    private suspend fun updateFileRecord(task: DownloadTask, localPath: String, fileSize: Long) {
        try {
            val db = MiyaDatabase.getInstance(context)
            val existing = db.fileRecordDao().getByMessageId(task.messageId ?: task.id)
            if (existing != null) {
                val updated = existing.copy(localPath = localPath, fileSize = fileSize)
                db.fileRecordDao().insert(updated)
            }
        } catch (_: Exception) {}
    }

    fun cancel(taskId: String) {
        activeJobs[taskId]?.cancel()
        activeJobs.remove(taskId)
        _tasks.update { tasks -> tasks.map { if (it.id == taskId) it.apply { setStatus(DownloadStatus.FAILED) } else it } }
    }

    fun clearCompleted() {
        _tasks.update { it.filter { task -> task.status.value != DownloadStatus.COMPLETED } }
    }

    fun destroy() {
        scope.cancel()
    }

    private fun showDownloadNotification(task: DownloadTask, text: String) {
        val channelId = "miya_file_downloads"
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(channelId, "文件下载", NotificationManager.IMPORTANCE_LOW)
            manager.createNotificationChannel(channel)
        }

        val intent = context.packageManager.getLaunchIntentForPackage(context.packageName)
        val pendingIntent = if (intent != null) {
            PendingIntent.getActivity(
                context, task.id.hashCode(), intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
        } else null

        val builder = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("弥娅文件")
            .setContentText(text)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setAutoCancel(task.status.value == DownloadStatus.COMPLETED)

        if (pendingIntent != null) {
            builder.setContentIntent(pendingIntent)
        }

        if (task.status.value == DownloadStatus.DOWNLOADING) {
            builder.setProgress(100, (task.progress.value * 100).toInt(), false)
            builder.setOngoing(true)
        }

        manager.notify(task.id.hashCode(), builder.build())
    }
}
