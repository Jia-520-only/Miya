package ai.miya.feature.settings

import ai.miya.domain.ConnectionProvider
import ai.miya.domain.ConnectionStatus
import ai.miya.domain.PreferenceProvider
import ai.miya.domain.ServiceRegistry
import ai.miya.uicommon.component.ConnectionDot
import ai.miya.uicommon.component.ConnectionDotState
import ai.miya.uicommon.theme.*
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.*
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import coil.compose.AsyncImage
import coil.request.ImageRequest
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

data class SettingsState(
    val connectionStatus: ConnectionStatus = ConnectionStatus.DISCONNECTED,
    val serverHost: String = "",
    val serverPort: String = "8000",
    val isConnecting: Boolean = false,
    val error: String? = null,
    val selectedThemeColor: Color = WarmAnime.Primary,
    val backgroundUri: Uri? = null,
)

class SettingsViewModel : androidx.lifecycle.ViewModel() {

    private val _state = MutableStateFlow(SettingsState())
    val state: StateFlow<SettingsState> = _state.asStateFlow()

    init { observeConnection(); loadPersistedSettings() }

    private fun observeConnection() {
        viewModelScope.launch {
            val cp = ServiceRegistry.get(ConnectionProvider::class.java)
            cp?.state?.collect { cs ->
                _state.update { it.copy(
                    connectionStatus = cs.status,
                    serverHost = cs.baseUrl.removePrefix("http://").split(":")[0],
                    serverPort = cs.baseUrl.removePrefix("http://").split(":").getOrElse(1) { "8000" },
                    error = cs.error,
                    isConnecting = cs.status == ConnectionStatus.CONNECTING,
                ) }
            }
        }
    }

    private fun loadPersistedSettings() {
        viewModelScope.launch {
            try {
                val pref = ServiceRegistry.getOrThrow(PreferenceProvider::class.java)

                pref.themeColorArgb.first()?.let { argb ->
                    _state.update { it.copy(selectedThemeColor = Color(argb)) }
                }

                pref.backgroundFilePath.first()?.let { path ->
                    val file = java.io.File(path)
                    if (file.exists()) {
                        _state.update { it.copy(backgroundUri = Uri.fromFile(file)) }
                    }
                }

                pref.serverHost.first()?.let { host ->
                    if (host.isNotEmpty()) _state.update { it.copy(serverHost = host) }
                }
                pref.serverPort.first()?.let { port ->
                    if (port.isNotEmpty()) _state.update { it.copy(serverPort = port) }
                }
            } catch (e: Exception) {
                android.util.Log.e("Settings", "Failed to load persisted settings", e)
            }
        }
    }

    fun onHostChanged(v: String) { _state.update { it.copy(serverHost = v, error = null) } }
    fun onPortChanged(v: String) { _state.update { it.copy(serverPort = v, error = null) } }

    fun connect() {
        _state.update { it.copy(isConnecting = true, error = null) }
        viewModelScope.launch {
            try {
                val cp = ServiceRegistry.getOrThrow(ConnectionProvider::class.java)
                val host = _state.value.serverHost.ifBlank { "localhost" }
                val port = _state.value.serverPort.toIntOrNull() ?: 8000
                cp.connectLan(host, port)

                val pref = ServiceRegistry.getOrThrow(PreferenceProvider::class.java)
                pref.setServerHost(host)
                pref.setServerPort(port.toString())
            } catch (e: Exception) {
                _state.update { it.copy(isConnecting = false, error = "连接失败: ${e.message}") }
            }
        }
    }

    fun disconnect() {
        viewModelScope.launch {
            ServiceRegistry.getOrThrow(ConnectionProvider::class.java).disconnect()
        }
    }

    fun selectThemeColor(color: Color) {
        _state.update { it.copy(selectedThemeColor = color) }
        updatePrimaryColor(color)
        viewModelScope.launch {
            try {
                val argb = color.toArgb().toLong() and 0xFFFFFFFFL
                ServiceRegistry.getOrThrow(PreferenceProvider::class.java).setThemeColorArgb(argb)
            } catch (_: Exception) {}
        }
    }

