package ai.miya.file

import android.content.Context
import android.graphics.BitmapFactory
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.util.UUID

class FileManager(private val context: Context) {

    private val miyaRootDir: File
        get() = File(context.filesDir, "miya_files").also { if (!it.exists()) it.mkdirs() }

    fun getRootDir(): File = miyaRootDir
    fun getCategoryDir(category: FileCategory): File =
        File(miyaRootDir, category.dirName).also { if (!it.exists()) it.mkdirs() }

    fun getSessionDir(category: FileCategory, sessionId: String): File =
        File(getCategoryDir(category), sessionId).also { if (!it.exists()) it.mkdirs() }

    fun generateFileName(originalName: String? = null, extension: String = ""): String {
        val uid = UUID.randomUUID().toString().take(8)
        val ext = originalName?.substringAfterLast('.', "") ?: extension
        return if (ext.isNotEmpty()) "${uid}_${System.currentTimeMillis()}.$ext" else "${uid}_${System.currentTimeMillis()}"
    }

    suspend fun copyFromUri(
        uri: Uri,
        category: FileCategory,
        sessionId: String? = null,
        customName: String? = null,
    ): File? = withContext(Dispatchers.IO) {
        try {
            val targetDir = if (sessionId != null) getSessionDir(category, sessionId) else getCategoryDir(category)
            val name = customName ?: generateFileName(getOriginalName(uri))
            val dest = File(targetDir, name)
            context.contentResolver.openInputStream(uri)?.use { input ->
                FileOutputStream(dest).use { output -> input.copyTo(output) }
            }
            dest
        } catch (_: Exception) {
            null
        }
    }

    suspend fun saveBytes(
        bytes: ByteArray,
        category: FileCategory,
        sessionId: String? = null,
        fileName: String,
    ): File = withContext(Dispatchers.IO) {
        val targetDir = if (sessionId != null) getSessionDir(category, sessionId) else getCategoryDir(category)
        val dest = File(targetDir, fileName)
        FileOutputStream(dest).use { it.write(bytes) }
        dest
    }

    fun getFile(category: FileCategory, fileName: String): File? {
        val file = File(getCategoryDir(category), fileName)
        return if (file.exists()) file else null
    }

    fun getFileByPath(filePath: String): File? {
        val file = File(filePath)
        return if (file.exists()) file else null
    }

    fun listFiles(category: FileCategory): List<File> {
        val dir = getCategoryDir(category)
        return dir.listFiles()?.toList() ?: emptyList()
    }

    fun listFiles(category: FileCategory, sessionId: String): List<File> {
        val dir = getSessionDir(category, sessionId)
        return dir.listFiles()?.toList() ?: emptyList()
    }

    fun deleteFile(category: FileCategory, fileName: String): Boolean {
        val file = File(getCategoryDir(category), fileName)
        return if (file.exists()) file.delete() else false
    }

    fun deleteFileByPath(filePath: String): Boolean {
        val file = File(filePath)
        return if (file.exists()) file.delete() else false
    }

    fun clearCache(category: FileCategory, olderThanMs: Long = 7 * 24 * 60 * 60 * 1000L): Int {
        val cutoff = System.currentTimeMillis() - olderThanMs
        var count = 0
        val dir = getCategoryDir(category)
        dir.listFiles()?.forEach { file ->
            if (file.lastModified() < cutoff && file.delete()) count++
        }
        return count
    }

    fun getStorageStats(): StorageStats {
        var totalSize = 0L
        var totalFiles = 0
        miyaRootDir.walkTopDown().forEach { file ->
            if (file.isFile) {
                totalSize += file.length()
                totalFiles++
            }
        }
        return StorageStats(
            totalSize = totalSize,
            totalFiles = totalFiles,
            rootPath = miyaRootDir.absolutePath,
        )
    }

    fun createTempFile(sessionId: String, fileName: String): File {
        val tempDir = File(miyaRootDir, "temp").also { it.mkdirs() }
        return File(tempDir, "${sessionId}_${System.currentTimeMillis()}_$fileName")
    }

    fun moveToCategory(tempFile: File, category: FileCategory, sessionId: String, fileName: String): File {
        val targetDir = getSessionDir(category, sessionId)
        val dest = File(targetDir, fileName)
        if (dest.exists()) dest.delete()
        tempFile.renameTo(dest)
        return dest
    }

    fun thumbnailFileFor(imageFile: File): File {
        val thumbDir = getCategoryDir(FileCategory.THUMBNAILS)
        return File(thumbDir, "thumb_${imageFile.name}")
    }

    suspend fun generateThumbnail(sourceFile: File, maxSize: Int = 256): File? = withContext(Dispatchers.IO) {
        try {
            val opts = BitmapFactory.Options()
            opts.inJustDecodeBounds = true
            BitmapFactory.decodeFile(sourceFile.absolutePath, opts)
            opts.inJustDecodeBounds = false
            opts.inSampleSize = maxOf(1, maxOf(opts.outWidth, opts.outHeight) / maxSize)

            val bmp = BitmapFactory.decodeFile(sourceFile.absolutePath, opts) ?: return@withContext null
            val thumb = thumbnailFileFor(sourceFile)
            FileOutputStream(thumb).use { out ->
                bmp.compress(android.graphics.Bitmap.CompressFormat.JPEG, 80, out)
            }
            bmp.recycle()
            thumb
        } catch (_: Exception) {
            null
        }
    }

    private fun getOriginalName(uri: Uri): String? {
        return try {
            context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                val idx = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
                if (cursor.moveToFirst() && idx >= 0) cursor.getString(idx) else null
            }
        } catch (_: Exception) {
            null
        }
    }
}

data class StorageStats(
    val totalSize: Long,
    val totalFiles: Int,
    val rootPath: String,
) {
    val formattedSize: String get() = when {
        totalSize < 1024 -> "${totalSize}B"
        totalSize < 1024 * 1024 -> "${"%.1f".format(totalSize / 1024.0)}KB"
        totalSize < 1024 * 1024 * 1024 -> "${"%.1f".format(totalSize / (1024.0 * 1024))}MB"
        else -> "${"%.2f".format(totalSize / (1024.0 * 1024 * 1024))}GB"
    }
}
