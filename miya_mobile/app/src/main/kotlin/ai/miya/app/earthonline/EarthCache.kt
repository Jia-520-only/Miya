package ai.miya.app.earthonline

import ai.miya.model.EarthCharacter
import ai.miya.model.EarthItem
import ai.miya.model.EarthPlayer
import ai.miya.model.EarthQuest
import ai.miya.model.EarthStory
import android.content.Context
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import java.io.File

/**
 * 地球online 本地缓存 — 像 QQ 一样先展示本地数据，再拉取服务器更新。
 *
 * 缓存目录: filesDir/earthonline/
 * - player.json / items.json / quests.json / characters.json / stories.json
 * - meta.json (lastSync 时间戳)
 */
class EarthCache(context: Context) {

    private val dir = File(context.filesDir, "earthonline").apply { mkdirs() }
    private val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        isLenient = true
    }

    private inline fun <reified T> read(name: String): T? {
        return try {
            val f = File(dir, name)
            if (!f.exists()) null else json.decodeFromString<T>(f.readText())
        } catch (_: Exception) {
            null
        }
    }

    private fun write(name: String, content: String) {
        try {
            File(dir, name).writeText(content)
        } catch (_: Exception) {
        }
    }

    fun hasCache(): Boolean = File(dir, "items.json").exists()

    fun saveAll(
        player: EarthPlayer,
        items: List<EarthItem>,
        quests: List<EarthQuest>,
        characters: List<EarthCharacter>,
        stories: List<EarthStory>,
    ) {
        write("player.json", json.encodeToString(player))
        write("items.json", json.encodeToString(items))
        write("quests.json", json.encodeToString(quests))
        write("characters.json", json.encodeToString(characters))
        write("stories.json", json.encodeToString(stories))
        write("meta.json", "{\"lastSync\":${System.currentTimeMillis()}}")
    }

    fun loadPlayer(): EarthPlayer? = read("player.json")
    fun loadItems(): List<EarthItem> = read("items.json") ?: emptyList()
    fun loadQuests(): List<EarthQuest> = read("quests.json") ?: emptyList()
    fun loadCharacters(): List<EarthCharacter> = read("characters.json") ?: emptyList()
    fun loadStories(): List<EarthStory> = read("stories.json") ?: emptyList()

    fun lastSync(): Long {
        return try {
            val f = File(dir, "meta.json")
            if (!f.exists()) return 0L
            val m = json.parseToJsonElement(f.readText())
            (m as? JsonObject)
                ?.get("lastSync")
                ?.let { (it as? JsonPrimitive)?.contentOrNull?.toLongOrNull() }
                ?: 0L
        } catch (_: Exception) {
            0L
        }
    }
}
