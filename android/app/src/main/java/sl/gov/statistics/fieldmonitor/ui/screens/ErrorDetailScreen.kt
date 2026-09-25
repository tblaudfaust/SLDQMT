package sl.gov.statistics.fieldmonitor.ui.screens

import android.content.Intent
import android.net.Uri
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
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import sl.gov.statistics.fieldmonitor.data.local.ActivityEntity
import sl.gov.statistics.fieldmonitor.data.local.ErrorEntity
import sl.gov.statistics.fieldmonitor.data.local.FollowUpEntity
import sl.gov.statistics.fieldmonitor.data.repo.ErrorRepository
import sl.gov.statistics.fieldmonitor.data.repo.ReferenceRepository
import sl.gov.statistics.fieldmonitor.data.repo.StatusUpdate
import sl.gov.statistics.fieldmonitor.ui.LabelValue
import sl.gov.statistics.fieldmonitor.ui.StatusChip
import sl.gov.statistics.fieldmonitor.ui.VSpace
import sl.gov.statistics.fieldmonitor.util.GpsFix
import sl.gov.statistics.fieldmonitor.util.LocationHelper
import sl.gov.statistics.fieldmonitor.util.Time
import javax.inject.Inject

data class DetailState(
    val error: ErrorEntity? = null,
    val followUps: List<FollowUpEntity> = emptyList(),
    val activity: List<ActivityEntity> = emptyList(),
    val lookups: Lookups = Lookups(),
)

