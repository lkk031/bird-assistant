package com.assistantbird.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val DarkColorScheme = darkColorScheme(
    primary = Accent,
    onPrimary = TextPrimary,
    secondary = AccentHover,
    background = BgPrimary,
    surface = BgSecondary,
    onBackground = TextPrimary,
    onSurface = TextPrimary,
    error = Error,
)

@Composable
fun AssistantBirdTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        typography = AppTypography,
        content = content,
    )
}
