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
import sl.gov.statistics.fieldmonitor.util.AppUpdater
import sl.gov.statistics.fieldmonitor.util.Time
import sl.gov.statistics.fieldmonitor.util.UpdateState
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.TextButton
import androidx.compose.material.icons.filled.SystemUpdate
import javax.inject.Inject

data class HomeState(val counts: Counts, val pending: Int, val sync: SyncStateEntity?)

@HiltViewModel
class HomeViewModel @Inject constructor(
    errors: ErrorRepository,
    db: AppDatabase,
    auth: AuthRepository,
    private val scheduler: SyncScheduler,
    private val updater: AppUpdater,
) : ViewModel() {
    val fullName = auth.fullName
    val state: Flow<HomeState> = combine(errors.observeCounts(), errors.observePendingCount(), db.syncStateDao().observe()) { c, p, s ->
        HomeState(c, p, s)
    }
    val update = updater.state

    init { viewModelScope.launch { updater.check() } }

    fun syncNow() { scheduler.syncNow(); viewModelScope.launch { updater.check(force = true) } }
    fun downloadUpdate() { val s = update.value; if (s is UpdateState.Available) viewModelScope.launch { updater.download(s.info) } else if (s is UpdateState.Failed) viewModelScope.launch { updater.download(s.info) } }
    fun installUpdate() { when (val s = update.value) { is UpdateState.Ready -> updater.install(s.info, s.file); is UpdateState.NeedPermission -> updater.install(s.info, s.file); else -> {} } }
    fun dismissUpdate() = updater.dismiss()
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
    val update by vm.update.collectAsStateWithLifecycle()
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
            if (update !is UpdateState.Idle) UpdateCard(update, vm::downloadUpdate, vm::installUpdate, vm::dismissUpdate)
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

/** "A new version is available": download with the system downloader, then open the installer. */
@Composable
internal fun UpdateCard(u: UpdateState, onDownload: () -> Unit, onInstall: () -> Unit, onDismiss: () -> Unit) {
    val info = when (u) { is UpdateState.Available -> u.info; is UpdateState.Downloading -> u.info; is UpdateState.Ready -> u.info; is UpdateState.NeedPermission -> u.info; is UpdateState.Failed -> u.info; else -> return }
    Card(colors = CardDefaults.cardColors(containerColor = Amber.copy(alpha = 0.18f)), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Icon(Icons.Default.SystemUpdate, null, tint = Navy)
                Text("Update available: SLPHC Field Monitor ${info.versionName}", style = MaterialTheme.typography.titleMedium)
            }
            if (info.notes.isNotBlank()) Text(info.notes, style = MaterialTheme.typography.bodyMedium)
            when (u) {
                is UpdateState.Downloading -> {
                    val total = if (u.total > 0) u.total else (info.sizeBytes ?: 0L)
                    if (total > 0) LinearProgressIndicator(progress = { (u.downloaded.toFloat() / total).coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth()) else LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    Text("Downloading… ${u.downloaded / 1_000_000} MB${if (total > 0) " of ${total / 1_000_000} MB" else ""}", style = MaterialTheme.typography.bodySmall)
                }
                is UpdateState.Ready -> Text("Downloaded. Tap Install: Android asks you to confirm, and the app reopens on the new version with your data in place.", style = MaterialTheme.typography.bodySmall)
                is UpdateState.NeedPermission -> Text("Allow this app to install updates on the settings page that opened, then come back and tap Install.", style = MaterialTheme.typography.bodySmall)
                is UpdateState.Failed -> Text(u.message, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                else -> Text("Your reports and drafts stay on the tablet. The download is ${info.sizeBytes?.let { "${it / 1_000_000} MB" } ?: "about 25 MB"}; use Wi-Fi if you can.", style = MaterialTheme.typography.bodySmall)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                when (u) {
                    is UpdateState.Available, is UpdateState.Failed -> Button(onClick = onDownload) { Text(if (u is UpdateState.Failed) "Try again" else "Download update") }
                    is UpdateState.Ready, is UpdateState.NeedPermission -> Button(onClick = onInstall) { Text("Install") }
                    else -> {}
                }
                if (u !is UpdateState.Downloading) TextButton(onClick = onDismiss) { Text("Later") }
            }
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
