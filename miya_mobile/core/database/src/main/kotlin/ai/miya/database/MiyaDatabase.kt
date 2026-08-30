package ai.miya.database

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [MessageEntity::class, FileRecordEntity::class],
    version = 2,
)
abstract class MiyaDatabase : RoomDatabase() {

    abstract fun messageDao(): MessageDao
    abstract fun fileRecordDao(): FileRecordDao

    companion object {
        @Volatile
        private var instance: MiyaDatabase? = null

        fun getInstance(context: Context): MiyaDatabase {
            return instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    MiyaDatabase::class.java,
                    "miya_cache.db"
                )
                    .addMigrations(MIGRATION_1_2)
                    .build()
                    .also { instance = it }
            }
        }
    }
}

private val MIGRATION_1_2 = object : Migration(1, 2) {
    override fun migrate(db: SupportSQLiteDatabase) {
        // Add new columns to messages table
        db.execSQL("ALTER TABLE messages ADD COLUMN file_local_path TEXT")
        db.execSQL("ALTER TABLE messages ADD COLUMN thumbnail_path TEXT")

        // Create file_records table
        db.execSQL("""
            CREATE TABLE IF NOT EXISTS file_records (
                id TEXT NOT NULL PRIMARY KEY,
                message_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                local_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                mime_type TEXT NOT NULL,
                remote_url TEXT,
                download_timestamp INTEGER NOT NULL
            )
        """.trimIndent())
    }
}
