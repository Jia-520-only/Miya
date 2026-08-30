package ai.miya.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "file_records")
data class FileRecordEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "message_id") val messageId: String,
    @ColumnInfo(name = "session_id") val sessionId: String,
    @ColumnInfo(name = "local_path") val localPath: String,
    @ColumnInfo(name = "file_name") val fileName: String,
    @ColumnInfo(name = "file_size") val fileSize: Long,
    @ColumnInfo(name = "mime_type") val mimeType: String,
    @ColumnInfo(name = "remote_url") val remoteUrl: String? = null,
    @ColumnInfo(name = "download_timestamp") val downloadTimestamp: Long = System.currentTimeMillis(),
)
