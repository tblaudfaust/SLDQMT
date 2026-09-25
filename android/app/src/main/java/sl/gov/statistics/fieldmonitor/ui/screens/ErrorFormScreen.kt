package sl.gov.statistics.fieldmonitor.ui.screens

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
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import sl.gov.statistics.fieldmonitor.data.repo.ErrorRepository
import sl.gov.statistics.fieldmonitor.data.repo.NewError
import sl.gov.statistics.fieldmonitor.data.repo.ReferenceRepository
import sl.gov.statistics.fieldmonitor.ui.DropdownField
import sl.gov.statistics.fieldmonitor.ui.Option
import sl.gov.statistics.fieldmonitor.util.GpsFix
import sl.gov.statistics.fieldmonitor.util.LocationHelper
import sl.gov.statistics.fieldmonitor.util.Time
import java.time.Instant
import java.time.ZoneOffset
import javax.inject.Inject

data class FormState(
    val districtId: Int? = null,
    val teamId: Int? = null,
    val supervisorId: Int? = null,
    val supervisorName: String = "",
    val enumeratorId: Int? = null,
    val enumeratorName: String = "",
    val eaId: Int? = null,
    val categoryId: Int? = null,
    val sourceId: Int? = null,
    val description: String = "",
    val dateReceived: String = Time.today(),
    val supportMethod: String = "REMOTE",
    val actionTaken: String = "",
    val comments: String = "",
    val gps: GpsFix? = null,
    val gpsBusy: Boolean = false,
    val error: String? = null,
    val saving: Boolean = false,
)

