package ai.miya.file

enum class FileCategory(val dirName: String) {
    IMAGES("images"),
    DOCUMENTS("documents"),
    AUDIO("audio"),
    WALLPAPER("wallpaper"),
    THUMBNAILS("thumbnails"),
    DOWNLOADS("downloads");

    companion object {
        fun fromMime(mimeType: String?): FileCategory {
            if (mimeType == null) return DOCUMENTS
            return when {
                mimeType.startsWith("image/") -> IMAGES
                mimeType.startsWith("audio/") || mimeType.startsWith("video/") -> AUDIO
                else -> DOCUMENTS
            }
        }

        fun fromExtension(fileName: String): FileCategory {
            val ext = fileName.substringAfterLast('.', "").lowercase()
            return when (ext) {
                "jpg", "jpeg", "png", "gif", "webp", "bmp" -> IMAGES
                "mp3", "wav", "ogg", "m4a", "aac", "mp4", "webm" -> AUDIO
                else -> DOCUMENTS
            }
        }
    }
}
