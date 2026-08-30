package ai.miya.file

import ai.miya.database.FileRecordEntity
import ai.miya.database.MiyaDatabase
import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class FileRepository(private val context: Context) {

    private val db by lazy { MiyaDatabase.getInstance(context) }

    suspend fun saveFileRecord(record: FileRecordEntity) = withContext(Dispatchers.IO) {
        db.fileRecordDao().insert(record)
    }

    suspend fun getFileByMessageId(messageId: String): FileRecordEntity? = withContext(Dispatchers.IO) {
        db.fileRecordDao().getByMessageId(messageId)
    }

    suspend fun getDownloadedFilesBySession(sessionId: String): List<FileRecordEntity> = withContext(Dispatchers.IO) {
        db.fileRecordDao().getBySession(sessionId)
    }

    suspend fun deleteFileRecord(messageId: String) = withContext(Dispatchers.IO) {
        db.fileRecordDao().deleteByMessageId(messageId)
    }
}
