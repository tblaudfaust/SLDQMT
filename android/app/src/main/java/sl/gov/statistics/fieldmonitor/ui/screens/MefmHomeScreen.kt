package sl.gov.statistics.fieldmonitor.ui.screens

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Place
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch
import sl.gov.statistics.fieldmonitor.data.local.AppDatabase
import sl.gov.statistics.fieldmonitor.data.local.MefmCounts
import sl.gov.statistics.fieldmonitor.data.local.MefmVisitEntity
import sl.gov.statistics.fieldmonitor.data.local.SyncStateEntity
import sl.gov.statistics.fieldmonitor.data.repo.AuthRepository
import sl.gov.statistics.fieldmonitor.data.repo.MefmRepository
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

data class MefmHomeState(val counts: MefmCounts, val pendingCheckins: Int, val eas: Int, val district: String, val sync: SyncStateEntity?, val hasForm: Boolean)

@HiltViewModel
class MefmHomeViewModel @Inject constructor(
    private val repo: MefmRepository,
    db: AppDatabase,
    auth: AuthRepository,
    private val scheduler: SyncScheduler,
) : ViewModel() {
    val fullName = auth.fullName
    val state: Flow<MefmHomeState> = combine(repo.counts(), repo.pendingCheckins(), repo.eaCount(), repo.districts(), db.syncStateDao().observe(), repo.form()) { values ->
        @Suppress("UNCHECKED_CAST")
        MefmHomeState(
            counts = values[0] as MefmCounts, pendingCheckins = values[1] as Int, eas = values[2] as Int,
            district = (values[3] as List<sl.gov.statistics.fieldmonitor.data.local.MefmDistrictEntity>).joinToString(", ") { it.name },
            sync = values[4] as SyncStateEntity?, hasForm = values[5] != null,
        )
    }
    val visits: Flow<List<MefmVisitEntity>> = repo.visits()
    fun syncNow() = scheduler.syncNow()
    fun newVisit(onCreated: (String) -> Unit) { viewModelScope.launch { onCreated(repo.newDraft()) } }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MefmHomeScreen(
    onOpenVisit: (String) -> Unit,
    onVisits: () -> Unit,
    onCheckin: () -> Unit,
    onSync: () -> Unit,
    onSettings: () -> Unit,
    vm: MefmHomeViewModel = hiltViewModel(),
) {
    val state by vm.state.collectAsStateWithLifecycle(initialValue = MefmHomeState(MefmCounts(0, 0, 0, 0), 0, 0, "", null, false))
    val visits by vm.visits.collectAsStateWithLifecycle(initialValue = emptyList())
    val permissions = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {}
    LaunchedEffect(Unit) {
        val wanted = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION)
        if (Build.VERSION.SDK_INT >= 33) wanted += Manifest.permission.POST_NOTIFICATIONS
        permissions.launch(wanted.toTypedArray())
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Column { Text("M&E Field Monitoring"); Text("${vm.fullName}${if (state.district.isNotBlank()) " · ${state.district}" else ""}", style = MaterialTheme.typography.bodySmall) } },
                navigationIcon = { CensusLogo(size = 36.dp, modifier = Modifier.padding(start = 12.dp)) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Navy, titleContentColor = MaterialTheme.colorScheme.onPrimary, actionIconContentColor = MaterialTheme.colorScheme.onPrimary),
                actions = {
                    IconButton(onClick = onSync) { Icon(Icons.Default.Sync, "Sync") }
                    IconButton(onClick = onSettings) { Icon(Icons.Default.Settings, "Settings") }
                },
            )
        },
    ) { padding ->
        Column(Modifier.padding(padding).padding(16.dp).fillMaxSize().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                StatTile("Drafts", state.counts.drafts, Amber, Modifier.weight(1f), onVisits)
                StatTile("Waiting to send", state.counts.waiting + state.pendingCheckins, Navy, Modifier.weight(1f), onVisits)
                StatTile("Sent", state.counts.synced, Green, Modifier.weight(1f), onVisits)
                StatTile("Rejected", state.counts.rejected, Red, Modifier.weight(1f), onVisits)
            }
            if (!state.hasForm || state.eas == 0) {
                Card { Column(Modifier.padding(14.dp)) {
                    Text("Waiting for the first sync", fontWeight = FontWeight.SemiBold)
                    Text("The questionnaire and your district's EA list come from the server. Connect to the internet once; after that the app works offline.", style = MaterialTheme.typography.bodySmall)
                    VSpace(8)
                    OutlinedButton(onClick = { vm.syncNow() }) { Text("Sync now") }
                } }
            }
            Button(onClick = { vm.newVisit(onOpenVisit) }, enabled = state.hasForm && state.eas > 0, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Default.Add, null); Text("  New visit form", style = MaterialTheme.typography.titleMedium)
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = onCheckin, Modifier.weight(1f), enabled = state.eas > 0) { Icon(Icons.Default.Place, null); Text(" Check in here") }
                OutlinedButton(onClick = onVisits, Modifier.weight(1f)) { Text("My forms") }
            }
            ListItem(
                headlineContent = { Text(when {
                    state.counts.waiting + state.pendingCheckins > 0 -> "${state.counts.waiting + state.pendingCheckins} record(s) waiting to send"
                    state.sync?.lastResult == "FAILED" -> "Last sync failed"
                    else -> "Everything is sent"
                }) },
                supportingContent = { Text((state.sync?.lastSyncAt?.let { "Last successful sync ${Time.format(it)}" } ?: "Not synced yet") + (state.sync?.lastError?.let { " · $it" } ?: "") + " · ${state.eas} EAs on this device") },
                trailingContent = { OutlinedButton(onClick = { vm.syncNow() }) { Text("Sync now") } },
            )
            if (visits.isNotEmpty()) {
                HorizontalDivider()
                Text("Recent forms", style = MaterialTheme.typography.titleMedium)
                visits.take(5).forEach { v -> VisitRow(v, onClick = { onOpenVisit(v.id) }) }
            }
        }
    }
}

