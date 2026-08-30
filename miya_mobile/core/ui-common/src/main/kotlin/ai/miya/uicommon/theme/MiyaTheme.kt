package ai.miya.uicommon.theme

import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.graphics.Color

@Composable
fun MiyaTheme(content: @Composable () -> Unit) {
    val theme by collectAsState()

    val colorScheme = darkColorScheme(
        primary = theme.primary,
        onPrimary = Color.White,
        primaryContainer = theme.primary.copy(alpha = 0.15f),
        onPrimaryContainer = theme.primaryLight,
        secondary = theme.secondary,
        onSecondary = Color.White,
        secondaryContainer = theme.secondary.copy(alpha = 0.15f),
        onSecondaryContainer = theme.secondary,
        tertiary = theme.secondaryLight,
        surface = theme.background,
        surfaceVariant = Color(0xFF2D2228),
        background = theme.background,
        onBackground = theme.onSurface,
        onSurface = theme.onSurface,
        onSurfaceVariant = theme.onSurfaceVariant,
        error = Color(0xFFFF6B6B),
        onError = Color.White,
        outline = theme.glassBorder,
        outlineVariant = theme.glassBorder.copy(alpha = 0.5f),
    )

    CompositionLocalProvider(LocalMiyaTheme provides theme) {
        MaterialTheme(
            colorScheme = colorScheme,
            typography = MiyaTypography,
            content = content,
        )
    }
}

@Composable
fun collectAsState(): State<MiyaThemeConfig> {
    return activeTheme.collectAsState()
}