    fun selectBackground(uri: Uri?, context: android.content.Context) {
        if (uri != null) {
            val localPath = copyBackgroundToAppStorage(context, uri)
            val localUri = if (localPath != null) Uri.parse("file://$localPath") else uri

            _state.update { it.copy(backgroundUri = localUri) }
            updateBackgroundUri(localUri)

            viewModelScope.launch {
                try {
                    ServiceRegistry.getOrThrow(PreferenceProvider::class.java)
                        .setBackgroundFilePath(localPath)
                } catch (_: Exception) {}
            }
        } else {
            _state.update { it.copy(backgroundUri = null) }
            updateBackgroundUri(null)
            viewModelScope.launch {
                try {
                    ServiceRegistry.getOrThrow(PreferenceProvider::class.java)
                        .setBackgroundFilePath(null)
                } catch (_: Exception) {}
            }
        }
    }

    fun clearError() { _state.update { it.copy(error = null) } }
}

private fun Color.toArgb(): Int {
    return android.graphics.Color.argb(
        (alpha * 255).toInt(),
        (red * 255).toInt(),
        (green * 255).toInt(),
        (blue * 255).toInt(),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    viewModel: SettingsViewModel = androidx.lifecycle.viewmodel.compose.viewModel(),
    onBack: (() -> Unit)? = null,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current

    val bgPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        uri?.let { viewModel.selectBackground(it, context) }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        if (onBack != null) {
            TopAppBar(title = { Text("设置") }, navigationIcon = {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回") }
            })
        }

        Column(
            modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            // Connection card
            AnimatedItem(0) {
                ConnectionStatusCard(
                    status = state.connectionStatus,
                    host = state.serverHost,
                    port = state.serverPort,
                    isConnecting = state.isConnecting,
                    error = state.error,
                    onConnect = { viewModel.connect() },
                    onDisconnect = { viewModel.disconnect() },
                    onHostChange = { viewModel.onHostChanged(it) },
                    onPortChange = { viewModel.onPortChanged(it) },
                    onDismissError = { viewModel.clearError() },
                )
            }

            // Theme customization
            AnimatedItem(1) {
                Card(shape = RoundedCornerShape(14.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f))) {
                    Column(Modifier.padding(16.dp)) {
                        Text("主题色", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(12.dp))
                        ThemeColorPicker(
                            selected = state.selectedThemeColor,
                            onSelect = { viewModel.selectThemeColor(it) },
                        )
                    }
                }
            }

            // Background image
            AnimatedItem(2) {
                Card(shape = RoundedCornerShape(14.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f))) {
                    Column(Modifier.padding(16.dp)) {
                        Text("自定义背景", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(8.dp))

                        Row(
                            Modifier.fillMaxWidth().height(100.dp),
                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                        ) {
                            // Default
                            Box(
                                Modifier.weight(1f).fillMaxHeight().clip(RoundedCornerShape(10.dp))
                                    .background(MaterialTheme.colorScheme.background)
                                    .clickable { viewModel.selectBackground(null, context) },
                            ) {
                                if (state.backgroundUri == null) {
                                    Box(Modifier.align(Alignment.TopEnd).padding(6.dp).size(22.dp).clip(CircleShape).background(MiyaColors.Primary), contentAlignment = Alignment.Center) {
                                        Icon(Icons.Default.Check, null, tint = Color.White, modifier = Modifier.size(14.dp))
                                    }
                                }
                                Text("默认", Modifier.align(Alignment.Center).padding(4.dp), color = Color.White.copy(alpha = 0.4f), fontSize = 13.sp)
                            }

                            // Custom
                            if (state.backgroundUri != null) {
                                Box(Modifier.weight(1f).fillMaxHeight().clip(RoundedCornerShape(10.dp)), contentAlignment = Alignment.TopEnd) {
                                    AsyncImage(
                                        model = ImageRequest.Builder(context).data(state.backgroundUri).size(256).crossfade(true).build(),
                                        contentDescription = null,
                                        modifier = Modifier.fillMaxSize(),
                                        contentScale = ContentScale.Crop,
                                    )
                                    Box(Modifier.padding(6.dp).size(22.dp).clip(CircleShape).background(MiyaColors.Primary), contentAlignment = Alignment.Center) {
                                        Icon(Icons.Default.Check, null, tint = Color.White, modifier = Modifier.size(14.dp))
                                    }
                                }
                            }

                            // Pick button
                            Box(
                                Modifier.weight(1f).fillMaxHeight().clip(RoundedCornerShape(10.dp))
                                    .background(Color.White.copy(alpha = 0.06f))
                                    .clickable { bgPicker.launch("image/*") },
                                contentAlignment = Alignment.Center,
                            ) {
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    Icon(Icons.Default.AddPhotoAlternate, null, tint = MiyaColors.Primary, modifier = Modifier.size(24.dp))
                                    Spacer(Modifier.height(4.dp))
                                    Text("选择图片", fontSize = 11.sp, color = MiyaColors.Primary)
                                }
                            }
                        }
                    }
                }
            }

            // About card
            AnimatedItem(3) {
                Card(shape = RoundedCornerShape(14.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f))) {
                    Column(Modifier.padding(20.dp)) {
                        Text("弥娅 (MIYA)", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(4.dp))
                        Text("AI 虚拟化身 · Android 客户端", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.height(12.dp))
                        AboutRow("版本", "1.0.0")
                        AboutRow("后端", "${state.serverHost}:${state.serverPort}")
                        AboutRow("架构", "Android Native + Compose M3")
                        AboutRow("通信", "REST + SSE + WebSocket")
                    }
                }
            }

            Spacer(Modifier.height(32.dp))
        }
    }
}

