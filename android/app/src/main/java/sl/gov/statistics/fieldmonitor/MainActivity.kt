package sl.gov.statistics.fieldmonitor

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import dagger.hilt.android.AndroidEntryPoint
import sl.gov.statistics.fieldmonitor.ui.FieldMonitorNavHost
import sl.gov.statistics.fieldmonitor.ui.theme.FieldMonitorTheme

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val openFollowUps = intent?.getBooleanExtra(EXTRA_OPEN_FOLLOW_UPS, false) ?: false
        setContent {
            FieldMonitorTheme {
                FieldMonitorNavHost(startAtFollowUps = openFollowUps)
            }
        }
    }

    companion object {
        const val EXTRA_OPEN_FOLLOW_UPS = "open_follow_ups"
    }
}
