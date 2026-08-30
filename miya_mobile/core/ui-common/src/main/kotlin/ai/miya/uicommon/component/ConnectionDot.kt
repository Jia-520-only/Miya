package ai.miya.uicommon.component

import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import ai.miya.uicommon.theme.MiyaColors

enum class ConnectionDotState { CONNECTED, CONNECTING, DISCONNECTED }

@Composable
fun ConnectionDot(
    state: ConnectionDotState,
    modifier: Modifier = Modifier,
) {
    val color by animateColorAsState(
        when (state) {
            ConnectionDotState.CONNECTED -> MiyaColors.Online
            ConnectionDotState.CONNECTING -> MiyaColors.Warning
            ConnectionDotState.DISCONNECTED -> MiyaColors.Offline
        },
    )
    Box(
        modifier = modifier
            .size(10.dp)
            .clip(CircleShape)
            .background(color),
    )
}
