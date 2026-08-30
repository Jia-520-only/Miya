package ai.miya.feature.chat

import ai.miya.uicommon.component.MiyaChatAvatar
import ai.miya.uicommon.component.pulseGlow
import ai.miya.uicommon.theme.LocalMiyaTheme
import ai.miya.uicommon.theme.MiyaColors
import ai.miya.file.FileCategory
import ai.miya.file.FileDownloader
import ai.miya.file.FileManager
import ai.miya.domain.ServiceRegistry
import ai.miya.network.MiyaApiClient
import android.graphics.BitmapFactory
import android.net.Uri
import android.util.Base64
import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.painter.ColorPainter
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import coil.compose.AsyncImagePainter
import coil.compose.rememberAsyncImagePainter
import coil.request.ImageRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

@Composable
fun ChatScreen(
    sessionId: String = "default",
    onBack: (() -> Unit)? = null,
) {
    val viewModel = androidx.lifecycle.viewmodel.compose.viewModel<ChatViewModel>()
    LaunchedEffect(sessionId) { viewModel.selectSession(sessionId); viewModel.init() }
    ChatContent(viewModel, onBack)
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun ChatContent(viewModel: ChatViewModel, onBack: (() -> Unit)?) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()
    val focusManager = LocalFocusManager.current
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val view = LocalView.current
    val density = LocalDensity.current

    var imeHeightDp by remember { mutableStateOf(0f) }
    DisposableEffect(view) {
        val listener = android.view.ViewTreeObserver.OnGlobalLayoutListener {
            val rect = android.graphics.Rect()
            view.getWindowVisibleDisplayFrame(rect)
            val keypadHeight = (view.rootView.height - rect.bottom).coerceAtLeast(0)
            imeHeightDp = with(density) { keypadHeight.toDp().value }
        }
        view.viewTreeObserver.addOnGlobalLayoutListener(listener)
        onDispose { view.viewTreeObserver.removeOnGlobalLayoutListener(listener) }
    }
    LaunchedEffect(imeHeightDp) {
        if (imeHeightDp > 0f) { listState.animateScrollToItem(listState.layoutInfo.totalItemsCount) }
    }

    val atBottom by remember {
        derivedStateOf {
            val last = listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
            last >= listState.layoutInfo.totalItemsCount - 2
        }
    }

    LaunchedEffect(state.messages.size) { listState.animateScrollToItem(listState.layoutInfo.totalItemsCount) }
    LaunchedEffect(state.streamedText) { if (atBottom) listState.animateScrollToItem(listState.layoutInfo.totalItemsCount) }

    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { viewModel.setPendingImage(it) }
    }
    val filePicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { viewModel.setPendingFile(it) }
    }

    var contextMenuMessage by remember { mutableStateOf<ChatMessage?>(null) }

    Column(modifier = Modifier.fillMaxSize()) {

        // 返回栏
        if (onBack != null) {
            Row(
                Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal = 4.dp, vertical = 2.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack, modifier = Modifier.size(36.dp)) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回", tint = MaterialTheme.colorScheme.onSurface)
                }
                Spacer(Modifier.width(4.dp))
                Text(
                    state.sessions.find { it.id == state.currentSessionId }?.displayName ?: "聊天",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Medium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
        }

        // Session pill + picker overlay
        if (onBack == null && state.sessions.size > 1) {
            val name = state.sessions.find { it.id == state.currentSessionId }?.displayName ?: "聊天"
            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.85f),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth().statusBarsPadding().padding(top = 8.dp, start = 14.dp),
            ) {
                Row(
                    Modifier.clickable { viewModel.toggleSessionPicker() }.padding(horizontal = 14.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(name, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.width(4.dp))
                    Icon(Icons.Default.ExpandMore, null, tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(14.dp))
                }
            }
        }
        AnimatedVisibility(
            visible = state.showSessionPicker,
            enter = fadeIn(tween(200)) + scaleIn(tween(200)),
            exit = fadeOut(tween(150)) + scaleOut(tween(150)),
            modifier = Modifier.fillMaxWidth().statusBarsPadding().padding(top = 50.dp, start = 14.dp),
        ) {
            Surface(color = MaterialTheme.colorScheme.surfaceVariant, shape = RoundedCornerShape(14.dp), tonalElevation = 8.dp, modifier = Modifier.widthIn(max = 280.dp)) {
                Column(Modifier.padding(12.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text("会话", style = MaterialTheme.typography.titleSmall)
                        IconButton(onClick = { viewModel.newSession() }, modifier = Modifier.size(28.dp)) {
                            Icon(Icons.Default.Add, "新建", tint = MiyaColors.Primary, modifier = Modifier.size(16.dp))
                        }
                    }
                    Spacer(Modifier.height(4.dp))
                    state.sessions.take(5).forEach { s ->
                        Row(
                            Modifier.fillMaxWidth().clip(RoundedCornerShape(8.dp)).clickable { viewModel.selectSession(s.id) }
                                .background(if (s.id == state.currentSessionId) MiyaColors.Primary.copy(alpha = 0.1f) else Color.Transparent)
                                .padding(horizontal = 10.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(s.displayName ?: s.name ?: s.id, style = MaterialTheme.typography.bodyMedium, maxLines = 1)
                                if (s.messageCount != null) Text("${s.messageCount}条", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            if (s.id == state.currentSessionId) Icon(Icons.Default.Check, null, tint = MiyaColors.Primary, modifier = Modifier.size(14.dp))
                            if (s.id != "default") {
                                IconButton(onClick = { viewModel.deleteSession(s.id) }, modifier = Modifier.size(24.dp)) {
                                    Icon(Icons.Default.Close, "删除", modifier = Modifier.size(12.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                        }
                    }
                }
            }
        }

        if (state.downloadTasks.isNotEmpty()) {
            DownloadProgressBar(state.downloadTasks)
        }

        Column(modifier = Modifier.weight(1f).padding(bottom = imeHeightDp.dp)) {
            LazyColumn(
                state = listState,
                modifier = Modifier.weight(1f).padding(horizontal = 8.dp),
                verticalArrangement = Arrangement.spacedBy(2.dp),
                contentPadding = PaddingValues(top = 8.dp, bottom = 8.dp),
            ) {
                if (state.messages.isEmpty() && !state.isStreaming) {
                    item(key = "empty") {
                        Box(Modifier.fillMaxWidth().heightIn(min = 280.dp), contentAlignment = Alignment.Center) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                MiyaChatAvatar(size = 64.dp, modifier = Modifier.pulseGlow(MiyaColors.Primary.copy(alpha = 0.3f), radius = 40.dp, durationMs = 2200))
                                Spacer(Modifier.height(16.dp))
                                Text("我是弥娅，你的 AI 虚拟化身", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurface)
                                Spacer(Modifier.height(6.dp))
                                Text("给我发张图片，或者和我说说话吧", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
                itemsIndexed(state.messages, key = { _, m -> m.id }) { _, message ->
                    ChatBubble(
                        message = message,
                        onLongPress = { contextMenuMessage = message },
                        onQuote = { viewModel.setQuotedMessage(message) },
                        onPoke = { viewModel.sendPoke() },
                    )
                }
                if (state.isStreaming && state.streamedText.isNotEmpty()) {
                    item(key = "streaming") { StreamingBubble(text = state.streamedText) }
                } else if (state.isStreaming) {
                    item(key = "typing") { TypingBubble() }
                }
            }

            // Quote bar
            AnimatedVisibility(
                visible = state.quotedMessage != null,
                enter = expandVertically(tween(200)) + fadeIn(tween(200)),
                exit = shrinkVertically(tween(150)) + fadeOut(tween(150)),
            ) {
                state.quotedMessage?.let { quoted ->
                    Surface(
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 2.dp),
                        shape = RoundedCornerShape(8.dp),
                    ) {
                        Row(
                            Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Box(Modifier.width(3.dp).height(32.dp).clip(RoundedCornerShape(2.dp)).background(MiyaColors.Primary))
                            Spacer(Modifier.width(8.dp))
                            Column(Modifier.weight(1f)) {
                                Text(if (quoted.isUser) "你" else "弥娅", style = MaterialTheme.typography.labelSmall, color = MiyaColors.Primary, fontWeight = FontWeight.Bold)
                                Text(quoted.contentPreview(60), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            }
                            IconButton(onClick = { viewModel.clearQuote() }, modifier = Modifier.size(28.dp)) {
                                Icon(Icons.Default.Close, "取消引用", tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(16.dp))
                            }
                        }
                    }
                }
            }

            // Image caption editor
            AnimatedVisibility(
                visible = state.pendingImageUri != null,
                enter = expandVertically(tween(200)) + fadeIn(tween(200)),
                exit = shrinkVertically(tween(150)) + fadeOut(tween(150)),
            ) {
                Surface(color = MaterialTheme.colorScheme.surfaceVariant, modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 2.dp), shape = RoundedCornerShape(10.dp)) {
                    Row(Modifier.padding(horizontal = 10.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Image, null, tint = MiyaColors.Primary, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Box(Modifier.weight(1f).clip(RoundedCornerShape(8.dp)).background(Color.White.copy(alpha = 0.06f)).padding(horizontal = 10.dp, vertical = 8.dp)) {
                            BasicTextField(
                                value = state.imageCaption,
                                onValueChange = { viewModel.onImageCaptionChange(it) },
                                textStyle = TextStyle(color = Color.White, fontSize = 14.sp),
                                cursorBrush = SolidColor(MiyaColors.Primary),
                                modifier = Modifier.fillMaxWidth(),
                                decorationBox = { inner ->
                                    if (state.imageCaption.isEmpty()) Text("添加图片描述…", color = Color.White.copy(alpha = 0.4f), fontSize = 14.sp)
                                    inner()
                                },
                            )
                        }
                        Spacer(Modifier.width(6.dp))
                        IconButton(onClick = { viewModel.confirmImageSend(context) }, modifier = Modifier.size(36.dp).clip(CircleShape).background(MiyaColors.Primary)) {
                            Icon(Icons.AutoMirrored.Filled.Send, "发送", tint = Color.White, modifier = Modifier.size(16.dp))
                        }
                        IconButton(onClick = { viewModel.cancelImageCaption() }, modifier = Modifier.size(28.dp)) {
                            Icon(Icons.Default.Close, "取消", tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(16.dp))
                        }
                    }
                }
            }

            // File caption editor
            AnimatedVisibility(
                visible = state.pendingFileUri != null,
                enter = expandVertically(tween(200)) + fadeIn(tween(200)),
                exit = shrinkVertically(tween(150)) + fadeOut(tween(150)),
            ) {
                Surface(color = MaterialTheme.colorScheme.surfaceVariant, modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 2.dp), shape = RoundedCornerShape(10.dp)) {
                    Row(Modifier.padding(horizontal = 10.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Description, null, tint = MiyaColors.Secondary, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Box(Modifier.weight(1f).clip(RoundedCornerShape(8.dp)).background(Color.White.copy(alpha = 0.06f)).padding(horizontal = 10.dp, vertical = 8.dp)) {
                            BasicTextField(
                                value = state.fileCaption,
                                onValueChange = { viewModel.onFileCaptionChange(it) },
                                textStyle = TextStyle(color = Color.White, fontSize = 14.sp),
                                cursorBrush = SolidColor(MiyaColors.Secondary),
                                modifier = Modifier.fillMaxWidth(),
                                decorationBox = { inner ->
                                    if (state.fileCaption.isEmpty()) Text("添加文件描述…", color = Color.White.copy(alpha = 0.4f), fontSize = 14.sp)
                                    inner()
                                },
                            )
                        }
                        Spacer(Modifier.width(6.dp))
                        IconButton(onClick = { viewModel.confirmFileSend(context) }, modifier = Modifier.size(36.dp).clip(CircleShape).background(MiyaColors.Secondary)) {
                            Icon(Icons.AutoMirrored.Filled.Send, "发送", tint = Color.White, modifier = Modifier.size(16.dp))
                        }
                        IconButton(onClick = { viewModel.cancelFileCaption() }, modifier = Modifier.size(28.dp)) {
                            Icon(Icons.Default.Close, "取消", tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(16.dp))
                        }
                    }
                }
            }

            // Error bar
            AnimatedVisibility(visible = state.error != null, enter = slideInVertically { it } + fadeIn(), exit = slideOutVertically { it } + fadeOut()) {
                Surface(color = MiyaColors.Error.copy(alpha = 0.1f), modifier = Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Error, null, tint = MiyaColors.Error, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(8.dp))
                        Text(state.error ?: "", style = MaterialTheme.typography.bodySmall, color = MiyaColors.Error, modifier = Modifier.weight(1f))
                        IconButton(onClick = { viewModel.clearError() }, modifier = Modifier.size(24.dp)) {
                            Icon(Icons.Default.Close, null, tint = MiyaColors.Error, modifier = Modifier.size(16.dp))
                        }
                    }
                }
            }

            // Attachment picker
            AnimatedVisibility(visible = state.showAttachmentPicker, enter = fadeIn(tween(200)) + slideInVertically(tween(250)) { it }, exit = fadeOut(tween(150)) + slideOutVertically(tween(200)) { it }) {
                Surface(color = MaterialTheme.colorScheme.surfaceVariant, tonalElevation = 4.dp, modifier = Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(horizontal = 16.dp, vertical = 12.dp), horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.clickable { imagePicker.launch("image/*"); viewModel.toggleAttachmentPicker() }) {
                            Box(Modifier.size(52.dp).clip(RoundedCornerShape(14.dp)).background(MiyaColors.Primary.copy(alpha = 0.12f)), contentAlignment = Alignment.Center) {
                                Icon(Icons.Default.Image, null, tint = MiyaColors.Primary, modifier = Modifier.size(26.dp))
                            }
                            Spacer(Modifier.height(4.dp))
                            Text("图片", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.clickable { filePicker.launch("*/*"); viewModel.toggleAttachmentPicker() }) {
                            Box(Modifier.size(52.dp).clip(RoundedCornerShape(14.dp)).background(MiyaColors.Secondary.copy(alpha = 0.12f)), contentAlignment = Alignment.Center) {
                                Icon(Icons.Default.Description, null, tint = MiyaColors.Secondary, modifier = Modifier.size(26.dp))
                            }
                            Spacer(Modifier.height(4.dp))
                            Text("文件", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }

            // Emoji picker (只展示内置 Unicode 表情)
            AnimatedVisibility(visible = state.showStickerPicker, enter = fadeIn(tween(200)) + expandVertically(tween(250)), exit = fadeOut(tween(150)) + shrinkVertically(tween(200))) {
                Surface(color = MaterialTheme.colorScheme.surfaceVariant, modifier = Modifier.fillMaxWidth().heightIn(max = 220.dp)) {
                    LazyVerticalGrid(
                        columns = GridCells.Fixed(6),
                        modifier = Modifier.padding(8.dp),
                        horizontalArrangement = Arrangement.spacedBy(4.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        items(COMMON_STICKERS) { (emoji, _) ->
                            Text(
                                text = emoji, fontSize = 28.sp,
                                modifier = Modifier.size(44.dp).clip(RoundedCornerShape(8.dp)).clickable { viewModel.sendSticker(emoji) }.padding(4.dp),
                            )
                        }
                    }
                }
            }

            // Input bar
            ChatInputBar(
                text = state.inputText,
                onTextChange = { viewModel.onInputChange(it) },
                onSend = { focusManager.clearFocus(); viewModel.sendMessage() },
                onStop = { viewModel.stopStreaming() },
                isStreaming = state.isStreaming,
                onAttachment = { viewModel.toggleAttachmentPicker() },
                onToggleSticker = { viewModel.toggleStickerPicker() },
            )
        }
    }

    // Context menu
    contextMenuMessage?.let { message ->
        AlertDialog(
            onDismissRequest = { contextMenuMessage = null },
            title = null,
            text = {
                Column {
                    if (!message.hasImage && !message.hasFile) {
                        TextButton(onClick = {
                            clipboard.setText(AnnotatedString(message.content))
                            contextMenuMessage = null
                        }, modifier = Modifier.fillMaxWidth()) {
                            Icon(Icons.Default.ContentCopy, null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(12.dp))
                            Text("复制文本")
                            Spacer(Modifier.weight(1f))
                        }
                    }
                    TextButton(onClick = {
                        viewModel.setQuotedMessage(message)
                        contextMenuMessage = null
                    }, modifier = Modifier.fillMaxWidth()) {
                        Icon(Icons.Default.FormatQuote, null, modifier = Modifier.size(18.dp), tint = MiyaColors.Primary)
                        Spacer(Modifier.width(12.dp))
                        Text("引用回复", color = MiyaColors.Primary)
                        Spacer(Modifier.weight(1f))
                    }
                    TextButton(onClick = {
                        viewModel.deleteMessage(message.id)
                        contextMenuMessage = null
                    }, modifier = Modifier.fillMaxWidth()) {
                        Icon(Icons.Default.Delete, null, modifier = Modifier.size(18.dp), tint = MiyaColors.Error)
                        Spacer(Modifier.width(12.dp))
                        Text("删除消息", color = MiyaColors.Error)
                        Spacer(Modifier.weight(1f))
                    }
                }
            },
            confirmButton = {},
            dismissButton = {},
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
            shape = RoundedCornerShape(16.dp),
        )
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun ChatBubble(message: ChatMessage, onLongPress: () -> Unit, onQuote: () -> Unit, onPoke: () -> Unit) {
    val isUser = message.isUser

    Row(
        Modifier.fillMaxWidth().combinedClickable(
            onClick = {},
            onLongClick = onLongPress,
        ),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        if (!isUser) {
            MiyaChatAvatar(
                modifier = Modifier
                    .padding(top = 4.dp, end = 8.dp)
                    .pointerInput(Unit) { detectTapGestures(onDoubleTap = { _ -> onPoke() }) },
                size = 32.dp,
            )
        }

        Column(horizontalAlignment = if (isUser) Alignment.End else Alignment.Start) {
            Surface(
                shape = RoundedCornerShape(
                    topStart = 18.dp, topEnd = 18.dp,
                    bottomStart = if (isUser) 18.dp else 6.dp,
                    bottomEnd = if (isUser) 6.dp else 18.dp,
                ),
                color = if (isUser) MiyaColors.Primary.copy(alpha = 0.85f) else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.92f),
                tonalElevation = 0.dp,
                shadowElevation = 0.dp,
                modifier = Modifier.widthIn(max = 280.dp),
            ) {
                Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
                    if (message.hasQuote) {
                        Surface(
                            color = Color.White.copy(alpha = 0.06f),
                            shape = RoundedCornerShape(6.dp),
                            modifier = Modifier.fillMaxWidth().padding(bottom = 4.dp),
                        ) {
                            Row(Modifier.padding(4.dp)) {
                                Box(Modifier.width(2.dp).height(28.dp).clip(RoundedCornerShape(1.dp)).background(MiyaColors.Primary.copy(alpha = 0.5f)))
                                Spacer(Modifier.width(6.dp))
                                Text(message.quotedContent ?: "", style = MaterialTheme.typography.labelSmall, color = Color.White.copy(alpha = 0.5f), maxLines = 2, overflow = TextOverflow.Ellipsis)
                            }
                        }
                    }
                    if (message.hasImage) {
                        ImageAttachmentCard(message.imageSrc)
                        Spacer(Modifier.height(4.dp))
                    }
                    if (message.hasFile) {
                        FileAttachmentCard(message.fileName, message.fileSize, message.fileMimeType, message.fileLocalPath, message.pendingFileUrl, message.id)
                        Spacer(Modifier.height(4.dp))
                    }
                    if (message.content.isNotEmpty()) {
                        if (!isUser) {
                            MarkdownText(message.content)
                        } else {
                            Text(
                                message.content,
                                style = MaterialTheme.typography.bodyLarge.copy(lineHeight = 22.sp, letterSpacing = 0.2.sp),
                                color = Color.White,
                            )
                        }
                    }
                }
            }

            Spacer(Modifier.height(2.dp))
        }
    }
}

@Composable
private fun ImageAttachmentCard(src: String?) {
    if (src == null) return
    val isDataUri = src.startsWith("data:")
    val isLocalFile = src.startsWith("/") || src.startsWith("file://")
    var showFullScreen by remember { mutableStateOf(false) }
    var imageBitmap by remember { mutableStateOf<androidx.compose.ui.graphics.ImageBitmap?>(null) }
    var bitmapWidth by remember { mutableIntStateOf(0) }
    var bitmapHeight by remember { mutableIntStateOf(0) }
    var loadFailed by remember { mutableStateOf(false) }

    if (isDataUri) {
        LaunchedEffect(src) {
            loadFailed = false
            imageBitmap = null
            bitmapWidth = 0
            bitmapHeight = 0
            withContext(Dispatchers.IO) {
                try {
                    val b64 = src.substringAfter("base64,").trim()
                    val bytes = Base64.decode(b64, Base64.DEFAULT)
                    val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                    if (bmp != null) {
                        bitmapWidth = bmp.width
                        bitmapHeight = bmp.height
                        imageBitmap = bmp.asImageBitmap()
                    } else {
                        loadFailed = true
                    }
                } catch (_: Exception) {
                    loadFailed = true
                }
            }
        }
    }

    Surface(
        shape = RoundedCornerShape(10.dp),
        color = Color.White.copy(alpha = 0.08f),
        modifier = Modifier.fillMaxWidth().clickable { showFullScreen = true },
    ) {
        if (isDataUri) {
            when {
                imageBitmap != null && bitmapWidth > 0 -> {
                    BoxWithConstraints(Modifier.fillMaxWidth()) {
                        val ratio = bitmapHeight.toFloat() / bitmapWidth.toFloat()
                        val displayHeight = minOf(maxWidth * ratio, 400.dp)
                        Image(
                            bitmap = imageBitmap!!,
                            contentDescription = "图片",
                            modifier = Modifier.fillMaxWidth().height(displayHeight).clip(RoundedCornerShape(10.dp)),
                            contentScale = ContentScale.FillBounds,
                        )
                        Box(
                            Modifier.align(Alignment.BottomStart).fillMaxWidth()
                                .background(Color.Black.copy(alpha = 0.35f))
                                .padding(horizontal = 8.dp, vertical = 3.dp),
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.Image, null, tint = Color.White, modifier = Modifier.size(12.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("图片", style = MaterialTheme.typography.labelSmall, color = Color.White)
                            }
                        }
                    }
                }
                loadFailed -> {
                    Box(Modifier.fillMaxWidth().height(80.dp), contentAlignment = Alignment.Center) {
                        Text("图片加载失败", fontSize = 12.sp, color = Color.White.copy(alpha = 0.4f))
                    }
                }
                else -> {
                    Box(Modifier.fillMaxWidth().height(100.dp), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(modifier = Modifier.size(22.dp), strokeWidth = 2.dp, color = MiyaColors.Primary)
                    }
                }
            }
        } else {
            val reqPainter = rememberAsyncImagePainter(
                model = ImageRequest.Builder(LocalContext.current).data(src).crossfade(true).build(),
                placeholder = ColorPainter(Color.White.copy(alpha = 0.05f)),
                error = ColorPainter(Color.White.copy(alpha = 0.05f)),
            )
            val urlW = remember { mutableIntStateOf(0) }
            val urlH = remember { mutableIntStateOf(0) }
            LaunchedEffect(reqPainter.state) {
                if (reqPainter.state is AsyncImagePainter.State.Success) {
                    val d = (reqPainter.state as AsyncImagePainter.State.Success).result.drawable
                    urlW.intValue = d.intrinsicWidth
                    urlH.intValue = d.intrinsicHeight
                }
            }
            if (urlW.intValue > 0) {
                BoxWithConstraints(Modifier.fillMaxWidth()) {
                    val ratio = urlH.intValue.toFloat() / urlW.intValue.toFloat()
                    val displayHeight = minOf(maxWidth * ratio, 400.dp)
                    Image(
                        painter = reqPainter,
                        contentDescription = "图片",
                        modifier = Modifier.fillMaxWidth().height(displayHeight).clip(RoundedCornerShape(10.dp)),
                        contentScale = ContentScale.FillBounds,
                    )
                    Box(
                        Modifier.align(Alignment.BottomStart).fillMaxWidth()
                            .background(Color.Black.copy(alpha = 0.35f))
                            .padding(horizontal = 8.dp, vertical = 3.dp),
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Image, null, tint = Color.White, modifier = Modifier.size(12.dp))
                            Spacer(Modifier.width(4.dp))
                            Text("图片", style = MaterialTheme.typography.labelSmall, color = Color.White)
                        }
                    }
                }
            } else {
                Box(Modifier.fillMaxWidth().heightIn(max = 400.dp)) {
                    Image(
                        painter = reqPainter,
                        contentDescription = "图片",
                        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)),
                        contentScale = ContentScale.FillWidth,
                    )
                    Box(
                        Modifier.align(Alignment.BottomStart).fillMaxWidth()
                            .background(Color.Black.copy(alpha = 0.35f))
                            .padding(horizontal = 8.dp, vertical = 3.dp),
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Image, null, tint = Color.White, modifier = Modifier.size(12.dp))
                            Spacer(Modifier.width(4.dp))
                            Text("图片", style = MaterialTheme.typography.labelSmall, color = Color.White)
                        }
                    }
                }
            }
        }
    }

    if (showFullScreen) {
        Dialog(
            onDismissRequest = { showFullScreen = false },
            properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false),
        ) {
            Box(
                Modifier.fillMaxSize().background(Color.Black).clickable { showFullScreen = false },
                contentAlignment = Alignment.Center,
            ) {
                if (imageBitmap != null) {
                    Image(
                        bitmap = imageBitmap!!,
                        contentDescription = "全屏图片",
                        modifier = Modifier.fillMaxSize().padding(16.dp),
                        contentScale = ContentScale.Fit,
                    )
                } else {
                    AsyncImage(
                        model = ImageRequest.Builder(LocalContext.current).data(src).crossfade(true).build(),
                        contentDescription = "全屏图片",
                        modifier = Modifier.fillMaxSize().padding(16.dp),
                        contentScale = ContentScale.Fit,
                        placeholder = ColorPainter(Color.White.copy(alpha = 0.05f)),
                    )
                }
                IconButton(
                    onClick = { showFullScreen = false },
                    modifier = Modifier.align(Alignment.TopEnd).statusBarsPadding().padding(12.dp).size(40.dp).clip(CircleShape).background(Color.Black.copy(alpha = 0.5f)),
                ) {
                    Icon(Icons.Default.Close, "关闭", tint = Color.White, modifier = Modifier.size(20.dp))
                }
            }
        }
    }
}

@Composable
private fun FileAttachmentCard(
    name: String?,
    size: Long?,
    mimeType: String?,
    localPath: String? = null,
    pendingFileUrl: String? = null,
    messageId: String? = null,
) {
    val context = LocalContext.current
    val downloader = remember { ServiceRegistry.getOrThrow(FileDownloader::class.java) }
    val realName = name ?: "file"
    val cat = when {
        mimeType?.startsWith("image/") == true -> FileCategory.IMAGES
        mimeType?.startsWith("audio/") == true -> FileCategory.AUDIO
        else -> FileCategory.DOWNLOADS
    }

    Surface(
        shape = RoundedCornerShape(10.dp),
        color = Color.White.copy(alpha = 0.06f),
        modifier = Modifier.fillMaxWidth().then(
            when {
                localPath != null -> Modifier.clickable { openFile(context, localPath, mimeType) }
                pendingFileUrl != null -> Modifier.clickable {
                    downloader.download(pendingFileUrl, realName, cat, null, mimeType ?: "application/octet-stream", messageId)
                }
                else -> Modifier
            }
        ),
    ) {
        Row(
            Modifier.padding(horizontal = 10.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                Modifier.size(38.dp).clip(RoundedCornerShape(8.dp)).background(MiyaColors.Secondary.copy(alpha = 0.15f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    when {
                        mimeType?.startsWith("image/") == true -> Icons.Default.Image
                        mimeType?.startsWith("audio/") == true -> Icons.Default.Audiotrack
                        mimeType?.startsWith("video/") == true -> Icons.Default.Videocam
                        else -> Icons.Default.Description
                    },
                    null,
                    tint = MiyaColors.Secondary,
                    modifier = Modifier.size(20.dp),
                )
            }
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(name ?: "文件", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (size != null && size > 0) {
                    Text(formatFileSize(size), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

private fun openFile(context: android.content.Context, localPath: String, mimeType: String?) {
    try {
        val uri = androidx.core.content.FileProvider.getUriForFile(
            context, "${context.packageName}.fileprovider",
            java.io.File(localPath),
        )
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, mimeType ?: "*/*")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(intent)
    } catch (_: Exception) {
        try {
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(android.net.Uri.parse("file://$localPath"), mimeType ?: "*/*")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            context.startActivity(intent)
        } catch (_: Exception) {}
    }
}

@Composable
private fun StreamingBubble(text: String) {
    val cursor by rememberInfiniteTransition().animateFloat(0f, 1f, infiniteRepeatable(tween(500), RepeatMode.Reverse))

    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        MiyaChatAvatar(
            modifier = Modifier.padding(top = 4.dp, end = 8.dp).pulseGlow(MiyaColors.Primary.copy(alpha = 0.5f), radius = 30.dp, durationMs = 1800),
            size = 32.dp,
        )

        Surface(
            shape = RoundedCornerShape(18.dp, 18.dp, 18.dp, 6.dp),
            color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.92f),
            modifier = Modifier.widthIn(max = 280.dp),
        ) {
            Box(Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
                Text(
                    buildAnnotatedString {
                        MarkdownParser.parseToAnnotated(text, this)
                        withStyle(SpanStyle(color = MiyaColors.Primary.copy(alpha = cursor))) { append("▌") }
                    },
                    style = MaterialTheme.typography.bodyLarge.copy(lineHeight = 22.sp),
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
        }
    }
}

@Composable
private fun TypingBubble() {
    val transition = rememberInfiniteTransition()
    val alphas = listOf(0, 120, 240).map { delay ->
        transition.animateFloat(0.4f, 1f, infiniteRepeatable(tween(400, delayMillis = delay), RepeatMode.Reverse)).value
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        MiyaChatAvatar(
            modifier = Modifier.padding(top = 4.dp, end = 8.dp).pulseGlow(MiyaColors.Primary.copy(alpha = 0.4f), radius = 28.dp, durationMs = 1500),
            size = 32.dp,
        )
        Surface(shape = RoundedCornerShape(18.dp, 18.dp, 18.dp, 6.dp), color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.92f)) {
            Row(Modifier.padding(horizontal = 14.dp, vertical = 12.dp), horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                alphas.forEach { alpha ->
                    Box(Modifier.size(7.dp).clip(CircleShape).background(MiyaColors.Primary.copy(alpha = alpha)))
                }
            }
        }
    }
}

@Composable
private fun ChatInputBar(
    text: String,
    onTextChange: (String) -> Unit,
    onSend: () -> Unit,
    onStop: () -> Unit,
    isStreaming: Boolean,
    onAttachment: () -> Unit,
    onToggleSticker: () -> Unit,
) {
    val hasContent = text.isNotBlank()
    Surface(color = MaterialTheme.colorScheme.background.copy(alpha = 0.95f), tonalElevation = 0.dp) {
        Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 10.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onAttachment, modifier = Modifier.size(36.dp)) {
                Icon(Icons.Default.Add, "附件", tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(22.dp))
            }
            IconButton(onClick = onToggleSticker, modifier = Modifier.size(36.dp)) {
                Icon(Icons.Default.EmojiEmotions, "表情", tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(22.dp))
            }
            Box(Modifier.weight(1f).clip(RoundedCornerShape(21.dp)).background(Color.White.copy(alpha = 0.06f)).padding(horizontal = 14.dp, vertical = 10.dp)) {
                BasicTextField(
                    value = text, onValueChange = onTextChange, maxLines = 4,
                    textStyle = TextStyle(color = MaterialTheme.colorScheme.onSurface, fontSize = 15.sp, lineHeight = 20.sp),
                    cursorBrush = SolidColor(MiyaColors.Primary),
                    modifier = Modifier.fillMaxWidth(),
                    decorationBox = { inner ->
                        if (text.isEmpty()) Text("和弥娅说些什么...", style = TextStyle(color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f), fontSize = 15.sp))
                        inner()
                    },
                )
            }
            Spacer(Modifier.width(8.dp))
            if (isStreaming) {
                IconButton(onClick = onStop, modifier = Modifier.size(40.dp).clip(CircleShape).background(MiyaColors.Error)) {
                    Icon(Icons.Default.Stop, "停止", tint = Color.White, modifier = Modifier.size(20.dp))
                }
            } else {
                IconButton(onClick = onSend, enabled = hasContent, modifier = Modifier.size(40.dp).clip(CircleShape).background(if (hasContent) MiyaColors.Primary else Color.White.copy(alpha = 0.06f))) {
                    Icon(Icons.AutoMirrored.Filled.Send, "发送", tint = if (hasContent) Color.White else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f), modifier = Modifier.size(18.dp))
                }
            }
        }
    }
}

@Composable
private fun MarkdownText(text: String) {
    val annotated = remember(text) {
        buildAnnotatedString { MarkdownParser.parseToAnnotated(text, this) }
    }
    Text(
        annotated,
        style = MaterialTheme.typography.bodyLarge.copy(lineHeight = 22.sp, letterSpacing = 0.2.sp),
        color = MaterialTheme.colorScheme.onSurface,
    )
}

object MarkdownParser {
    fun parseToAnnotated(text: String, builder: androidx.compose.ui.text.AnnotatedString.Builder) {
        val codeBlockPattern = Regex("```(?:\\w+\\n)?([\\s\\S]*?)```")
        val boldPattern = Regex("\\*\\*(.+?)\\*\\*")
        val italicPattern = Regex("\\*(.+?)\\*")
        val inlineCodePattern = Regex("`(.+?)`")

        var remaining = text

        while (remaining.isNotEmpty()) {
            val codeBlock = codeBlockPattern.find(remaining)
            val bold = boldPattern.find(remaining)
            val italic = italicPattern.find(remaining)
            val inlineCode = inlineCodePattern.find(remaining)

            val matches = listOfNotNull(
                codeBlock?.let { "code" to it },
                bold?.let { "bold" to it },
                italic?.let { "italic" to it },
                inlineCode?.let { "icode" to it },
            ).sortedBy { it.second.range.first }

            if (matches.isEmpty()) {
                builder.append(remaining)
                break
            }

            val (type, match) = matches.first()
            if (match.range.first > 0) {
                builder.append(remaining.substring(0, match.range.first))
            }

            when (type) {
                "code" -> {
                    val code = match.groupValues[1].trim()
                    builder.withStyle(SpanStyle(fontFamily = FontFamily.Monospace, fontSize = 13.sp, background = Color.White.copy(alpha = 0.06f))) { append("\n$code\n") }
                }
                "icode" -> {
                    val code = match.groupValues[1]
                    builder.withStyle(SpanStyle(fontFamily = FontFamily.Monospace, fontSize = 13.sp, background = Color.White.copy(alpha = 0.08f))) { append(code) }
                }
                "bold" -> {
                    builder.withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(match.groupValues[1]) }
                }
                "italic" -> {
                    builder.withStyle(SpanStyle(fontStyle = FontStyle.Italic)) { append(match.groupValues[1]) }
                }
            }

            remaining = remaining.substring(match.range.last + 1)
        }
    }
}

@Composable
private fun DownloadProgressBar(tasks: List<FileDownloader.DownloadTask>) {
    Column(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 4.dp),
    ) {
        tasks.filter { it.status.value != FileDownloader.DownloadStatus.COMPLETED }.forEach { task ->
            val progress by task.progress.collectAsStateWithLifecycle()
            val status by task.status.collectAsStateWithLifecycle()
            Surface(
                shape = RoundedCornerShape(10.dp),
                color = MiyaColors.Secondary.copy(alpha = 0.1f),
                modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
            ) {
                Row(
                    Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        Icons.Default.CloudDownload,
                        null,
                        tint = MiyaColors.Secondary,
                        modifier = Modifier.size(18.dp),
                    )
                    Spacer(Modifier.width(8.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            task.fileName,
                            style = MaterialTheme.typography.bodySmall,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        if (status == FileDownloader.DownloadStatus.DOWNLOADING) {
                            LinearProgressIndicator(
                                progress = { progress },
                                modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                                color = MiyaColors.Primary,
                                trackColor = MiyaColors.Primary.copy(alpha = 0.1f),
                            )
                        } else if (status == FileDownloader.DownloadStatus.FAILED) {
                            Text("下载失败", style = MaterialTheme.typography.labelSmall, color = MiyaColors.Error)
                        }
                    }
                }
            }
        }
    }
}

