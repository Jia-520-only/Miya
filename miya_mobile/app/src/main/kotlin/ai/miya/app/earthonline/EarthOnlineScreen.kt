package ai.miya.app.earthonline

import ai.miya.domain.ConnectionProvider
import ai.miya.domain.ServiceRegistry
import ai.miya.model.EarthCharacter
import ai.miya.model.EarthItem
import ai.miya.model.EarthPlayer
import ai.miya.model.EarthQuest
import ai.miya.model.EarthQuestTemplate
import ai.miya.model.EarthStory
import ai.miya.model.EarthTemplates
import ai.miya.network.MiyaApiClient
import ai.miya.uicommon.theme.MiyaColors
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import coil.compose.AsyncImage
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private val RarityColors = mapOf(
    "common" to Color(0xFF9E9E9E), "uncommon" to Color(0xFF4CAF50), "rare" to Color(0xFF29B6F6),
    "epic" to Color(0xFFAB47BC), "legendary" to Color(0xFFFFB300),
)
private val RarityLabels = mapOf(
    "common" to "普通", "uncommon" to "稀有", "rare" to "珍贵", "epic" to "史诗", "legendary" to "传说",
)
private val CategoryLabels = mapOf(
    "digital" to "数码", "book" to "书籍", "life" to "生活", "food" to "食品",
    "tool" to "工具", "clothing" to "服饰", "collectible" to "收藏", "other" to "其他",
)
private val QuestTypeLabels = mapOf("main" to "主线", "branch" to "支线", "daily" to "日常", "optional" to "可选")
private val QuestStatusLabels = mapOf(
    "pending" to "待开始", "ongoing" to "进行中", "completed" to "已完成", "failed" to "失败", "cancelled" to "已取消",
)
private val RelationshipLabels = mapOf(
    "family" to "家人", "friend" to "朋友", "colleague" to "同事", "partner" to "恋人", "other" to "其他",
)

private fun formatSyncTime(ts: Long): String {
    if (ts <= 0) return "从未同步"
    val now = System.currentTimeMillis()
    val diff = now - ts
    return when {
        diff < 60_000 -> "刚刚同步"
        diff < 3_600_000 -> "${diff / 60_000} 分钟前同步"
        else -> SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(Date(ts)) + " 同步"
    }
}