@Composable
fun VisitRow(v: MefmVisitEntity, onClick: () -> Unit) {
    val status = when {
        !v.complete -> "Draft" to Amber
        v.syncError != null -> "Rejected" to Red
        v.pending -> "Waiting to send" to Navy
        v.serverStatus == "REVIEWED" -> "Reviewed" to Green
        else -> "Sent" to Green
    }
    ListItem(
        modifier = Modifier.clickable(onClick = onClick),
        headlineContent = { Text(if (v.eaLabel.isNotBlank()) v.eaLabel else if (v.popEaCode.isNotBlank()) "EA ${v.popEaCode}" else "No EA yet") },
        supportingContent = { Text("${Time.formatDate(v.visitDate)}${phaseName(v.phase)}${if (v.flags.isNotBlank()) " · GPS flags: ${v.flags.replace('_', ' ').replace(",", ", ")}" else ""}${if (v.openIssues > 0) " · ${v.openIssues} open issue(s)" else ""}") },
        trailingContent = { Text(status.first, color = status.second, fontWeight = FontWeight.SemiBold) },
    )
}

fun phaseName(p: String): String = when (p) { "P" -> " · Pre-field"; "L" -> " · Listing"; "E" -> " · Enumeration"; "M" -> " · Mop-up"; else -> "" }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MefmVisitListScreen(onOpen: (String) -> Unit, onBack: () -> Unit, vm: MefmHomeViewModel = hiltViewModel()) {
    val visits by vm.visits.collectAsStateWithLifecycle(initialValue = emptyList())
    Scaffold(topBar = { TopAppBar(title = { Text("My forms") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } }) }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState())) {
            if (visits.isEmpty()) Text("No forms yet. Start one from the home screen.", Modifier.padding(20.dp))
            visits.forEach { v -> VisitRow(v, onClick = { onOpen(v.id) }); HorizontalDivider() }
        }
    }
}
