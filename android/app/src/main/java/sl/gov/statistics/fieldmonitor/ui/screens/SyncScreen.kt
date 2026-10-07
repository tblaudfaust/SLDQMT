package sl.gov.statistics.fieldmonitor.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.work.WorkInfo
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import sl.gov.statistics.fieldmonitor.BuildConfig
import sl.gov.statistics.fieldmonitor.data.SessionStore
import sl.gov.statistics.fieldmonitor.data.local.AppDatabase
import sl.gov.statistics.fieldmonitor.data.local.ErrorEntity
import sl.gov.statistics.fieldmonitor.data.local.SyncStateEntity
import sl.gov.statistics.fieldmonitor.data.repo.ErrorRepository
import sl.gov.statistics.fieldmonitor.data.repo.MefmRepository
import sl.gov.statistics.fieldmonitor.sync.SyncScheduler
import sl.gov.statistics.fieldmonitor.ui.LabelValue
import sl.gov.statistics.fieldmonitor.util.Time
import javax.inject.Inject

data class SyncUi(val state: SyncStateEntity?, val pending: Int, val rejected: List<ErrorEntity>, val running: Boolean)

@HiltViewModel
class SyncViewModel @Inject constructor(
    db: AppDatabase,
    errors: ErrorRepository,
    mefm: MefmRepository,
    session: SessionStore,
    private val scheduler: SyncScheduler,
) : ViewModel() {
    val deviceId = session.deviceId
    private val pending = combine(errors.observePendingCount(), mefm.pendingVisits(), mefm.pendingCheckins()) { a, b, c -> a + b + c }
    val ui: Flow<SyncUi> = combine(
        db.syncStateDao().observe(),
        pending,
        errors.observeRejected(),
        scheduler.observeSyncRunning().map { infos -> infos.any { it.state == WorkInfo.State.RUNNING } },
    ) { s, p, r, running -> SyncUi(s, p, r, running) }

    fun syncNow() = scheduler.syncNow()
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SyncScreen(onOpen: (String) -> Unit, onBack: () -> Unit, vm: SyncViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsStateWithLifecycle(initialValue = SyncUi(null, 0, emptyList(), false))

    Scaffold(topBar = { TopAppBar(title = { Text("Sync") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } }) }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Card { Column(Modifier.padding(16.dp)) {
                LabelValue("Last successful sync", ui.state?.lastSyncAt?.let { Time.format(it) } ?: "Never")
                LabelValue("Last result", ui.state?.lastResult ?: "—")
                LabelValue("Last error", ui.state?.lastError)
                LabelValue("Waiting to upload", "${ui.pending} record(s)")
                LabelValue("Rejected by server", "${ui.rejected.size}")
                LabelValue("App version", BuildConfig.VERSION_NAME)
                LabelValue("Device ID", vm.deviceId)
            } }
            Button(onClick = { vm.syncNow() }, enabled = !ui.running, modifier = Modifier.fillMaxWidth()) { Text(if (ui.running) "Syncing…" else "Sync now") }
            Text("Sync runs automatically every 15 minutes and a few seconds after every change, whenever the tablet has a connection. Nothing is removed from the tablet until the server confirms it.", style = MaterialTheme.typography.bodySmall)
            if (ui.rejected.isNotEmpty()) {
                Text("Rejected records", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.error)
                ui.rejected.forEach { e ->
                    Card(Modifier.fillMaxWidth().clickable { onOpen(e.id) }) {
                        Column(Modifier.padding(12.dp)) {
                            Text(e.displayId, style = MaterialTheme.typography.titleSmall)
                            Text(e.syncError ?: "", color = MaterialTheme.colorScheme.error)
                            Text("Open the record to retry after fixing it.", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }
    }
}
