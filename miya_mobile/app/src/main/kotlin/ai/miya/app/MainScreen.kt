package ai.miya.app

import ai.miya.app.earthonline.EarthOnlineScreen
import ai.miya.feature.chat.ChatScreen
import ai.miya.feature.chat.SessionListScreen
import ai.miya.feature.settings.SettingsScreen
import ai.miya.uicommon.component.MiyaBackground
import ai.miya.uicommon.theme.*
import androidx.activity.compose.BackHandler
import androidx.compose.animation.*
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun MainScreen(
    deepLinkSessionId: String? = null,
    onSessionConsumed: (() -> Unit)? = null,
) {
    var selectedTab by remember { mutableIntStateOf(0) }
    var activeSessionId by remember { mutableStateOf(deepLinkSessionId) }

    LaunchedEffect(deepLinkSessionId) {
        if (deepLinkSessionId != null) {
            activeSessionId = deepLinkSessionId
            onSessionConsumed?.invoke()
        }
    }

    val theme by collectAsState()
    val bgUri by backgroundUri.collectAsState()

    BackHandler(enabled = activeSessionId != null || selectedTab == 1 || selectedTab == 2) {
        when {
            activeSessionId != null -> activeSessionId = null
            selectedTab == 1 -> selectedTab = 0
            selectedTab == 2 -> selectedTab = 0
        }
    }

    MiyaTheme {
        Box(modifier = Modifier.fillMaxSize()) {
            MiyaBackground(accentColor = theme.primary, backgroundUri = bgUri)

            if (activeSessionId != null) {
                ChatScreen(sessionId = activeSessionId!!, onBack = { activeSessionId = null })
            } else {
                Scaffold(
                    containerColor = Color.Transparent,
                    contentColor = theme.onSurface,
                    bottomBar = {
                        Box(
                            modifier = Modifier.fillMaxWidth().padding(bottom = 4.dp)
                                .background(Brush.verticalGradient(listOf(Color.Transparent, MaterialTheme.colorScheme.background.copy(alpha = 0.5f), MaterialTheme.colorScheme.background.copy(alpha = 0.85f))))
                                .padding(vertical = 6.dp),
                        ) {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                                TabItem(selected = selectedTab == 0, onClick = { selectedTab = 0; activeSessionId = null },
                                    icon = { Icon(Icons.Default.QuestionAnswer, null, modifier = Modifier.size(20.dp)) }, label = "聊天")
                                TabItem(selected = selectedTab == 1, onClick = { selectedTab = 1; activeSessionId = null },
                                    icon = { Icon(Icons.Default.Star, null, modifier = Modifier.size(20.dp)) }, label = "地球")
                                TabItem(selected = selectedTab == 2, onClick = { selectedTab = 2; activeSessionId = null },
                                    icon = { Icon(Icons.Default.Settings, null, modifier = Modifier.size(20.dp)) }, label = "设置")
                            }
                        }
                    },
                ) { innerPadding ->
                    Box(Modifier.padding(innerPadding).fillMaxSize()) {
                        when (selectedTab) {
                            0 -> SessionListScreen(onEnterSession = { sessionId -> activeSessionId = sessionId })
                            1 -> EarthOnlineScreen()
                            2 -> SettingsScreen()
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TabItem(selected: Boolean, onClick: () -> Unit, icon: @Composable () -> Unit, label: String) {
    val color by animateColorAsState(if (selected) MiyaColors.Primary else Color.White.copy(alpha = 0.4f), tween(200))
    Column(Modifier.clickable(onClick = onClick).padding(horizontal = 24.dp, vertical = 0.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        icon()
        Spacer(Modifier.height(1.dp))
        CompositionLocalProvider(LocalContentColor provides color) {
            Text(label, fontSize = 9.sp, fontWeight = if (selected) FontWeight.Medium else FontWeight.Normal)
        }
    }
}
