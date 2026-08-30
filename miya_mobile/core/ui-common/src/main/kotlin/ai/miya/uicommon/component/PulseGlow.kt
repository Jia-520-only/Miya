package ai.miya.uicommon.component

import androidx.compose.animation.core.EaseInOutCubic
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

@Composable
fun Modifier.pulseGlow(
    color: Color = Color(0xFFFF8BA7),
    radius: Dp = 48.dp,
    durationMs: Int = 2000,
): Modifier {
    val infiniteTransition = rememberInfiniteTransition()
    val alpha by infiniteTransition.animateFloat(
        0.08f, 0.25f,
        infiniteRepeatable(tween(durationMs, easing = EaseInOutCubic), RepeatMode.Reverse),
    )

    return this.drawBehind {
        val center = Offset(size.width / 2f, size.height / 2f)
        drawCircle(
            color = color.copy(alpha = alpha),
            radius = radius.toPx(),
            center = center,
        )
        drawCircle(
            color = color.copy(alpha = alpha * 0.5f),
            radius = radius.toPx() * 1.3f,
            center = center,
            style = Stroke(width = 1.5f),
        )
    }
}