@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class ErrorFormViewModel @Inject constructor(
    private val reference: ReferenceRepository,
    private val errors: ErrorRepository,
    private val location: LocationHelper,
) : ViewModel() {
    val form = MutableStateFlow(FormState())

    val districts = reference.districts().stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
    val teams = form.flatMapLatest { f -> f.districtId?.let { reference.teams(it) } ?: flowOf(emptyList()) }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
    val supervisors = form.flatMapLatest { f -> f.teamId?.let { reference.supervisors(it) } ?: flowOf(emptyList()) }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
    val enumerators = form.flatMapLatest { f -> f.teamId?.let { reference.enumerators(it) } ?: flowOf(emptyList()) }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
    val eas = form.flatMapLatest { f -> f.teamId?.let { reference.eas(it) } ?: flowOf(emptyList()) }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
    val categories = reference.categories().stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
    val sources = reference.sources().stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    init {
        // Pre-select when the monitor has exactly one district.
        viewModelScope.launch {
            districts.collect { d -> if (d.size == 1 && form.value.districtId == null) update { copy(districtId = d.first().id) } }
        }
    }

    fun update(block: FormState.() -> FormState) { form.value = form.value.block() }

    fun captureGps() {
        viewModelScope.launch {
            update { copy(gpsBusy = true) }
            val fix = location.currentFix()
            update { copy(gps = fix, gpsBusy = false, error = if (fix == null) "Could not get a GPS fix. Check location is on and try outdoors." else null) }
        }
    }

    fun save(onSaved: (String) -> Unit) {
        val f = form.value
        val missing = when {
            f.districtId == null -> "Select the district"
            f.teamId == null -> "Select the team"
            f.supervisorName.isBlank() -> "Enter the supervisor"
            f.categoryId == null -> "Select the error category"
            f.description.isBlank() -> "Describe the error"
            f.sourceId == null -> "Select how the error was received"
            f.actionTaken.isBlank() -> "Record the action taken"
            else -> null
        }
        if (missing != null) { update { copy(error = missing) }; return }
        viewModelScope.launch {
            update { copy(saving = true, error = null) }
            val district = districts.value.first { it.id == f.districtId }
            val id = errors.create(
                NewError(
                    districtId = district.id, districtCode = district.code, teamId = f.teamId, supervisorId = f.supervisorId,
                    supervisorName = f.supervisorName.ifBlank { null }, enumeratorId = f.enumeratorId, enumeratorName = f.enumeratorName.ifBlank { null },
                    eaId = f.eaId, categoryId = f.categoryId!!, sourceId = f.sourceId, description = f.description, dateReceived = f.dateReceived,
                    supportMethod = f.supportMethod, actionTaken = f.actionTaken, comments = f.comments.ifBlank { null }, gps = f.gps,
                )
            )
            onSaved(id)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ErrorFormScreen(onSaved: (String) -> Unit, onBack: () -> Unit, vm: ErrorFormViewModel = hiltViewModel()) {
    val f by vm.form.collectAsStateWithLifecycle()
    val districts by vm.districts.collectAsStateWithLifecycle()
    val teams by vm.teams.collectAsStateWithLifecycle()
    val supervisors by vm.supervisors.collectAsStateWithLifecycle()
    val enumerators by vm.enumerators.collectAsStateWithLifecycle()
    val eas by vm.eas.collectAsStateWithLifecycle()
    val categories by vm.categories.collectAsStateWithLifecycle()
    val sources by vm.sources.collectAsStateWithLifecycle()
    var showDate by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("Log new error") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } })
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Where", style = MaterialTheme.typography.titleMedium)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                DropdownField("District", districts.map { Option(it.id, it.name) }, f.districtId, { vm.update { copy(districtId = it.id, teamId = null, supervisorId = null, supervisorName = "", enumeratorId = null, enumeratorName = "", eaId = null) } }, Modifier.weight(1f))
                DropdownField("Team (supervisory area)", teams.map { Option(it.id, "${it.code} ${it.name}") }, f.teamId, { vm.update { copy(teamId = it.id, supervisorId = null, supervisorName = "", enumeratorId = null, enumeratorName = "", eaId = null) } }, Modifier.weight(1f), enabled = f.districtId != null)
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (supervisors.isNotEmpty()) {
                    DropdownField("Supervisor", supervisors.map { Option(it.id, it.name) }, f.supervisorId, { o -> vm.update { copy(supervisorId = o.id, supervisorName = o.label) } }, Modifier.weight(1f), enabled = f.teamId != null)
                } else {
                    OutlinedTextField(f.supervisorName, { s -> vm.update { copy(supervisorName = s) } }, label = { Text("Supervisor") }, modifier = Modifier.weight(1f), singleLine = true)
                }
                if (enumerators.isNotEmpty()) {
                    DropdownField("Enumerator", listOf(Option(null, "Not applicable")) + enumerators.map { Option(it.id, it.name) }, f.enumeratorId, { o -> vm.update { copy(enumeratorId = o.id, enumeratorName = if (o.id == null) "" else o.label) } }, Modifier.weight(1f), enabled = f.teamId != null)
                } else {
                    OutlinedTextField(f.enumeratorName, { s -> vm.update { copy(enumeratorName = s) } }, label = { Text("Enumerator (optional)") }, modifier = Modifier.weight(1f), singleLine = true)
                }
                DropdownField("EA", listOf(Option(null, "Not applicable")) + eas.map { Option(it.id, "EA ${it.code.takeLast(4)} · ${it.name ?: ""}${it.locality?.let { l -> " ($l)" } ?: ""}") }, f.eaId, { vm.update { copy(eaId = it.id) } }, Modifier.weight(1f), enabled = f.teamId != null)
            }

            Text("What", style = MaterialTheme.typography.titleMedium)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                DropdownField("Error category", categories.map { Option(it.id, it.name) }, f.categoryId, { vm.update { copy(categoryId = it.id) } }, Modifier.weight(1f))
                DropdownField("Received via", sources.map { Option(it.id, it.name) }, f.sourceId, { vm.update { copy(sourceId = it.id) } }, Modifier.weight(1f))
                OutlinedTextField(Time.formatDate(f.dateReceived), {}, readOnly = true, label = { Text("Date received") }, modifier = Modifier.weight(1f), trailingIcon = { TextButton(onClick = { showDate = true }) { Text("Change") } })
            }
            OutlinedTextField(f.description, { s -> vm.update { copy(description = s) } }, label = { Text("Error description (as received from DQM)") }, modifier = Modifier.fillMaxWidth(), minLines = 2)

            Text("Action", style = MaterialTheme.typography.titleMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = f.supportMethod == "REMOTE", onClick = { vm.update { copy(supportMethod = "REMOTE") } }, label = { Text("Remote (phone / WhatsApp)") })
                FilterChip(selected = f.supportMethod == "ONSITE", onClick = { vm.update { copy(supportMethod = "ONSITE") } }, label = { Text("Onsite visit") })
            }
            OutlinedTextField(f.actionTaken, { s -> vm.update { copy(actionTaken = s) } }, label = { Text("Action taken") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
            OutlinedTextField(f.comments, { s -> vm.update { copy(comments = s) } }, label = { Text("Comments (optional)") }, modifier = Modifier.fillMaxWidth())
            if (f.supportMethod == "ONSITE") {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    OutlinedButton(onClick = { vm.captureGps() }, enabled = !f.gpsBusy) { Text(if (f.gpsBusy) "Getting GPS…" else if (f.gps == null) "Capture GPS location" else "Recapture GPS") }
                    f.gps?.let { Text("%.5f, %.5f (±%.0f m)%s".format(it.lat, it.lng, it.accuracyM, if (it.good) "" else " · low accuracy")) }
                }
            }
            f.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button(onClick = { vm.save(onSaved) }, enabled = !f.saving, modifier = Modifier.fillMaxWidth()) { Text("Save error") }
            Text("The error is saved on this tablet immediately and synced when there is a connection. A follow-up reminder comes every 4 hours until it is resolved.", style = MaterialTheme.typography.bodySmall)
        }
    }

    if (showDate) {
        val state = rememberDatePickerState(initialSelectedDateMillis = Instant.parse(f.dateReceived + "T00:00:00Z").toEpochMilli())
        DatePickerDialog(
            onDismissRequest = { showDate = false },
            confirmButton = {
                TextButton(onClick = {
                    state.selectedDateMillis?.let { ms -> vm.update { copy(dateReceived = Instant.ofEpochMilli(ms).atZone(ZoneOffset.UTC).toLocalDate().toString()) } }
                    showDate = false
                }) { Text("OK") }
            },
        ) { DatePicker(state = state) }
    }
}
