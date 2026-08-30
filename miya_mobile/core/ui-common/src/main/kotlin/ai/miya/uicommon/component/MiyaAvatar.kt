package ai.miya.uicommon.component

import ai.miya.uicommon.R
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import coil.request.ImageRequest

@Composable
fun MiyaCircleAvatar(
    imageUrl: String? = null,
    modifier: Modifier = Modifier,
    size: Dp = 48.dp,
    placeholder: @Composable () -> Unit = {
        val context = LocalContext.current
        Box(
            modifier = Modifier.size(size).clip(CircleShape).background(Color(0xFFFF8BA7).copy(alpha = 0.15f)),
            contentAlignment = Alignment.Center,
        ) {
            AsyncImage(
                model = ImageRequest.Builder(context).data(R.drawable.miya_avatar).size(128).crossfade(true).build(),
                contentDescription = null,
                modifier = Modifier.fillMaxSize().clip(CircleShape),
                contentScale = ContentScale.Crop,
            )
        }
    },
) {
    // Use miya_avatar.png by default, or provided URL
    if (imageUrl != null && imageUrl.isNotEmpty()) {
        AsyncImage(
            model = ImageRequest.Builder(LocalContext.current).data(imageUrl).size(128).crossfade(true).build(),
            contentDescription = null,
            modifier = modifier.size(size).clip(CircleShape),
            contentScale = ContentScale.Crop,
        )
    } else {
        placeholder()
    }
}

// Convenience: avatar for chat bubble use
@Composable
fun MiyaChatAvatar(modifier: Modifier = Modifier, size: Dp = 32.dp) {
    val context = LocalContext.current
    AsyncImage(
        model = ImageRequest.Builder(context).data(R.drawable.miya_avatar).size(64).crossfade(true).build(),
        contentDescription = null,
        modifier = modifier.size(size).clip(CircleShape),
        contentScale = ContentScale.Crop,
    )
}
