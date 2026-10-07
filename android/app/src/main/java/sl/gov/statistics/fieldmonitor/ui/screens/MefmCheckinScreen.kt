package sl.gov.statistics.fieldmonitor.ui.screens

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
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
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
import sl.gov.statistics.fieldmonitor.data.local.MefmCheckinEntity
import sl.gov.statistics.fieldmonitor.data.repo.MefmRepository
import sl.gov.statistics.fieldmonitor.ui.DropdownField
import sl.gov.statistics.fieldmonitor.ui.Option
import sl.gov.statistics.fieldmonitor.util.GpsFix
import sl.gov.statistics.fieldmonitor.util.LocationHelper
import sl.gov.statistics.fieldmonitor.util.Time
import javax.inject.Inject

data class CheckinState(val chiefdomId: Int? = null, val sectionId: Int? = null, val note: String = "", val gps: GpsFix? = null, val gpsBusy: Boolean = false, val error: String? = null, val saved: Boolean = false)

@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class MefmCheckinViewModel @Inject constructor(private val repo: MefmRepository, private val location: LocationHelper) : ViewModel() {
    val state = MutableStateFlow(CheckinState())
    val chiefdoms = repo.chiefdoms().stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
    val sections = state.flatMapLatest { s -> s.chiefdomId?.let { repo.sections(it) } ?: flowOf(emptyList()) }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
    val recent = repo.checkins()

    fun update(block: CheckinState.() -> CheckinState) { state.value = state.value.block() }

    fun captureGps() {
        viewModelScope.launch {
            update { copy(gpsBusy = true) }
            val fix = location.currentFix()
            update { copy(gps = fix, gpsBusy = false, error = if (fix == null) "Could not get a GPS fix. Check location is on and try outdoors." else null) }
        }
    }

    fun save() {
        val s = state.value
        val chiefdom = chiefdoms.value.firstOrNull { it.id == s.chiefdomId }
        if (chiefdom == null) { update { copy(error = "Select the chiefdom") }; return }
        val gps = s.gps
        if (gps == null) { update { copy(error = "A GPS fix is required for a check-in") }; return }
        viewModelScope.launch {
            repo.checkin(chiefdom, sections.value.firstOrNull { it.id == s.sectionId }, s.note, gps)
            update { copy(saved = true, error = null, note = "", gps = null) }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MefmCheckinScreen(onBack: () -> Unit, vm: MefmCheckinViewModel = hiltViewModel()) {
    val s by vm.state.collectAsStateWithLifecycle()
    val chiefdoms by vm.chiefdoms.collectAsStateWithLifecycle()
    val sections by vm.sections.collectAsStateWithLifecycle()
    val recent by vm.recent.collectAsStateWithLifecycle(initialValue = emptyList<MefmCheckinEntity>())
    LaunchedEffect(Unit) { if (s.gps == null && !s.gpsBusy) vm.captureGps() }

    Scaffold(topBar = { TopAppBar(title = { Text("Check in") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } }) }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Record where you are without filling a full form, for example when passing through a chiefdom or section.", style = MaterialTheme.typography.bodyMedium)
            DropdownField("Chiefdom", chiefdoms.map { Option(it.id, it.name) }, s.chiefdomId, { vm.update { copy(chiefdomId = it.id, sectionId = null, saved = false) } })
            DropdownField("Section (optional)", listOf(Option(null, "Not specified")) + sections.map { Option(it.id, it.name) }, s.sectionId, { vm.update { copy(sectionId = it.id, saved = false) } }, enabled = s.chiefdomId != null)
            OutlinedTextField(s.note, { vm.update { copy(note = it, saved = false) } }, label = { Text("Note (optional)") }, modifier = Modifier.fillMaxWidth())
            GpsLine(s.gps, s.gpsBusy, onRecapture = { vm.captureGps() })
            s.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            if (s.saved) Text("Check-in saved. It is sent at the next sync.", color = MaterialTheme.colorScheme.tertiary)
            Button(onClick = { vm.save() }, enabled = s.gps != null && !s.gpsBusy, modifier = Modifier.fillMaxWidth()) { Text("Save check-in") }
            if (recent.isNotEmpty()) {
                HorizontalDivider()
                Text("Recent check-ins", style = MaterialTheme.typography.titleMedium)
                recent.forEach { c ->
                    ListItem(headlineContent = { Text(c.label) }, supportingContent = { Text("${Time.format(c.at)}${c.note?.let { " · $it" } ?: ""}") }, trailingContent = { Text(if (c.syncError != null) "Rejected" else if (c.pending) "Waiting" else "Sent") })
                }
            }
        }
    }
}

@Composable
fun GpsLine(gps: GpsFix?, busy: Boolean, onRecapture: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            when {
                busy -> "Getting GPS fix…"
                gps == null -> "No GPS fix yet. The form cannot be submitted without one."
                else -> "GPS %.5f, %.5f (±%.0f m)%s".format(gps.lat, gps.lng, gps.accuracyM, if (gps.good) "" else " · low accuracy, move to open sky and recapture")
            },
            style = MaterialTheme.typography.bodyMedium,
            color = if (gps == null && !busy) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
        )
        OutlinedButton(onClick = onRecapture, enabled = !busy) { Text(if (gps == null) "Capture GPS" else "Recapture GPS") }
    }
}
