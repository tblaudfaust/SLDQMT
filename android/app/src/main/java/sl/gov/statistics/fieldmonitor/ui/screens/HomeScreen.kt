package sl.gov.statistics.fieldmonitor.ui.screens

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import sl.gov.statistics.fieldmonitor.data.local.AppDatabase
import sl.gov.statistics.fieldmonitor.data.local.Counts
import sl.gov.statistics.fieldmonitor.data.local.SyncStateEntity
import sl.gov.statistics.fieldmonitor.data.repo.AuthRepository
import sl.gov.statistics.fieldmonitor.data.repo.ErrorRepository
import sl.gov.statistics.fieldmonitor.sync.SyncScheduler
import sl.gov.statistics.fieldmonitor.ui.CensusLogo
import sl.gov.statistics.fieldmonitor.ui.StatTile
import sl.gov.statistics.fieldmonitor.ui.VSpace
import sl.gov.statistics.fieldmonitor.ui.theme.Amber
import sl.gov.statistics.fieldmonitor.ui.theme.Green
import sl.gov.statistics.fieldmonitor.ui.theme.Navy
import sl.gov.statistics.fieldmonitor.ui.theme.Red
import sl.gov.statistics.fieldmonitor.util.Time
import javax.inject.Inject

data class HomeState(val counts: Counts, val pending: Int, val sync: SyncStateEntity?)

@HiltViewModel
class HomeViewModel @Inject constructor(
    errors: ErrorRepository,
    db: AppDatabase,
    auth: AuthRepository,
    private val scheduler: SyncScheduler,
) : ViewModel() {
    val fullName = auth.fullName
    val state: Flow<HomeState> = combine(errors.observeCounts(), errors.observePendingCount(), db.syncStateDao().observe()) { c, p, s ->
        HomeState(c, p, s)
    }
    fun syncNow() = scheduler.syncNow()
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onNewError: () -> Unit,
    onErrors: () -> Unit,
    onDue: () -> Unit,
    onSync: () -> Unit,
    onSettings: () -> Unit,
    vm: HomeViewModel = hiltViewModel(),
) {
    val state by vm.state.collectAsStateWithLifecycle(initialValue = HomeState(Counts(0, 0, 0, 0), 0, null))
    val permissions = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {}
    LaunchedEffect(Unit) {
        val wanted = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION)
        if (Build.VERSION.SDK_INT >= 33) wanted += Manifest.permission.POST_NOTIFICATIONS
        permissions.launch(wanted.toTypedArray())
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Field Monitor · ${vm.fullName}") },
                navigationIcon = { CensusLogo(size = 36.dp, modifier = Modifier.padding(start = 12.dp)) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Navy, titleContentColor = MaterialTheme.colorScheme.onPrimary, actionIconContentColor = MaterialTheme.colorScheme.onPrimary),
                actions = {
                    IconButton(onClick = onSync) { Icon(Icons.Default.Sync, "Sync") }
                    IconButton(onClick = onSettings) { Icon(Icons.Default.Settings, "Settings") }
                },
            )
        },
    ) { padding ->
        Column(Modifier.padding(padding).padding(20.dp).fillMaxSize().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                StatTile("Total errors", state.counts.total, Navy, Modifier.weight(1f), onErrors)
                StatTile("Resolved", state.counts.resolved, Green, Modifier.weight(1f), onErrors)
                StatTile("Unresolved", state.counts.unresolved, Amber, Modifier.weight(1f), onErrors)
                StatTile("Overdue follow-ups", state.counts.overdue, Red, Modifier.weight(1f), onDue)
            }
            Button(onClick = onNewError, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Default.Add, null); Text("  Log new error", style = MaterialTheme.typography.titleMedium)
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedButton(onClick = onErrors, Modifier.weight(1f)) { Text("All errors") }
                OutlinedButton(onClick = onDue, Modifier.weight(1f)) { Text("Follow-ups due (${state.counts.overdue})") }
            }
            VSpace(4)
            ListItem(
                headlineContent = { Text(syncHeadline(state)) },
                supportingContent = { Text(syncDetail(state)) },
                trailingContent = { OutlinedButton(onClick = { vm.syncNow() }) { Text("Sync now") } },
            )
        }
    }
}

private fun syncHeadline(s: HomeState): String = when {
    s.pending > 0 -> "${s.pending} change(s) waiting to sync"
    s.sync?.lastResult == "FAILED" -> "Last sync failed"
    else -> "Everything is synced"
}

private fun syncDetail(s: HomeState): String {
    val last = s.sync?.lastSyncAt?.let { "Last successful sync ${Time.format(it)}" } ?: "Not synced yet"
    val err = s.sync?.lastError?.let { " · $it" } ?: ""
    return last + err
}