@Composable
fun EarthOnlineScreen() {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val cache = remember { EarthCache(context) }
    val cp = remember { ServiceRegistry.get(ConnectionProvider::class.java) }
    val client = remember {
        MiyaApiClient(baseUrl = cp?.state?.value?.baseUrl ?: "http://localhost:8000")
    }

    var tab by remember { mutableIntStateOf(0) }
    var playerMode by remember { mutableStateOf(true) }  // true=前台展示(玩家), false=后台管理
    var player by remember { mutableStateOf<EarthPlayer?>(null) }
    var items by remember { mutableStateOf<List<EarthItem>>(emptyList()) }
    var quests by remember { mutableStateOf<List<EarthQuest>>(emptyList()) }
    var characters by remember { mutableStateOf<List<EarthCharacter>>(emptyList()) }
    var stories by remember { mutableStateOf<List<EarthStory>>(emptyList()) }
    var templates by remember { mutableStateOf(EarthTemplates()) }
    var offline by remember { mutableStateOf(false) }
    var lastSync by remember { mutableLongStateOf(0L) }
    var refreshing by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(true) }
    val snackbarHostState = remember { SnackbarHostState() }

    // 弹窗状态
    var showAddDialog by remember { mutableStateOf(false) }
    var detailItem by remember { mutableStateOf<EarthItem?>(null) }
    var viewItem by remember { mutableStateOf<EarthItem?>(null) }
    var affinityTarget by remember { mutableStateOf<EarthCharacter?>(null) }
    var deleteItem by remember { mutableStateOf<EarthItem?>(null) }
    var deleteCharacter by remember { mutableStateOf<EarthCharacter?>(null) }

    suspend fun refreshFromServer() {
        refreshing = true
        try {
            if (!client.earthPing()) {
                offline = true
                return
            }
            val p = client.earthPlayer()
            val it = client.earthListItems()
            val q = client.earthListQuests()
            val c = client.earthListCharacters()
            val s = client.earthListStory()
            val t = client.earthTemplates()
            player = p; items = it; quests = q; characters = c; stories = s; templates = t
            offline = false
            lastSync = System.currentTimeMillis()
            cache.saveAll(p, it, q, c, s)
        } catch (_: Exception) {
            offline = true
        } finally {
            refreshing = false
            loading = false
        }
    }

    // QQ 式秒开: 先用本地缓存渲染，再后台拉取服务器
    LaunchedEffect(Unit) {
        player = cache.loadPlayer()
        items = cache.loadItems()
        quests = cache.loadQuests()
        characters = cache.loadCharacters()
        stories = cache.loadStories()
        lastSync = cache.lastSync()
        refreshFromServer()
    }

    fun reload() {
        scope.launch { refreshFromServer() }
    }

    // 读取相册照片字节并上传 → 返回 image_path
    suspend fun uploadPickedPhoto(uri: Uri, itemId: Int? = null): String {
        return try {
            val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return ""
            val mime = context.contentResolver.getType(uri) ?: "image/jpeg"
            val name = "earth_${System.currentTimeMillis()}.jpg"
            val resp = client.earthUploadItemImage(name, bytes, mime, itemId)
            if (resp.success) resp.imagePath else ""
        } catch (_: Exception) {
            ""
        }
    }

    Scaffold(
        containerColor = Color.Transparent,
        contentColor = MaterialTheme.colorScheme.onSurface,
        snackbarHost = { SnackbarHost(snackbarHostState) },
        floatingActionButton = {
            if (!playerMode) {
                FloatingActionButton(
                    onClick = { showAddDialog = true },
                    containerColor = MiyaColors.Primary,
                    contentColor = Color.White,
                ) { Icon(Icons.Default.Add, contentDescription = "新增") }
            }
        },
    ) { padding ->
        Column(
            Modifier.padding(padding).fillMaxSize().statusBarsPadding(),
        ) {
            PlayerHeader(player, client)
            SyncBar(offline, lastSync, refreshing, onRefresh = { reload() })
            ModeSwitch(playerMode, onModeChange = { playerMode = it })

            when {
                loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                playerMode -> PlayerModeContent(
                    player = player,
                    client = client,
                    templates = templates,
                    items = items,
                    quests = quests,
                    characters = characters,
                    stories = stories,
                    onAccept = { id ->
                        scope.launch {
                            client.earthAcceptQuest(id)
                            snackbarHostState.showSnackbar("已接取委托，加油！")
                            reload()
                        }
                    },
                    onComplete = { id ->
                        scope.launch {
                            val r = client.earthCompleteQuest(id)
                            snackbarHostState.showSnackbar("任务完成！+${r.reward?.currency ?: 0} 地球币")
                            reload()
                        }
                    },
                    onFail = { id ->
                        scope.launch {
                            client.earthFailQuest(id)
                            snackbarHostState.showSnackbar("任务已放弃，地球币已扣除")
                            reload()
                        }
                    },
                    onCancel = { id ->
                        scope.launch {
                            client.earthCancelQuest(id)
                            snackbarHostState.showSnackbar("任务已取消")
                            reload()
                        }
                    },
                    onCharacterClick = { affinityTarget = it },
                    onItemClick = { viewItem = it },
                )
                else -> {
                    TabRow(
                        selectedTabIndex = tab,
                        containerColor = Color.Transparent,
                        contentColor = MaterialTheme.colorScheme.onSurface,
                    ) {
                        listOf("背包", "任务", "角色", "剧情").forEachIndexed { index, label ->
                            Tab(selected = tab == index, onClick = { tab = index }, text = { Text(label, fontSize = 13.sp) })
                        }
                    }
                    when (tab) {
                        0 -> ItemList(items, client, onClick = { detailItem = it })
                        1 -> QuestList(
                            quests,
                            onComplete = { id ->
                                scope.launch {
                                    val r = client.earthCompleteQuest(id)
                                    snackbarHostState.showSnackbar("任务完成！+${r.reward?.currency ?: 0} 地球币")
                                    reload()
                                }
                            },
                            onFail = { id ->
                                scope.launch {
                                    client.earthFailQuest(id)
                                    snackbarHostState.showSnackbar("任务已标记失败，地球币已扣除")
                                    reload()
                                }
                            },
                            onCancel = { id ->
                                scope.launch {
                                    client.earthCancelQuest(id)
                                    snackbarHostState.showSnackbar("任务已取消")
                                    reload()
                                }
                            },
                        )
                        2 -> CharacterList(
                            characters,
                            client,
                            templates,
                            onClick = { affinityTarget = it },
                            onDelete = { deleteCharacter = it },
                        )
                        3 -> StoryList(stories)
                    }
                }
            }
        }
    }

    // ── 新增弹窗 ──
    if (showAddDialog) {
        AddEntityDialog(
            tab = tab,
            templates = templates,
            onDismiss = { showAddDialog = false },
            onPhotoPicked = { uri -> uploadPickedPhoto(uri) },
            onConfirm = { payload ->
                showAddDialog = false
                scope.launch {
                    when (tab) {
                        0 -> client.earthCreateItem(payload)
                        1 -> client.earthCreateQuest(payload + mapOf("quest_type" to "branch", "source" to "manual"))
                        2 -> client.earthCreateCharacter(payload)
                        3 -> client.earthCreateStory(payload)
                    }
                    snackbarHostState.showSnackbar("已记录～")
                    reload()
                }
            },
        )
    }

    // ── 物品详情/编辑 ──
    detailItem?.let { item ->
        ItemDetailDialog(
            item = item,
            imageResolver = { path -> client.earthImageUrl(path) },
            onDismiss = { detailItem = null },
            onPhotoPicked = { uri -> uploadPickedPhoto(uri, item.id) },
            onSave = { id, data ->
                scope.launch {
                    client.earthUpdateItem(id, data)
                    snackbarHostState.showSnackbar("物品已更新")
                    detailItem = null
                    reload()
                }
            },
            onDelete = {
                detailItem = null
                deleteItem = item
            },
        )
    }

    // ── 物品档案弹窗 (前台展示: 封面 + 简介 + Markdown 详情) ──
    viewItem?.let { item ->
        ItemArchiveDialog(
            item = item,
            imageUrl = { path -> client.earthImageUrl(path) },
            onDismiss = { viewItem = null },
        )
    }

    // ── 好感度弹窗 ──
    affinityTarget?.let { c ->
        AffinityDialog(
            character = c,
            affinityLabel = affinityLevelLabel(templates, c.affinity),
            onDismiss = { affinityTarget = null },
            onConfirm = { delta, reason ->
                scope.launch {
                    client.earthAddAffinity(c.id, delta, reason)
                    snackbarHostState.showSnackbar("「${c.name}」好感度已更新")
                    affinityTarget = null
                    reload()
                }
            },
        )
    }

    // ── 删除确认 ──
    deleteItem?.let { item ->
        AlertDialog(
            onDismissRequest = { deleteItem = null },
            title = { Text("移除物品") },
            text = { Text("确认把「${item.name}」从背包里移除吗？") },
            confirmButton = {
                TextButton(onClick = {
                    deleteItem = null
                    scope.launch {
                        client.earthDeleteItem(item.id)
                        snackbarHostState.showSnackbar("物品已移除")
                        reload()
                    }
                }) { Text("移除", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = { TextButton(onClick = { deleteItem = null }) { Text("取消") } },
        )
    }

    deleteCharacter?.let { c ->
        AlertDialog(
            onDismissRequest = { deleteCharacter = null },
            title = { Text("移除角色") },
            text = { Text("确认把「${c.name}」从图鉴里移除吗？") },
            confirmButton = {
                TextButton(onClick = {
                    deleteCharacter = null
                    scope.launch {
                        client.earthDeleteCharacter(c.id)
                        snackbarHostState.showSnackbar("角色已移除")
                        reload()
                    }
                }) { Text("移除", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = { TextButton(onClick = { deleteCharacter = null }) { Text("取消") } },
        )
    }
}

private fun affinityLevelLabel(templates: EarthTemplates, affinity: Int): Pair<String, Color> {
    val level = templates.affinityLevels.find { affinity >= it.min && affinity <= it.max }
    if (level == null) return "未知" to Color.Gray
    val color = try {
        Color(android.graphics.Color.parseColor(level.color))
    } catch (_: Exception) {
        Color(0xFF9E9E9E)
    }
    return level.label to color
}

@Composable
private fun ModeSwitch(playerMode: Boolean, onModeChange: (Boolean) -> Unit) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 2.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        FilterChip(
            selected = playerMode,
            onClick = { onModeChange(true) },
            label = { Text("🎮 前台展示", fontSize = 12.sp) },
        )
        FilterChip(
            selected = !playerMode,
            onClick = { onModeChange(false) },
            label = { Text("🛠 后台管理", fontSize = 12.sp) },
        )
        Spacer(Modifier.weight(1f))
        Text(
            if (playerMode) "玩家 · 展示与接取" else "管理 · 录入数据",
            fontSize = 10.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun SyncBar(offline: Boolean, lastSync: Long, refreshing: Boolean, onRefresh: () -> Unit) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 14.dp, vertical = 4.dp),
    ) {
        if (offline) {
            Icon(Icons.Default.CloudOff, contentDescription = null, tint = Color(0xFFFF6B6B), modifier = Modifier.size(14.dp))
            Spacer(Modifier.width(5.dp))
            Text("离线模式 · 显示本地缓存 · ${formatSyncTime(lastSync)}", fontSize = 11.sp, color = Color(0xFFFF6B6B))
        } else {
            Text("已同步 · ${formatSyncTime(lastSync)}", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.weight(1f))
        IconButton(onClick = onRefresh, enabled = !refreshing, modifier = Modifier.size(28.dp)) {
            if (refreshing) {
                CircularProgressIndicator(modifier = Modifier.size(14.dp), strokeWidth = 2.dp)
            } else {
                Icon(Icons.Default.Refresh, contentDescription = "刷新", tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(16.dp))
            }
        }
    }
}

@Composable
private fun PlayerHeader(player: EarthPlayer?, client: MiyaApiClient) {
    val level = player?.level ?: 1
    val totalExp = player?.exp ?: 0
    val spentExp = (level - 1) * level / 2 * 100
    val levelExp = (totalExp - spentExp).coerceAtLeast(0)
    val levelNeed = level * 100
    val expProgress = if (levelNeed > 0) (levelExp.toFloat() / levelNeed).coerceIn(0f, 1f) else 0f
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 14.dp, vertical = 6.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(Brush.horizontalGradient(listOf(Color(0xFFC9AC67).copy(alpha = 0.14f), Color(0xFF141B24))))
            .border(1.dp, Color(0xFFC9AC67).copy(alpha = 0.3f), RoundedCornerShape(12.dp))
            .padding(horizontal = 12.dp, vertical = 8.dp),
    ) {
        Box(
            Modifier.size(36.dp).clip(RoundedCornerShape(9.dp))
                .background(Brush.linearGradient(listOf(Color(0xFFC9AC67), Color(0xFF7C4DFF)))),
            contentAlignment = Alignment.Center,
        ) {
            val url = client.earthImageUrl(player?.avatarPath ?: "")
            if (url.isNotEmpty()) {
                AsyncImage(model = url, contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
            } else {
                Text("地", color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Bold)
            }
        }
        Spacer(Modifier.width(10.dp))
        Row(verticalAlignment = Alignment.Bottom) {
            Text(player?.name?.ifEmpty { "玩家" } ?: "玩家", fontSize = 14.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.width(7.dp))
            Text("Lv.$level", color = Color(0xFFC9AC67), fontSize = 12.sp, fontWeight = FontWeight.Bold)
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            LinearProgressIndicator(
                progress = { expProgress },
                modifier = Modifier.fillMaxWidth().height(4.dp).clip(CircleShape),
                color = Color(0xFFC9AC67),
                trackColor = Color.White.copy(alpha = 0.12f),
            )
            Spacer(Modifier.height(2.dp))
            Text("经验 $levelExp/$levelNeed", fontSize = 9.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun EarthCard(modifier: Modifier, content: @Composable ColumnScope.() -> Unit) {
    Column(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(Color.Black.copy(alpha = 0.35f))
            .border(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.2f), RoundedCornerShape(12.dp))
            .padding(12.dp),
        content = content,
    )
}

@Composable
private fun FieldsChips(fields: Map<String, JsonElement>, limit: Int = 3) {
    val entries = fields.entries.take(limit)
    if (entries.isEmpty()) return
    Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
        entries.forEach { (k, v) ->
            val text = (v as? JsonPrimitive)?.contentOrNull ?: v.toString()
            Text(
                "$k: $text",
                fontSize = 10.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier
                    .border(1.dp, MiyaColors.Primary.copy(alpha = 0.3f), RoundedCornerShape(10.dp))
                    .padding(horizontal = 6.dp, vertical = 2.dp),
            )
        }
    }
}

// ── 前台展示面板 (玩家视角) ──

private fun questStars(difficulty: Int): String {
    val d = difficulty.coerceIn(1, 5)
    return "★".repeat(d) + "☆".repeat(5 - d)
}

@Composable
private fun PlayerModeContent(
    player: EarthPlayer?,
    client: MiyaApiClient,
    templates: EarthTemplates,
    items: List<EarthItem>,
    quests: List<EarthQuest>,
    characters: List<EarthCharacter>,
    stories: List<EarthStory>,
    onAccept: (Int) -> Unit,
    onComplete: (Int) -> Unit,
    onFail: (Int) -> Unit,
    onCancel: (Int) -> Unit,
    onCharacterClick: (EarthCharacter) -> Unit,
    onItemClick: (EarthItem) -> Unit,
) {
    var tab by remember { mutableIntStateOf(0) }
    val pending = quests.filter { it.status == "pending" }
    val ongoing = quests.filter { it.status == "ongoing" }
    val done = quests.filter { it.status in listOf("completed", "failed", "cancelled") }

    Column(Modifier.fillMaxSize()) {
        TabRow(
            selectedTabIndex = tab,
            containerColor = Color.Transparent,
            contentColor = MaterialTheme.colorScheme.onSurface,
        ) {
            listOf("主界面", "任务板", "背包", "角色", "剧情", "档案").forEachIndexed { index, label ->
                Tab(selected = tab == index, onClick = { tab = index }, text = { Text(label, fontSize = 13.sp) })
            }
        }
        when (tab) {
            0 -> HomeMenu(
                player = player,
                pendingCount = pending.size + ongoing.size,
                itemCount = items.size,
                charCount = characters.size,
                storyCount = stories.size,
                onNavigate = { tab = it },
            )
            1 -> LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                item { SectionHead("📜 可接取委托 (${pending.size})") }
                if (pending.isEmpty()) {
                    item { EarthCard(Modifier) { Text("暂时没有新委托，去后台让弥娅给你安排一个吧～", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant) } }
                } else {
                    items(pending, key = { it.id }) { q ->
                        EarthCard(Modifier) {
                            QuestBoardCard(q, templates, onPrimary = { onAccept(q.id) }, primaryLabel = "⚔ 接取委托")
                        }
                    }
                }
                item { SectionHead("🔥 进行中 (${ongoing.size})") }
                if (ongoing.isEmpty()) {
                    item { EarthCard(Modifier) { Text("没有进行中的任务～", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant) } }
                } else {
                    items(ongoing, key = { it.id }) { q ->
                        EarthCard(Modifier) {
                            QuestBoardCard(q, templates, onPrimary = { onComplete(q.id) }, primaryLabel = "✓ 完成", onFail = { onFail(q.id) }, onCancel = { onCancel(q.id) })
                        }
                    }
                }
                if (done.isNotEmpty()) {
                    item { SectionHead("🗂 已结束 (最近 ${done.take(8).size})") }
                    items(done.take(8), key = { it.id }) { q ->
                        EarthCard(Modifier) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    when (q.status) { "completed" -> "✓"; "failed" -> "✕"; else -> "−" },
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = when (q.status) { "completed" -> Color(0xFF81C784); "failed" -> Color(0xFFFF6B6B); else -> MaterialTheme.colorScheme.onSurfaceVariant },
                                )
                                Spacer(Modifier.width(8.dp))
                                Text(q.title, fontSize = 13.sp, modifier = Modifier.weight(1f))
                                Text((q.completedAt ?: "").take(16).replace('T', ' '), fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
            2 -> Column(Modifier.fillMaxSize()) {
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp)) {
                    Text("🎒 我的背包", fontSize = 14.sp, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.weight(1f))
                    Text(
                        "◆ 地球币 ${player?.currency ?: 0}",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFFC9AC67),
                        modifier = Modifier
                            .border(1.dp, Color(0xFFC9AC67).copy(alpha = 0.4f), RoundedCornerShape(20.dp))
                            .background(Color(0xFFC9AC67).copy(alpha = 0.1f), RoundedCornerShape(20.dp))
                            .padding(horizontal = 10.dp, vertical = 4.dp),
                    )
                }
                ItemList(items, client, onClick = onItemClick)
            }
            3 -> CharacterList(characters, client, templates, onClick = onCharacterClick, onDelete = null)
            4 -> StoryList(stories)
            5 -> ProfileTab(player, items.size, characters.size, stories.size)
        }
    }
}

@Composable
private fun HomeMenu(
    player: EarthPlayer?,
    pendingCount: Int,
    itemCount: Int,
    charCount: Int,
    storyCount: Int,
    onNavigate: (Int) -> Unit,
) {
    LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Column {
                Text(
                    "地球online",
                    fontSize = 22.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = 3.sp,
                    color = Color(0xFFC9AC67),
                )
                Spacer(Modifier.height(3.dp))
                Text("${player?.name ?: "玩家"}，欢迎回到你的现实游戏世界。", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        item { MenuCard("📜", "任务板", "QUEST BOARD", "$pendingCount 个任务进行中", { onNavigate(1) }) }
        item { MenuCard("🎒", "背包", "BACKPACK", "$itemCount 件物品 · ◆ ${player?.currency ?: 0} 地球币", { onNavigate(2) }) }
        item { MenuCard("💛", "角色图鉴", "CHARACTERS", "$charCount 位角色", { onNavigate(3) }) }
        item { MenuCard("📖", "人生剧情", "STORY", "$storyCount 段剧情", { onNavigate(4) }) }
        item { MenuCard("👤", "玩家档案", "PROFILE", "Lv.${player?.level ?: 1} · 属性 / 自传 / 生涯", { onNavigate(5) }) }
    }
}

@Composable
private fun MenuCard(icon: String, name: String, en: String, desc: String, onClick: () -> Unit) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(Brush.horizontalGradient(listOf(Color(0xFFC9AC67).copy(alpha = 0.1f), Color.Black.copy(alpha = 0.35f))))
            .border(1.dp, Color(0xFFC9AC67).copy(alpha = 0.25f), RoundedCornerShape(12.dp))
            .clickable { onClick() }
            .padding(14.dp),
    ) {
        Box(
            Modifier.size(44.dp).clip(RoundedCornerShape(11.dp))
                .background(Color(0xFFC9AC67).copy(alpha = 0.12f))
                .border(1.dp, Color(0xFFC9AC67).copy(alpha = 0.3f), RoundedCornerShape(11.dp)),
            contentAlignment = Alignment.Center,
        ) { Text(icon, fontSize = 20.sp) }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(name, fontSize = 15.sp, fontWeight = FontWeight.Bold)
            Text(en, fontSize = 9.sp, letterSpacing = 2.sp, color = Color(0xFFC9AC67).copy(alpha = 0.7f))
            Spacer(Modifier.height(3.dp))
            Text(desc, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Text("›", fontSize = 20.sp, color = Color(0xFFC9AC67).copy(alpha = 0.6f))
    }
}

@Composable
private fun ProfileTab(player: EarthPlayer?, itemCount: Int, charCount: Int, storyCount: Int) {
    LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            EarthCard(Modifier) {
                Text("📝 关于我", fontSize = 14.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(6.dp))
                if (!player?.bio.isNullOrEmpty()) {
                    Text(player?.bio ?: "", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 20.sp)
                } else {
                    Text("还没有自我介绍～ 在后台管理 → 编辑玩家卡里，用 Markdown 写一段关于自己的文字吧。", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        item {
            EarthCard(Modifier) {
                Text("🏅 生涯数据", fontSize = 14.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    CareerStat(player?.totalCompleted ?: 0, "完成任务", Modifier.weight(1f))
                    CareerStat(player?.totalFailed ?: 0, "失败任务", Modifier.weight(1f))
                    CareerStat(itemCount, "背包物品", Modifier.weight(1f))
                }
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    CareerStat(charCount, "图鉴角色", Modifier.weight(1f))
                    CareerStat(storyCount, "剧情记录", Modifier.weight(1f))
                }
            }
        }
        item {
            EarthCard(Modifier) {
                Text("💡 小提示", fontSize = 14.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(6.dp))
                Text("昵称、头像、简介都可以在「后台管理 → 编辑玩家卡」中自定义。你的数据全部保存在弥娅主机上，手机本地有缓存，离线也能看。", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 19.sp)
            }
        }
    }
}

@Composable
private fun CareerStat(num: Int, label: String, modifier: Modifier = Modifier) {
    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = modifier) {
        Text(num.toString(), fontSize = 17.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFFD54F))
        Text(label, fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun SectionHead(text: String) {
    Text(text, fontSize = 14.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(vertical = 2.dp))
}

@Composable
private fun QuestBoardCard(
    q: EarthQuest,
    templates: EarthTemplates,
    onPrimary: () -> Unit,
    primaryLabel: String,
    onFail: (() -> Unit)? = null,
    onCancel: (() -> Unit)? = null,
) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            QuestTypeLabels[q.questType] ?: q.questType,
            fontSize = 11.sp,
            color = MiyaColors.Primary,
            modifier = Modifier.border(1.dp, MiyaColors.Primary.copy(alpha = 0.4f), RoundedCornerShape(4.dp)).padding(horizontal = 6.dp, vertical = 2.dp),
        )
        Spacer(Modifier.width(6.dp))
        Text(questStars(q.difficulty), fontSize = 11.sp, color = Color(0xFFFFB300))
        if (q.mustComplete) { Spacer(Modifier.width(6.dp)); Text("必须", fontSize = 11.sp, color = Color(0xFFFF6B6B)) }
        if (q.source == "miya") { Spacer(Modifier.width(6.dp)); Text("弥娅安排", fontSize = 10.sp, color = Color(0xFF7C4DFF)) }
    }
    Spacer(Modifier.height(6.dp))
    Text(q.title, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
    if (q.description.isNotEmpty()) { Spacer(Modifier.height(2.dp)); Text(q.description, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    Spacer(Modifier.height(4.dp))
    FieldsChips(q.fields)
    Spacer(Modifier.height(6.dp))
    Row {
        Text("+${q.rewardCurrency} 币", fontSize = 12.sp, color = Color(0xFFFFD54F))
        Spacer(Modifier.width(10.dp))
        Text("+${q.rewardExp} 经验", fontSize = 12.sp, color = Color(0xFFFFD54F))
        if (q.penaltyCurrency > 0) { Spacer(Modifier.width(10.dp)); Text("鸽: -${q.penaltyCurrency} 币", fontSize = 12.sp, color = Color(0xFFFF6B6B)) }
        if (q.deadline.isNotEmpty()) { Spacer(Modifier.width(10.dp)); Text("截止 ${q.deadline.take(16).replace('T', ' ')}", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
    Spacer(Modifier.height(8.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(
            onClick = onPrimary,
            modifier = Modifier.weight(1f),
            colors = ButtonDefaults.buttonColors(containerColor = if (primaryLabel.startsWith("⚔")) Color(0xFFFFB300) else MiyaColors.Primary, contentColor = if (primaryLabel.startsWith("⚔")) Color(0xFF1A1206) else Color.White),
        ) { Text(primaryLabel) }
        if (onCancel != null) {
            OutlinedButton(onClick = onCancel, modifier = Modifier.weight(1f)) { Text("取消") }
        }
        if (onFail != null) {
            OutlinedButton(
                onClick = onFail,
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = Color(0xFFFF6B6B)),
            ) { Text("放弃") }
        }
    }
}

@Composable
private fun ItemList(items: List<EarthItem>, client: MiyaApiClient, onClick: (EarthItem) -> Unit) {
    if (items.isEmpty()) { EmptyHint("背包还是空的呢，亲爱的，拍张照记录点什么吧～"); return }
    LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        items(items, key = { it.id }) { item ->
            val color = RarityColors[item.rarity] ?: Color.Gray
            EarthCard(Modifier.clickable { onClick(item) }) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        Modifier.size(52.dp).clip(RoundedCornerShape(10.dp)).background(color.copy(alpha = 0.2f)),
                        contentAlignment = Alignment.Center,
                    ) {
                        val url = client.earthImageUrl(item.imagePath)
                        if (url.isNotEmpty()) {
                            AsyncImage(model = url, contentDescription = item.name, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
                        } else {
                            Text(item.name.take(1), fontSize = 20.sp, color = color, fontWeight = FontWeight.Bold)
                        }
                    }
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(item.name, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                            if (item.quantity > 1) { Spacer(Modifier.width(6.dp)); Text("×${item.quantity}", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                        }
                        Text("${CategoryLabels[item.category] ?: item.category} · ${RarityLabels[item.rarity] ?: item.rarity}", fontSize = 11.sp, color = color)
                        if (item.description.isNotEmpty()) Text(item.description, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
                        Spacer(Modifier.height(3.dp))
                        FieldsChips(item.fields)
                    }
                }
            }
        }
    }
}

@Composable
private fun QuestList(
    quests: List<EarthQuest>,
    onComplete: (Int) -> Unit,
    onFail: (Int) -> Unit,
    onCancel: (Int) -> Unit,
) {
    if (quests.isEmpty()) { EmptyHint("还没有任务，让弥娅给你安排一个吧～"); return }
    LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        items(quests, key = { it.id }) { q ->
            EarthCard(Modifier) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        QuestTypeLabels[q.questType] ?: q.questType,
                        fontSize = 11.sp,
                        color = MiyaColors.Primary,
                        modifier = Modifier.border(1.dp, MiyaColors.Primary.copy(alpha = 0.4f), RoundedCornerShape(4.dp)).padding(horizontal = 6.dp, vertical = 2.dp),
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(if (q.mustComplete) "必须" else "可选", fontSize = 11.sp, color = if (q.mustComplete) Color(0xFFFFB300) else MiyaColors.Primary)
                    if (q.source == "miya") { Spacer(Modifier.width(6.dp)); Text("弥娅安排", fontSize = 10.sp, color = Color(0xFF7C4DFF)) }
                    Spacer(Modifier.weight(1f))
                    Text(QuestStatusLabels[q.status] ?: q.status, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Spacer(Modifier.height(6.dp))
                Text(q.title, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                if (q.description.isNotEmpty()) { Spacer(Modifier.height(2.dp)); Text(q.description, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                Spacer(Modifier.height(4.dp))
                FieldsChips(q.fields)
                Spacer(Modifier.height(6.dp))
                Row {
                    Text(questStars(q.difficulty), fontSize = 11.sp, color = Color(0xFFFFB300))
                    Spacer(Modifier.width(10.dp))
                    Text("+${q.rewardCurrency} 币", fontSize = 12.sp, color = Color(0xFFFFD54F))
                    Spacer(Modifier.width(10.dp))
                    Text("+${q.rewardExp} 经验", fontSize = 12.sp, color = Color(0xFFFFD54F))
                    if (q.penaltyCurrency > 0) { Spacer(Modifier.width(10.dp)); Text("鸽: -${q.penaltyCurrency} 币", fontSize = 12.sp, color = Color(0xFFFF6B6B)) }
                    if (q.deadline.isNotEmpty()) { Spacer(Modifier.width(10.dp)); Text("截止 ${q.deadline.take(16).replace('T', ' ')}", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
                if (q.status == "pending" || q.status == "ongoing") {
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = { onComplete(q.id) },
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.buttonColors(containerColor = MiyaColors.Primary),
                        ) { Text("✓ 完成") }
                        OutlinedButton(onClick = { onCancel(q.id) }, modifier = Modifier.weight(1f)) { Text("取消") }
                        OutlinedButton(
                            onClick = { onFail(q.id) },
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = Color(0xFFFF6B6B)),
                        ) { Text("失败") }
                    }
                }
            }
        }
    }
}

@Composable
private fun CharacterList(
    characters: List<EarthCharacter>,
    client: MiyaApiClient,
    templates: EarthTemplates,
    onClick: (EarthCharacter) -> Unit,
    onDelete: ((EarthCharacter) -> Unit)?,
) {
    if (characters.isEmpty()) { EmptyHint("图鉴里还没有角色，先记录一位重要的人吧～"); return }
    LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        items(characters, key = { it.id }) { c ->
            val (stageLabel, stageColor) = affinityLevelLabel(templates, c.affinity)
            EarthCard(Modifier.clickable { onClick(c) }) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        Modifier.size(44.dp).clip(CircleShape).background(MiyaColors.Primary.copy(alpha = 0.25f)),
                        contentAlignment = Alignment.Center,
                    ) {
                        val url = client.earthImageUrl(c.avatarPath)
                        if (url.isNotEmpty()) {
                            AsyncImage(model = url, contentDescription = c.name, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
                        } else {
                            Text(c.name.take(1), color = MiyaColors.Primary, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(c.name, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                            if (c.nickname.isNotEmpty()) { Spacer(Modifier.width(6.dp)); Text(c.nickname, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(RelationshipLabels[c.relationship] ?: c.relationship, fontSize = 11.sp, color = MiyaColors.Primary)
                            Spacer(Modifier.width(6.dp))
                            Text(stageLabel, fontSize = 11.sp, color = stageColor, fontWeight = FontWeight.SemiBold)
                        }
                        Spacer(Modifier.height(4.dp))
                        LinearProgressIndicator(
                            progress = { c.affinity / 100f },
                            modifier = Modifier.fillMaxWidth().height(6.dp).clip(CircleShape),
                            color = Color(0xFFFFD54F),
                            trackColor = Color.White.copy(alpha = 0.12f),
                        )
                        if (c.notes.isNotEmpty()) { Spacer(Modifier.height(4.dp)); Text(c.notes, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2) }
                        Spacer(Modifier.height(3.dp))
                        FieldsChips(c.fields)
                    }
                    Spacer(Modifier.width(8.dp))
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(Icons.Default.Star, contentDescription = null, tint = Color(0xFFFFD54F), modifier = Modifier.size(16.dp))
                        Text(c.affinity.toString(), fontSize = 15.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFFD54F))
                    }
                    if (onDelete != null) {
                        IconButton(onClick = { onDelete(c) }) {
                            Icon(Icons.Default.Delete, contentDescription = "删除", tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(18.dp))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StoryList(stories: List<EarthStory>) {
    if (stories.isEmpty()) { EmptyHint("还没有剧情记录，亲爱的，今天有什么故事想告诉我吗？"); return }
    LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        items(stories, key = { it.id }) { s ->
            EarthCard(Modifier) {
                Text(s.title, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                if (s.content.isNotEmpty()) { Spacer(Modifier.height(4.dp)); Text(s.content, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                Spacer(Modifier.height(4.dp))
                Text(s.happenedAt.take(16).replace('T', ' '), fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun EmptyHint(text: String) {
    Box(Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
        Text(text, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

// ── 通用照片选择组件 ──

@Composable
private fun PhotoPickerBox(
    preview: Any?,
    onPicked: (Uri) -> Unit,
) {
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) onPicked(uri)
    }
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Box(
            Modifier.size(64.dp).clip(RoundedCornerShape(10.dp)).background(Color.White.copy(alpha = 0.06f))
                .border(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.3f), RoundedCornerShape(10.dp)),
            contentAlignment = Alignment.Center,
        ) {
            if (preview != null) {
                AsyncImage(model = preview, contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
            } else {
                Icon(Icons.Default.CameraAlt, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        OutlinedButton(onClick = { launcher.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }) {
            Icon(Icons.Default.CameraAlt, contentDescription = null, modifier = Modifier.size(16.dp))
            Spacer(Modifier.width(6.dp))
            Text("拍照/选照片", fontSize = 13.sp)
        }
    }
}

// ── 新增实体弹窗 (带模板下拉) ──

@Composable
private fun AddEntityDialog(
    tab: Int,
    templates: EarthTemplates,
    onDismiss: () -> Unit,
    onPhotoPicked: suspend (Uri) -> String,
    onConfirm: (Map<String, Any?>) -> Unit,
) {
    var field1 by remember { mutableStateOf("") }
    var field2 by remember { mutableStateOf("") }
    var must by remember { mutableStateOf(false) }
    var category by remember { mutableStateOf("digital") }
    var rarity by remember { mutableStateOf("common") }
    var relationship by remember { mutableStateOf("friend") }
    var questTemplateId by remember { mutableStateOf("custom") }
    var pickedUri by remember { mutableStateOf<Uri?>(null) }
    var uploadedPath by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()

    val title = when (tab) {
        0 -> "新增物品"; 1 -> "新任务"; 2 -> "新增角色"; else -> "记录剧情"
    }
    val label1 = when (tab) { 0 -> "名称"; 1 -> "标题"; 2 -> "姓名"; else -> "标题" }
    val label2 = when (tab) { 0 -> "描述"; 1 -> "描述"; 2 -> "昵称"; else -> "内容" }
    val hint1 = when (tab) { 0 -> "物品名称"; 1 -> "任务标题"; 2 -> "现实中的人物"; else -> "事件的标题" }
    val hint2 = when (tab) { 0 -> "这件物品对你的意义…"; 1 -> "任务详情…"; 2 -> "昵称/称呼"; else -> "这一天发生了什么…" }
    val hasPhoto = tab == 0 || tab == 2

    val selectedQuestTemplate: EarthQuestTemplate? = templates.quests.find { it.id == questTemplateId }

    Dialog(onDismissRequest = onDismiss) {
        Card(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Color(0xFF161D26)).padding(20.dp),
        ) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(value = field1, onValueChange = { field1 = it }, label = { Text(label1) }, placeholder = { Text(hint1) }, singleLine = true, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(value = field2, onValueChange = { field2 = it }, label = { Text(label2) }, placeholder = { Text(hint2) }, modifier = Modifier.fillMaxWidth(), minLines = 2)

            if (tab == 0) {
                Spacer(Modifier.height(8.dp))
                Text("分类 (决定模板参数)", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                    CategoryLabels.forEach { (key, label) ->
                        FilterChip(
                            selected = category == key,
                            onClick = { category = key },
                            label = { Text(label, fontSize = 12.sp) },
                        )
                    }
                }
                Spacer(Modifier.height(6.dp))
                Text("稀有度", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                    RarityLabels.forEach { (key, label) ->
                        FilterChip(
                            selected = rarity == key,
                            onClick = { rarity = key },
                            label = { Text(label, fontSize = 12.sp) },
                        )
                    }
                }
            }

            if (tab == 1) {
                Spacer(Modifier.height(8.dp))
                Text("任务模板", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                    FilterChip(
                        selected = questTemplateId == "custom",
                        onClick = { questTemplateId = "custom" },
                        label = { Text("自定义", fontSize = 12.sp) },
                    )
                    templates.quests.forEach { tpl ->
                        FilterChip(
                            selected = questTemplateId == tpl.id,
                            onClick = { questTemplateId = tpl.id },
                            label = { Text(tpl.label, fontSize = 12.sp) },
                        )
                    }
                }
                Spacer(Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = must, onCheckedChange = { must = it })
                    Text("必须任务（失败会惩罚）", fontSize = 13.sp)
                }
            }

            if (tab == 2) {
                Spacer(Modifier.height(8.dp))
                Text("关系 (决定模板参数)", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                    RelationshipLabels.forEach { (key, label) ->
                        FilterChip(
                            selected = relationship == key,
                            onClick = { relationship = key },
                            label = { Text(label, fontSize = 12.sp) },
                        )
                    }
                }
            }

            if (hasPhoto) {
                Spacer(Modifier.height(10.dp))
                PhotoPickerBox(
                    preview = pickedUri,
                    onPicked = { uri ->
                        pickedUri = uri
                        scope.launch {
                            uploadedPath = onPhotoPicked(uri)
                            if (uploadedPath.isEmpty()) { pickedUri = null }
                        }
                    },
                )
            }
            Spacer(Modifier.height(16.dp))
            Row(horizontalArrangement = Arrangement.End, modifier = Modifier.fillMaxWidth()) {
                TextButton(onClick = onDismiss) { Text("取消") }
                Spacer(Modifier.width(8.dp))
                Button(
                    onClick = {
                        val primary = field1.trim()
                        if (primary.isEmpty()) return@Button
                        when (tab) {
                            0 -> onConfirm(mapOf(
                                "name" to primary, "description" to field2,
                                "rarity" to rarity, "category" to category,
                                "image_path" to uploadedPath,
                            ))
                            1 -> onConfirm(mapOf(
                                "title" to primary, "description" to field2, "must_complete" to must,
                                "reward_currency" to (selectedQuestTemplate?.rewardCurrency ?: 10),
                                "reward_exp" to (selectedQuestTemplate?.rewardExp ?: 15),
                                "penalty_currency" to (selectedQuestTemplate?.penaltyCurrency ?: if (must) 50 else 20),
                                "difficulty" to (selectedQuestTemplate?.difficulty ?: 1),
                            ))
                            2 -> onConfirm(mapOf(
                                "name" to primary, "nickname" to field2,
                                "relationship" to relationship, "affinity" to 0,
                                "avatar_path" to uploadedPath,
                            ))
                            else -> onConfirm(mapOf("title" to primary, "content" to field2, "event_type" to "life"))
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MiyaColors.Primary),
                ) { Text("保存") }
            }
        }
    }
}

// ── 物品档案弹窗 (前台: 封面 + 简介 + Markdown 详情) ──

@Composable
private fun ItemArchiveDialog(
    item: EarthItem,
    imageUrl: (String) -> String,
    onDismiss: () -> Unit,
) {
    Dialog(onDismissRequest = onDismiss) {
        Card(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Color(0xFF161D26)).padding(20.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("物品档案", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                TextButton(onClick = onDismiss) { Text("关闭") }
            }
            Spacer(Modifier.height(8.dp))
            val color = RarityColors[item.rarity] ?: Color.Gray
            Box(
                Modifier.fillMaxWidth().height(140.dp).clip(RoundedCornerShape(12.dp)).background(color.copy(alpha = 0.15f)),
                contentAlignment = Alignment.Center,
            ) {
                val url = imageUrl(item.imagePath)
                if (url.isNotEmpty()) {
                    AsyncImage(model = url, contentDescription = item.name, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
                } else {
                    Text(item.name.take(1), fontSize = 40.sp, color = color, fontWeight = FontWeight.Bold)
                }
            }
            Spacer(Modifier.height(10.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(item.name, fontSize = 17.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                Text("${CategoryLabels[item.category] ?: item.category} · ${RarityLabels[item.rarity] ?: item.rarity}", fontSize = 11.sp, color = color)
            }
            Spacer(Modifier.height(8.dp))
            Text("📋 简介", fontSize = 13.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(3.dp))
            Text(item.description.ifEmpty { "还没有简介～" }, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 18.sp)
            Spacer(Modifier.height(4.dp))
            FieldsChips(item.fields)
            Spacer(Modifier.height(8.dp))
            Text("📄 详细档案", fontSize = 13.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(4.dp))
            Column(
                Modifier.fillMaxWidth().heightIn(max = 220.dp).verticalScroll(rememberScrollState())
                    .background(Color.Black.copy(alpha = 0.3f), RoundedCornerShape(10.dp))
                    .border(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.15f), RoundedCornerShape(10.dp))
                    .padding(10.dp),
            ) {
                Text(
                    item.markdown.ifEmpty { "_还没有详细档案，去后台用 Markdown 写一份吧～_" },
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    lineHeight = 19.sp,
                )
            }
            Spacer(Modifier.height(12.dp))
        }
    }
}

// ── 物品详情/编辑弹窗 ──

@Composable
private fun ItemDetailDialog(
    item: EarthItem,
    imageResolver: (String) -> String,
    onDismiss: () -> Unit,
    onPhotoPicked: suspend (Uri) -> String,
    onSave: (Int, Map<String, Any?>) -> Unit,
    onDelete: () -> Unit,
) {
    var name by remember { mutableStateOf(item.name) }
    var description by remember { mutableStateOf(item.description) }
    var quantity by remember { mutableStateOf(item.quantity.toString()) }
    var markdown by remember { mutableStateOf(item.markdown) }
    var previewPath by remember { mutableStateOf(item.imagePath) }
    var previewUri by remember { mutableStateOf<Uri?>(null) }
    val scope = rememberCoroutineScope()

    Dialog(onDismissRequest = onDismiss) {
        Card(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Color(0xFF161D26)).padding(20.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("物品详情", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                IconButton(onClick = onDelete) {
                    Icon(Icons.Default.Delete, contentDescription = "移除", tint = MaterialTheme.colorScheme.error)
                }
            }
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("名称") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(value = description, onValueChange = { description = it }, label = { Text("描述") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(value = quantity, onValueChange = { quantity = it }, label = { Text("数量") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(value = markdown, onValueChange = { markdown = it }, label = { Text("详细档案 (Markdown)") }, placeholder = { Text("# 档案标题…") }, modifier = Modifier.fillMaxWidth(), minLines = 3)
            Spacer(Modifier.height(10.dp))
            PhotoPickerBox(
                preview = previewUri ?: imageResolver(previewPath).ifEmpty { null },
                onPicked = { uri ->
                    previewUri = uri
                    scope.launch {
                        val path = onPhotoPicked(uri)
                        if (path.isNotEmpty()) {
                            previewPath = path
                            previewUri = null
                        }
                    }
                },
            )
            Spacer(Modifier.height(16.dp))
            Row(horizontalArrangement = Arrangement.End, modifier = Modifier.fillMaxWidth()) {
                TextButton(onClick = onDismiss) { Text("取消") }
                Spacer(Modifier.width(8.dp))
                Button(
                    onClick = {
                        val qty = quantity.toIntOrNull()?.coerceAtLeast(1) ?: 1
                        onSave(item.id, mapOf("name" to name.trim(), "description" to description, "quantity" to qty, "image_path" to previewPath, "markdown" to markdown))
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MiyaColors.Primary),
                ) { Text("保存") }
            }
        }
    }
}

// ── 好感度弹窗 ──

@Composable
private fun AffinityDialog(
    character: EarthCharacter,
    affinityLabel: Pair<String, Color>,
    onDismiss: () -> Unit,
    onConfirm: (delta: Int, reason: String) -> Unit,
) {
    var reason by remember { mutableStateOf("") }
    val presets = listOf(-10, -5, -1, 1, 3, 5, 10)
    Dialog(onDismissRequest = onDismiss) {
        Card(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Color(0xFF161D26)).padding(20.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("「${character.name}」好感度", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                Text(affinityLabel.first, fontSize = 13.sp, color = affinityLabel.second, fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.height(4.dp))
            Text("当前: ${character.affinity}/100", fontSize = 13.sp, color = Color(0xFFFFD54F))
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.fillMaxWidth()) {
                presets.forEach { d ->
                    OutlinedButton(
                        onClick = { onConfirm(d, reason.trim()) },
                        modifier = Modifier.weight(1f),
                        colors = if (d > 0) ButtonDefaults.outlinedButtonColors(contentColor = Color(0xFFFFD54F))
                        else ButtonDefaults.outlinedButtonColors(contentColor = Color(0xFFFF6B6B)),
                    ) { Text(if (d > 0) "+$d" else "$d", fontSize = 13.sp) }
                }
            }
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(value = reason, onValueChange = { reason = it }, label = { Text("原因（比如：一起吃了顿饭）") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
            if (character.notes.isNotEmpty() || character.markdown.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text("📄 详细档案", fontSize = 13.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(4.dp))
                Column(
                    Modifier.fillMaxWidth().heightIn(max = 180.dp).verticalScroll(rememberScrollState())
                        .background(Color.Black.copy(alpha = 0.3f), RoundedCornerShape(10.dp))
                        .border(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.15f), RoundedCornerShape(10.dp))
                        .padding(10.dp),
                ) {
                    if (character.notes.isNotEmpty()) {
                        Text(character.notes, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 18.sp)
                        Spacer(Modifier.height(6.dp))
                    }
                    if (character.markdown.isNotEmpty()) {
                        Text(character.markdown, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 19.sp)
                    }
                }
            }
            Spacer(Modifier.height(16.dp))
            Row(horizontalArrangement = Arrangement.End, modifier = Modifier.fillMaxWidth()) {
                TextButton(onClick = onDismiss) { Text("取消") }
            }
        }
    }
}
