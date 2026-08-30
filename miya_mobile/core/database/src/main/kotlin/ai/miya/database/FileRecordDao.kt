package ai.miya.database

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface FileRecordDao {
    @Query("SELECT * FROM file_records WHERE message_id = :messageId LIMIT 1")
    suspend fun getByMessageId(messageId: String): FileRecordEntity?

    @Query("SELECT * FROM file_records WHERE session_id = :sessionId ORDER BY download_timestamp DESC")
    suspend fun getBySession(sessionId: String): List<FileRecordEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(record: FileRecordEntity)

    @Query("DELETE FROM file_records WHERE message_id = :messageId")
    suspend fun deleteByMessageId(messageId: String)
}