@Composable
private fun ThemeColorPicker(selected: Color, onSelect: (Color) -> Unit) {
    val presets = listOf(
        "粉红" to Color(0xFFFF8BA7),
        "珊瑚" to Color(0xFFFF6B6B),
        "薰紫" to Color(0xFFD4A5FF),
        "天蓝" to Color(0xFF7EC8E3),
        "薄荷" to Color(0xFF81C784),
        "橘暖" to Color(0xFFFFB74D),
    )

    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        presets.forEach { (name, color) ->
            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.weight(1f).clickable { onSelect(color) }) {
                Box(
                    Modifier.size(40.dp).clip(CircleShape).background(color)
                        .then(if (selected == color) Modifier.border(3.dp, Color.White, CircleShape) else Modifier),
                    contentAlignment = Alignment.Center,
                ) {
                    if (selected == color) {
                        Icon(Icons.Default.Check, null, tint = Color.White, modifier = Modifier.size(18.dp))
                    }
                }
                Spacer(Modifier.height(4.dp))
                Text(name, style = MaterialTheme.typography.labelSmall, color = if (selected == color) MiyaColors.Primary else MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

// ── Connection Status Card ──

@Composable
private fun ConnectionStatusCard(
    status: ConnectionStatus,
    host: String,
    port: String,
    isConnecting: Boolean,
    error: String?,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
    onHostChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onDismissError: () -> Unit,
) {
    Card(
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (status == ConnectionStatus.CONNECTED) MiyaColors.Online.copy(alpha = 0.08f) else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
        ),
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                ConnectionDot(state = when (status) {
                    ConnectionStatus.CONNECTED -> ConnectionDotState.CONNECTED
                    ConnectionStatus.CONNECTING -> ConnectionDotState.CONNECTING
                    else -> ConnectionDotState.DISCONNECTED
                })
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        when (status) {
                            ConnectionStatus.CONNECTED -> "弥娅守护进程已连接"
                            ConnectionStatus.CONNECTING -> "正在连接..."
                            ConnectionStatus.ERROR -> "连接失败"
                            else -> "未连接"
                        },
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Text("$host:$port", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }

            if (error != null) {
                Spacer(Modifier.height(8.dp))
                Surface(shape = RoundedCornerShape(8.dp), color = MiyaColors.Error.copy(alpha = 0.1f)) {
                    Row(Modifier.padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(error, style = MaterialTheme.typography.bodySmall, color = MiyaColors.Error, modifier = Modifier.weight(1f))
                        TextButton(onClick = onDismissError) { Text("关闭", style = MaterialTheme.typography.bodySmall) }
                    }
                }
            }

            if (status != ConnectionStatus.CONNECTED) {
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(value = host, onValueChange = onHostChange, label = { Text("服务器地址") }, modifier = Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(10.dp))
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(value = port, onValueChange = onPortChange, label = { Text("端口") }, modifier = Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(10.dp))
                Spacer(Modifier.height(12.dp))
                Button(onClick = onConnect, enabled = !isConnecting, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
                    if (isConnecting) { CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp, color = Color.White); Spacer(Modifier.width(8.dp)) }
                    Text(if (isConnecting) "连接中..." else "连接弥娅")
                }
            } else {
                Spacer(Modifier.height(12.dp))
                OutlinedButton(onClick = onDisconnect, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp), colors = ButtonDefaults.outlinedButtonColors(contentColor = MiyaColors.Error)) {
                    Text("断开连接")
                }
            }
        }
    }
}

@Composable
private fun AboutRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 2.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun AnimatedItem(index: Int, content: @Composable () -> Unit) {
    AnimatedVisibility(visible = true, enter = fadeIn(tween(400, delayMillis = index * 80)) + slideInVertically(tween(400, delayMillis = index * 80)) { it / 4 }) {
        content()
    }
}
