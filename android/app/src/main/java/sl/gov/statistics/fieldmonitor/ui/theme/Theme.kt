package sl.gov.statistics.fieldmonitor.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Census identity: the logo blue ring (#5170FF) darkened for text contrast, and the logo green (#00BC5D).
val Navy = Color(0xFF2F4FD6)
val NavyDark = Color(0xFF1E3599)
val Amber = Color(0xFFF2B84B)
val Green = Color(0xFF00A651)
val Red = Color(0xFFC62828)
val Surface = Color(0xFFF7F9FC)

private val LightColors = lightColorScheme(
    primary = Navy,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDCE3FB),
    onPrimaryContainer = NavyDark,
    secondary = Amber,
    onSecondary = Color.Black,
    tertiary = Green,
    error = Red,
    background = Surface,
    surface = Color.White,
)

/** Light only: tablets are used outdoors, in sunlight. */
@Composable
fun FieldMonitorTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = LightColors, content = content)
}
