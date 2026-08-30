package ai.miya.feature.chat

import ai.miya.uicommon.component.MiyaChatAvatar
import ai.miya.uicommon.theme.MiyaColors
import androidx.compose.animation.*
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import java.text.SimpleDateFormat
import java.util.*

@Composable
fun SessionListScreen(
    onEnterSession: (String) -> Unit,
    viewModel: ChatViewModel = androidx.lifecycle.viewmodel.compose.viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LaunchedEffect(Unit) { viewModel.loadSessions() }

    LazyColumn(
        modifier = Modifier.fillMaxSize().statusBarsPadding(),
        contentPadding = PaddingValues(bottom = 12.dp),
    ) {
        // 弥娅固定入口卡片
        item(key = "miya_entry") {
            MiyaEntryCard(onClick = { onEnterSession("default") })
            Spacer(Modifier.height(12.dp))
        }

        // 历史会话标题（仅在有历史会话时显示）
        if (state.sessions.any { it.id != "default" }) {
            item(key = "history_header") {
                Text(
                    "历史会话",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                )
            }
        }

        // 历史会话列表
        val historySessions = state.sessions.filter { it.id != "default" }
        if (historySessions.isNotEmpty()) {
            items(historySessions, key = { it.id }) { session ->
                SessionListItem(
                    session = session,
                    onClick = { onEnterSession(session.id) },
                    onDelete = { viewModel.deleteSession(session.id) },
                )
            }
        }
    }
}

@Composable
private fun MiyaEntryCard(onClick: () -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 14.dp).clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        color = MiyaColors.Primary.copy(alpha = 0.08f),
        tonalElevation = 0.dp,
    ) {
        Row(
            Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            MiyaChatAvatar(size = 56.dp)

            Spacer(Modifier.width(14.dp))

            Column(Modifier.weight(1f)) {
                Text(
                    "弥娅",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = MiyaColors.Primary,
                )
                Spacer(Modifier.height(2.dp))
                Text(
                    "AI 虚拟化身 · 随时陪我聊天",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Icon(
                Icons.Default.ChevronRight,
                contentDescription = null,
                tint = MiyaColors.Primary.copy(alpha = 0.5f),
                modifier = Modifier.size(22.dp),
            )
        }
    }
}

@Composable
private fun SessionListItem(
    session: ai.miya.model.SessionInfo,
    onClick: () -> Unit,
    onDelete: () -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // Small avatar placeholder
        Box(
            Modifier.size(44.dp).background(MiyaColors.Secondary.copy(alpha = 0.1f), RoundedCornerShape(12.dp)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Default.ChatBubbleOutline, null, tint = MiyaColors.Secondary, modifier = Modifier.size(20.dp))
        }

        Spacer(Modifier.width(12.dp))

        Column(Modifier.weight(1f)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(
                    session.displayName ?: session.name ?: "会话",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f, fill = false),
                )
                Text(
                    formatSessionTime(session.updatedAt ?: session.createdAt),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(2.dp))
            Text(
                session.lastMessage ?: "${session.messageCount ?: 0}条消息",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }

        IconButton(onClick = onDelete, modifier = Modifier.size(28.dp)) {
            Icon(Icons.Default.Close, "删除", modifier = Modifier.size(14.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.3f))
        }
    }

    Box(Modifier.fillMaxWidth().padding(start = 72.dp, end = 16.dp).height(0.5.dp).background(Color.White.copy(alpha = 0.04f)))
}

private fun formatSessionTime(dateStr: String?): String {
    if (dateStr == null) return ""
    return try {
        val iso = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.getDefault())
        val date = iso.parse(dateStr) ?: return ""
        val diff = System.currentTimeMillis() - date.time
        when {
            diff < 60_000 -> "刚刚"
            diff < 3600_000 -> "${diff / 60_000}分钟前"
            diff < 86_400_000 -> "${diff / 3600_000}小时前"
            diff < 172_800_000 -> "昨天"
            else -> SimpleDateFormat("MM/dd", Locale.getDefault()).format(date)
        }
    } catch (_: Exception) { "" }
}
