package ai.miya.uicommon.component

import android.net.Uri
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import coil.compose.AsyncImage
import coil.request.ImageRequest
import kotlin.math.cos
import kotlin.math.sin

@Composable
fun MiyaBackground(
    modifier: Modifier = Modifier,
    baseColor: Color = Color(0xFF1A111A),
    accentColor: Color = Color(0xFFFF8BA7),
    backgroundUri: Uri? = null,
) {
    val context = LocalContext.current

    Box(modifier = modifier.fillMaxSize()) {
        if (backgroundUri != null) {
            AsyncImage(
                model = ImageRequest.Builder(context).data(backgroundUri).crossfade(true).build(),
                contentDescription = null,
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Crop,
            )
            // Glass overlay on top of custom image
            Canvas(modifier = Modifier.fillMaxSize()) {
                drawRect(Color(0x4D1A111A))
            }
        }

        // Animated orbs
        AnimatedOrbContent(
            modifier = Modifier.fillMaxSize(),
            baseColor = if (backgroundUri != null) Color.Transparent else baseColor,
            accentColor = accentColor,
        )
    }
}

@Composable
fun AnimatedOrbBackground(
    modifier: Modifier = Modifier,
    baseColor: Color = Color(0xFF1A111A),
    accentColor: Color = Color(0xFFFF8BA7),
) {
    AnimatedOrbContent(modifier = modifier, baseColor = baseColor, accentColor = accentColor)
}

@Composable
private fun AnimatedOrbContent(
    modifier: Modifier,
    baseColor: Color,
    accentColor: Color,
) {
    val infiniteTransition = rememberInfiniteTransition()

    val orb1Phase by infiniteTransition.animateFloat(0f, 1f, infiniteRepeatable(tween(15000, easing = LinearEasing), RepeatMode.Restart))
    val orb2Phase by infiniteTransition.animateFloat(0f, 1f, infiniteRepeatable(tween(18000, easing = LinearEasing), RepeatMode.Restart))

    Canvas(modifier = modifier.fillMaxSize()) {
        if (baseColor != Color.Transparent) {
            drawRect(
                brush = Brush.verticalGradient(
                    colors = listOf(baseColor, Color(0xFF1A111A), accentColor.copy(alpha = 0.06f)),
                ),
            )
        }

        val ox1 = size.width * (0.45f + 0.12f * cos(orb1Phase * 2 * Math.PI).toFloat())
        val oy1 = size.height * (0.35f + 0.08f * sin(orb1Phase * 2 * Math.PI).toFloat())
        drawOrb(Offset(ox1, oy1), size.width * 0.42f, accentColor.copy(alpha = 0.08f))

        val ox2 = size.width * (0.55f + 0.15f * sin(orb2Phase * 2 * Math.PI).toFloat())
        val oy2 = size.height * (0.60f + 0.10f * cos(0.7f * orb2Phase * 2 * Math.PI).toFloat())
        drawOrb(Offset(ox2, oy2), size.width * 0.35f, accentColor.copy(alpha = 0.06f))
    }
}

private fun DrawScope.drawOrb(center: Offset, radius: Float, color: Color) {
    drawCircle(
        brush = Brush.radialGradient(
            colors = listOf(color, Color.Transparent),
            center = center, radius = radius,
        ),
        radius = radius, center = center,
    )
}