@HiltViewModel
class ErrorDetailViewModel @Inject constructor(
    saved: SavedStateHandle,
    private val errors: ErrorRepository,
    reference: ReferenceRepository,
    private val location: LocationHelper,
) : ViewModel() {
    private val id: String = saved["id"] ?: ""
    val gps = MutableStateFlow<GpsFix?>(null)
    val gpsBusy = MutableStateFlow(false)

    private val lookups = combine(reference.districts(), reference.allTeams(), reference.categories(), reference.allEas()) { d, t, c, e ->
        Lookups(d.associate { it.id to it.name }, t.associate { it.id to "${it.code} ${it.name}" }, c.associate { it.id to it.name }, e.associate { it.id to it.code })
    }

    val state = combine(errors.observe(id), errors.observeFollowUps(id), errors.observeActivity(id), lookups) { e, f, a, l ->
        DetailState(e, f, a, l)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), DetailState())

    fun captureGps() {
        viewModelScope.launch { gpsBusy.value = true; gps.value = location.currentFix(); gpsBusy.value = false }
    }

    fun submit(update: StatusUpdate, done: () -> Unit) {
        viewModelScope.launch { errors.update(id, update.copy(gps = gps.value)); gps.value = null; done() }
    }

    fun retry() { viewModelScope.launch { errors.retry(id) } }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ErrorDetailScreen(errorId: String, onBack: () -> Unit, vm: ErrorDetailViewModel = hiltViewModel()) {
    val s by vm.state.collectAsStateWithLifecycle()
    val gps by vm.gps.collectAsStateWithLifecycle()
    val gpsBusy by vm.gpsBusy.collectAsStateWithLifecycle()
    var showUpdate by remember { mutableStateOf(false) }
    val context = LocalContext.current
    val e = s.error

    Scaffold(
        topBar = {
            TopAppBar(title = { Text(e?.displayId ?: "Error") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } })
        },
    ) { padding ->
        if (e == null) { Text("Loading…", Modifier.padding(padding).padding(20.dp)); return@Scaffold }
        val overdue = Time.isOverdue(e.nextFollowUpAt, e.status)
        Column(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(s.lookups.categories[e.categoryId] ?: "", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                StatusChip(e.status, overdue)
            }
            if (e.syncError != null) {
                Card(colors = androidx.compose.material3.CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                    Column(Modifier.padding(12.dp)) {
                        Text("The server rejected this record: ${e.syncError}", color = MaterialTheme.colorScheme.onErrorContainer)
                        OutlinedButton(onClick = { vm.retry() }) { Text("Retry sync") }
                    }
                }
            }
            Card { Column(Modifier.padding(16.dp)) {
                LabelValue("Description", e.description)
                LabelValue("District", s.lookups.districts[e.districtId])
                LabelValue("Team", s.lookups.teams[e.teamId])
                LabelValue("EA", s.lookups.eas[e.eaId])
                LabelValue("Supervisor", e.supervisorName)
                LabelValue("Enumerator", e.enumeratorName)
                LabelValue("Date received", Time.formatDate(e.dateReceived))
                LabelValue("Support method", if (e.supportMethod == "ONSITE") "Onsite visit" else "Remote")
                LabelValue("Action taken", e.actionTaken)
                LabelValue("Comments", e.comments)
                LabelValue("Last action", Time.format(e.lastActionAt))
                if (e.status == "RESOLVED") LabelValue("Resolved", Time.format(e.resolvedAt)) else LabelValue(if (overdue) "Follow-up was due" else "Next follow-up", Time.format(e.nextFollowUpAt))
                if (e.lat != null && e.lng != null) {
                    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        LabelValue("GPS", "%.5f, %.5f (±%.0f m)".format(e.lat, e.lng, e.accuracyM ?: 0.0))
                        OutlinedButton(onClick = {
                            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("geo:${e.lat},${e.lng}?q=${e.lat},${e.lng}(${e.displayId})")))
                        }) { Text("Open in maps") }
                    }
                }
                LabelValue("Sync", if (e.pending) "Waiting to sync" else "Synced")
            } }

            Button(onClick = { showUpdate = true }, modifier = Modifier.fillMaxWidth()) {
                Text(if (e.status == "RESOLVED") "Record new feedback / reopen" else "Record follow-up or update status")
            }

            Text("Follow-ups (${s.followUps.size})", style = MaterialTheme.typography.titleMedium)
            if (s.followUps.isEmpty()) Text("No follow-ups recorded yet.", style = MaterialTheme.typography.bodyMedium)
            s.followUps.forEach { f ->
                Card { Column(Modifier.padding(12.dp)) {
                    Text("${Time.format(f.at)} · ${if (f.method == "ONSITE") "Onsite" else "Remote"}${f.contacted?.let { " · $it" } ?: ""}", style = MaterialTheme.typography.labelLarge)
                    f.outcome?.let { Text(it) }
                    f.comments?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                    if (f.lat != null) Text("GPS %.5f, %.5f".format(f.lat, f.lng), style = MaterialTheme.typography.bodySmall)
                } }
            }

            Text("Activity history", style = MaterialTheme.typography.titleMedium)
            s.activity.forEach { a ->
                Column(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                    Text("${Time.format(a.clientAt)} · ${a.previousStatus?.let { "$it → " } ?: ""}${a.newStatus}", style = MaterialTheme.typography.labelLarge)
                    a.actionTaken?.let { Text(it) }
                    a.comments?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                    HorizontalDivider(Modifier.padding(top = 6.dp))
                }
            }
            VSpace(24)
        }
    }

    if (showUpdate && e != null) {
        UpdateSheet(
            current = e, gps = gps, gpsBusy = gpsBusy, onCaptureGps = { vm.captureGps() },
            onDismiss = { showUpdate = false },
            onSubmit = { u -> vm.submit(u) { showUpdate = false } },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun UpdateSheet(current: ErrorEntity, gps: GpsFix?, gpsBusy: Boolean, onCaptureGps: () -> Unit, onDismiss: () -> Unit, onSubmit: (StatusUpdate) -> Unit) {
    var status by remember { mutableStateOf(current.status) }
    var method by remember { mutableStateOf(current.supportMethod) }
    var contacted by remember { mutableStateOf(current.supervisorName ?: "") }
    var action by remember { mutableStateOf("") }
    var comments by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(Modifier.padding(20.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Update ${current.displayId}", style = MaterialTheme.typography.titleLarge)
            Text("Status", style = MaterialTheme.typography.labelLarge)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = status == "UNRESOLVED", onClick = { status = "UNRESOLVED" }, label = { Text("Unresolved") })
                FilterChip(selected = status == "RESOLVED", onClick = { status = "RESOLVED" }, label = { Text("Resolved") })
            }
            Text("Support method", style = MaterialTheme.typography.labelLarge)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = method == "REMOTE", onClick = { method = "REMOTE" }, label = { Text("Remote") })
                FilterChip(selected = method == "ONSITE", onClick = { method = "ONSITE" }, label = { Text("Onsite") })
            }
            OutlinedTextField(contacted, { contacted = it }, label = { Text("Person contacted") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(action, { action = it }, label = { Text(if (status == "RESOLVED") "How was it resolved?" else "Action taken / feedback from the team") }, minLines = 2, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(comments, { comments = it }, label = { Text("Comments (optional)") }, modifier = Modifier.fillMaxWidth())
            if (method == "ONSITE") {
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedButton(onClick = onCaptureGps, enabled = !gpsBusy) { Text(if (gpsBusy) "Getting GPS…" else if (gps == null) "Capture GPS" else "Recapture GPS") }
                    gps?.let { Text("%.5f, %.5f (±%.0f m)".format(it.lat, it.lng, it.accuracyM)) }
                }
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button(
                onClick = {
                    if (action.isBlank()) { error = "Record what was done"; return@Button }
                    onSubmit(StatusUpdate(status, action, comments.ifBlank { null }, method, contacted.ifBlank { null }, gps))
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text(if (status == "RESOLVED") "Mark resolved" else "Save follow-up") }
            Text(if (status == "RESOLVED") "Reminders stop once resolved." else "The next reminder comes 4 hours after this follow-up.", style = MaterialTheme.typography.bodySmall)
            VSpace(24)
        }
    }
}
