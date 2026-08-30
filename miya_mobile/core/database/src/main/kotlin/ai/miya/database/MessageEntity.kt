package ai.miya.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "messages")
data class MessageEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "session_id") val sessionId: String,
    val content: String,
    val role: String,
    val timestamp: Long,
    @ColumnInfo(name = "image_base64") val imageBase64: String? = null,
    @ColumnInfo(name = "file_local_path") val fileLocalPath: String? = null,
    @ColumnInfo(name = "file_name") val fileName: String? = null,
    @ColumnInfo(name = "file_size") val fileSize: Long? = null,
    @ColumnInfo(name = "file_mime_type") val fileMimeType: String? = null,
    @ColumnInfo(name = "thumbnail_path") val thumbnailPath: String? = null,
)
