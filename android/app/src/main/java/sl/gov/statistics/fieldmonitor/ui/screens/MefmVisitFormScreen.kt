package sl.gov.statistics.fieldmonitor.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import sl.gov.statistics.fieldmonitor.data.local.MefmEaEntity
import sl.gov.statistics.fieldmonitor.data.repo.EaLookup
import sl.gov.statistics.fieldmonitor.data.repo.MefmRepository
import sl.gov.statistics.fieldmonitor.mefm.Answers
import sl.gov.statistics.fieldmonitor.mefm.FormSpec
import sl.gov.statistics.fieldmonitor.mefm.Item
import sl.gov.statistics.fieldmonitor.mefm.Problem
import sl.gov.statistics.fieldmonitor.mefm.Routing
import sl.gov.statistics.fieldmonitor.mefm.Section
import sl.gov.statistics.fieldmonitor.mefm.Validation
import sl.gov.statistics.fieldmonitor.mefm.list
import sl.gov.statistics.fieldmonitor.mefm.rows
import sl.gov.statistics.fieldmonitor.mefm.str
import sl.gov.statistics.fieldmonitor.ui.VSpace
import sl.gov.statistics.fieldmonitor.ui.theme.Red
import sl.gov.statistics.fieldmonitor.util.GpsFix
import sl.gov.statistics.fieldmonitor.util.LocationHelper
import sl.gov.statistics.fieldmonitor.util.Time
import java.time.Instant
import java.time.LocalTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import javax.inject.Inject

data class FormUi(
    val sectionIndex: Int = 0,
    val ea: EaLookup? = null,
    val suggestions: List<MefmEaEntity> = emptyList(),
    val gps: GpsFix? = null,
    val gpsBusy: Boolean = false,
    val problems: List<Problem> = emptyList(),
    val serverError: String? = null,
    val wasComplete: Boolean = false,
    val loaded: Boolean = false,
    val message: String? = null,
)

@HiltViewModel
class MefmFormViewModel @Inject constructor(
    savedState: SavedStateHandle,
    private val repo: MefmRepository,
    private val location: LocationHelper,
    private val json: Json,
) : ViewModel() {
    val visitId: String = savedState.get<String>("id") ?: ""
    val spec = repo.form().stateIn(viewModelScope, SharingStarted.Eagerly, null)
    val answers = MutableStateFlow<Map<String, JsonElement>>(emptyMap())
    val ui = MutableStateFlow(FormUi())
    private var saveJob: Job? = null

    init {
        viewModelScope.launch {
            val v = repo.get(visitId)
            val loaded: Map<String, JsonElement> = v?.let { runCatching { json.decodeFromString(JsonObject.serializer(), it.answers) }.getOrNull() } ?: emptyMap()
            val a = loaded.toMutableMap()
            if (a.str("A2").isNullOrEmpty()) a["A2"] = JsonPrimitive(Time.today())
            if (a.str("A3_arrived").isNullOrEmpty()) a["A3_arrived"] = JsonPrimitive(LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm")))
            answers.value = a
            val gps = if (v?.lat != null && v.lng != null) GpsFix(v.lat, v.lng, v.accuracyM ?: 0.0, v.gpsAt ?: Time.nowIso()) else null
            ui.value = ui.value.copy(gps = gps, serverError = v?.syncError, wasComplete = v?.complete == true, loaded = true)
            a.str("A8")?.let { code -> if (code.length == 10) lookup(code, prefill = false) }
            if (gps == null) captureGps()
        }
    }

    fun set(code: String, value: JsonElement?) {
        val a = answers.value.toMutableMap()
        if (value == null) a.remove(code) else a[code] = value
        answers.value = a
        if (code == "A8") {
            val digits = (value as? JsonPrimitive)?.content?.filter(Char::isDigit) ?: ""
            viewModelScope.launch {
                if (digits.length == 10) lookup(digits, prefill = true)
                else ui.value = ui.value.copy(ea = null, suggestions = repo.suggestEas(digits))
            }
        }
        autosave()
    }

    fun setRow(group: String, index: Int, code: String, value: JsonElement?) {
        val rows = answers.value.rows(group).toMutableList()
        while (rows.size <= index) rows.add(JsonObject(emptyMap()))
        val row = rows[index].toMutableMap()
        if (value == null) row.remove(code) else row[code] = value
        rows[index] = JsonObject(row)
        set(group, JsonArray(rows))
    }

    fun addRow(group: String) = set(group, JsonArray(answers.value.rows(group) + JsonObject(emptyMap())))
    fun removeRow(group: String, index: Int) = set(group, JsonArray(answers.value.rows(group).filterIndexed { i, _ -> i != index }))

    private suspend fun lookup(code: String, prefill: Boolean) {
        val found = repo.lookupEa(code)
        ui.value = ui.value.copy(ea = found, suggestions = emptyList())
        if (found != null && prefill) {
            val a = answers.value.toMutableMap()
            found.ea.locStatus?.let { if (a.str("A9").isNullOrEmpty()) a["A9"] = JsonPrimitive(if (it == "2") "1" else "2") }
            found.ea.expectedHouseholds?.let { n -> if (a.str("E3").isNullOrEmpty()) a["E3"] = JsonPrimitive(n); if (a.str("H9_expected").isNullOrEmpty()) a["H9_expected"] = JsonPrimitive(n) }
            found.team?.supervisor?.let { s -> if (a.str("A11").isNullOrEmpty()) a["A11"] = JsonPrimitive(s) }
            answers.value = a
        }
    }

    fun captureGps() {
        viewModelScope.launch {
            ui.value = ui.value.copy(gpsBusy = true)
            val fix = location.currentFix()
            ui.value = ui.value.copy(gps = fix ?: ui.value.gps, gpsBusy = false, message = if (fix == null) "Could not get a GPS fix. Check location is on and try outdoors." else null)
            fix?.let { set("A15", buildJsonObject { put("lat", it.lat); put("lng", it.lng); put("accuracy_m", it.accuracyM); put("at", it.atIso) }) }
        }
    }

    fun goTo(index: Int) { ui.value = ui.value.copy(sectionIndex = index, message = null); saveNow(false) }

    private fun autosave() {
        saveJob?.cancel()
        saveJob = viewModelScope.launch { delay(700); repo.save(visitId, JsonObject(answers.value), ui.value.ea?.label ?: "", ui.value.gps, complete = false) }
    }

    fun saveNow(complete: Boolean) {
        saveJob?.cancel()
        viewModelScope.launch { repo.save(visitId, JsonObject(answers.value), ui.value.ea?.label ?: "", ui.value.gps, complete) }
    }

    fun submit(onDone: () -> Unit) {
        val s = spec.value ?: return
        val problems = Validation.validate(s, answers.value)
        if (ui.value.gps == null) { ui.value = ui.value.copy(problems = listOf(Problem("A", "A15", "A15: a GPS fix is required; wait for the device to capture one")) + problems); return }
        if (problems.isNotEmpty()) { ui.value = ui.value.copy(problems = problems); return }
        saveJob?.cancel()
        viewModelScope.launch {
            repo.save(visitId, JsonObject(answers.value), ui.value.ea?.label ?: "", ui.value.gps, complete = true)
            onDone()
        }
    }

    fun delete(onDone: () -> Unit) { viewModelScope.launch { repo.delete(visitId); onDone() } }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MefmVisitFormScreen(onDone: () -> Unit, onBack: () -> Unit, vm: MefmFormViewModel = hiltViewModel()) {
    val spec by vm.spec.collectAsStateWithLifecycle()
    val answers by vm.answers.collectAsStateWithLifecycle()
    val ui by vm.ui.collectAsStateWithLifecycle()
    var confirmDelete by remember { mutableStateOf(false) }
    val scroll = rememberScrollState()
    LaunchedEffect(ui.sectionIndex) { scroll.scrollTo(0) }
    val s = spec
    val sections = if (s != null) Routing.askedSections(s, answers) else emptyList()
    val index = ui.sectionIndex.coerceIn(0, (sections.size - 1).coerceAtLeast(0))
    val section = sections.getOrNull(index)
    val critical = if (s != null) Validation.criticalItems(s, answers) else emptyList()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(section?.let { "${it.code.take(1)}. ${it.title}" } ?: "Visit form") },
                navigationIcon = { IconButton(onClick = { vm.saveNow(false); onBack() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
                actions = { TextButton(onClick = { confirmDelete = true }) { Text("Delete") } },
            )
        },
    ) { padding ->
        if (s == null || section == null || !ui.loaded) {
            Column(Modifier.padding(padding).padding(20.dp)) { Text(if (s == null) "The questionnaire has not been downloaded yet. Sync once with internet." else "Loading…") }
            return@Scaffold
        }
        Column(Modifier.padding(padding).fillMaxSize().verticalScroll(scroll).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            LinearProgressIndicator(progress = { (index + 1f) / sections.size }, modifier = Modifier.fillMaxWidth())
            Text("Section ${index + 1} of ${sections.size}${ui.ea?.let { " · ${it.label}" } ?: ""}", style = MaterialTheme.typography.bodySmall)
            ui.serverError?.let { Card(colors = CardDefaults.cardColors(containerColor = Red.copy(alpha = 0.1f))) { Column(Modifier.padding(12.dp)) { Text("Rejected by the server", fontWeight = FontWeight.SemiBold, color = Red); Text(it) ; Text("Correct the form and submit it again.", style = MaterialTheme.typography.bodySmall) } } }
            section.intro?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }

            when (section.repeat) {
                "household" -> {
                    val rows = answers.rows("G")
                    rows.forEachIndexed { i, row ->
                        Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text("Household ${i + 1}", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                                TextButton(onClick = { vm.removeRow("G", i) }) { Text("Remove") }
                            }
                            section.items.filter { Routing.itemAsked(it, row) }.forEach { item -> ItemField(item, row, { code, v -> vm.setRow("G", i, code, v) }, ui, vm) }
                        } }
                    }
                    OutlinedButton(onClick = { vm.addRow("G") }) { Text("Add household (${rows.size} of at least ${section.minRepeat})") }
                }
                "respondent" -> {
                    val rows = answers.rows("I")
                    section.respondents.forEachIndexed { idx, label ->
                        val row = rows.getOrNull(idx) ?: emptyMap()
                        Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Text(label, style = MaterialTheme.typography.titleMedium)
                            section.items.filter { Routing.itemAsked(it, row, idx) }.forEach { item -> ItemField(item, row, { code, v -> vm.setRow("I", idx, code, v) }, ui, vm) }
                        } }
                    }
                }
                else -> section.items.filter { Routing.itemAsked(it, answers) }.forEach { item -> ItemField(item, answers, { code, v -> vm.set(code, v) }, ui, vm) }
            }

            if (section.code == "J" && critical.isNotEmpty()) {
                Card(colors = CardDefaults.cardColors(containerColor = Red.copy(alpha = 0.08f))) { Column(Modifier.padding(12.dp)) {
                    Text("Added automatically as Critical (⚑ items)", fontWeight = FontWeight.SemiBold)
                    critical.forEach { Text("• $it", style = MaterialTheme.typography.bodySmall) }
                } }
            }
            if (ui.problems.isNotEmpty()) {
                Card(colors = CardDefaults.cardColors(containerColor = Red.copy(alpha = 0.1f))) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Please complete before submitting (${ui.problems.size})", fontWeight = FontWeight.SemiBold, color = Red)
                    ui.problems.take(12).forEach { p ->
                        val target = sections.indexOfFirst { it.code == p.section }
                        Text(p.message, style = MaterialTheme.typography.bodySmall, modifier = Modifier.clickable(enabled = target >= 0) { vm.goTo(target) })
                    }
                    if (ui.problems.size > 12) Text("… and ${ui.problems.size - 12} more", style = MaterialTheme.typography.bodySmall)
                } }
            }
            ui.message?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            HorizontalDivider()
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedButton(onClick = { vm.goTo(index - 1) }, enabled = index > 0, modifier = Modifier.weight(1f)) { Text("Previous") }
                if (index < sections.size - 1) Button(onClick = { vm.goTo(index + 1) }, modifier = Modifier.weight(1f)) { Text("Next") }
                else Button(onClick = { vm.submit(onDone) }, modifier = Modifier.weight(1f)) { Text(if (ui.wasComplete) "Submit again" else "Submit form") }
            }
            Text("Answers are saved on this device as you go. A submitted form is sent at the next sync.", style = MaterialTheme.typography.bodySmall)
            VSpace(24)
        }
    }

    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("Delete this form?") },
            text = { Text("It is removed from this device. A copy already sent to the server stays there.") },
            confirmButton = { TextButton(onClick = { confirmDelete = false; vm.delete(onDone) }) { Text("Delete") } },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancel") } },
        )
    }
}

@OptIn(ExperimentalLayoutApi::class, ExperimentalMaterial3Api::class)
@Composable
private fun ItemField(item: Item, scope: Answers, set: (String, JsonElement?) -> Unit, ui: FormUi, vm: MefmFormViewModel) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(item.text + if (item.required && item.type !in listOf("gps", "issues")) "" else "", style = MaterialTheme.typography.bodyLarge, fontWeight = if (item.flag) FontWeight.SemiBold else FontWeight.Normal)
        item.help?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        when (item.type) {
            "code", "rating" -> {
                val current = scope.str(item.code)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    item.options.forEach { o -> FilterChip(selected = current == o.value, onClick = { set(item.code, if (current == o.value) null else JsonPrimitive(o.value)) }, label = { Text(o.label) }) }
                }
                if (item.other != null && current == item.other) {
                    OutlinedTextField(scope.str("${item.code}_other") ?: "", { set("${item.code}_other", JsonPrimitive(it)) }, label = { Text("Please specify") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                }
            }
            "multi" -> {
                val current = scope.list(item.code)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    item.options.forEach { o ->
                        FilterChip(
                            selected = o.value in current,
                            onClick = {
                                val next = when {
                                    o.value in current -> current - o.value
                                    o.value == item.exclusive -> listOf(o.value)
                                    else -> (current - listOfNotNull(item.exclusive)) + o.value
                                }
                                set(item.code, if (next.isEmpty()) null else JsonArray(next.map { JsonPrimitive(it) }))
                            },
                            label = { Text(o.label) },
                        )
                    }
                }
            }
            "int" -> OutlinedTextField(
                scope.str(item.code) ?: "", { t -> val d = t.filter(Char::isDigit).take(6); set(item.code, if (d.isEmpty()) null else JsonPrimitive(d.toInt())) },
                modifier = Modifier.fillMaxWidth(), singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                supportingText = if (item.maximum != null) ({ Text("0 to ${item.maximum}") }) else null,
            )
            "text" -> OutlinedTextField(scope.str(item.code) ?: "", { set(item.code, if (it.isBlank()) null else JsonPrimitive(it)) }, modifier = Modifier.fillMaxWidth(), minLines = if (item.code == "J10" || item.code == "I6") 2 else 1)
            "time" -> OutlinedTextField(
                scope.str(item.code) ?: "", { t -> set(item.code, if (t.isBlank()) null else JsonPrimitive(t.take(5))) }, placeholder = { Text("HH:MM") },
                modifier = Modifier.fillMaxWidth(), singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                trailingIcon = { TextButton(onClick = { set(item.code, JsonPrimitive(LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm")))) }) { Text("Now") } },
            )
            "date" -> {
                var show by remember { mutableStateOf(false) }
                val current = scope.str(item.code)
                OutlinedTextField(
                    Time.formatDate(current).ifBlank { "" }, {}, readOnly = true, modifier = Modifier.fillMaxWidth(), placeholder = { Text("Not set") },
                    trailingIcon = { Row { if (!item.required && current != null) TextButton(onClick = { set(item.code, null) }) { Text("Clear") }; TextButton(onClick = { show = true }) { Text(if (current == null) "Pick" else "Change") } } },
                )
                if (show) {
                    val state = rememberDatePickerState(initialSelectedDateMillis = runCatching { Instant.parse((current ?: Time.today()) + "T00:00:00Z").toEpochMilli() }.getOrNull())
                    DatePickerDialog(
                        onDismissRequest = { show = false },
                        confirmButton = { TextButton(onClick = { state.selectedDateMillis?.let { ms -> set(item.code, JsonPrimitive(Instant.ofEpochMilli(ms).atZone(ZoneOffset.UTC).toLocalDate().toString())) }; show = false }) { Text("OK") } },
                    ) { DatePicker(state = state) }
                }
            }
            "ea" -> {
                OutlinedTextField(
                    scope.str(item.code) ?: "", { t -> set(item.code, JsonPrimitive(t.filter(Char::isDigit).take(10))) }, modifier = Modifier.fillMaxWidth(), singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), placeholder = { Text("10-digit EA code") },
                    isError = (scope.str(item.code)?.length ?: 0) == 10 && ui.ea == null,
                )
                val found = ui.ea
                if (found != null) {
                    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) { Column(Modifier.padding(12.dp)) {
                        Text(found.ea.name ?: found.ea.code, fontWeight = FontWeight.SemiBold)
                        Text("Chiefdom ${found.chiefdom?.name ?: found.ea.chiefdomCode ?: "—"} · Section ${found.section?.name ?: found.ea.sectionCode ?: "—"}", style = MaterialTheme.typography.bodySmall)
                        Text("SA ${found.team?.code ?: "—"} ${found.team?.name ?: ""} · Supervisor ${found.team?.supervisor ?: "—"}", style = MaterialTheme.typography.bodySmall)
                        found.team?.enumerators?.takeIf { it.isNotBlank() }?.let { Text("Enumerators: $it", style = MaterialTheme.typography.bodySmall) }
                        Text("${found.ea.expectedHouseholds?.let { "$it expected households · " } ?: ""}${if (found.ea.lat != null) "reference point on file" else "no reference point"}", style = MaterialTheme.typography.bodySmall)
                    } }
                } else if ((scope.str(item.code)?.length ?: 0) == 10) {
                    Text("No EA with this code in your district's frame. Check the code.", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                } else if (ui.suggestions.isNotEmpty()) {
                    ui.suggestions.forEach { ea ->
                        Text("${ea.popEaCode} · ${ea.name ?: ea.code}${ea.locality?.let { " ($it)" } ?: ""}", modifier = Modifier.fillMaxWidth().clickable { set(item.code, JsonPrimitive(ea.popEaCode ?: "")) }.padding(vertical = 6.dp), style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
            "gps" -> GpsLine(ui.gps, ui.gpsBusy, onRecapture = { vm.captureGps() })
            "issues" -> IssuesEditor(scope.rows(item.code), set = { rows -> set(item.code, if (rows.isEmpty()) null else JsonArray(rows)) }, vm)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun IssuesEditor(rows: List<JsonObject>, set: (List<JsonObject>) -> Unit, vm: MefmFormViewModel) {
    val spec by vm.spec.collectAsStateWithLifecycle()
    fun update(i: Int, key: String, value: String?) {
        val row = rows[i].toMutableMap()
        if (value.isNullOrBlank()) row.remove(key) else row[key] = JsonPrimitive(value)
        set(rows.mapIndexed { j, r -> if (j == i) JsonObject(row) else r })
    }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        rows.forEachIndexed { i, row ->
            Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Issue ${i + 1}", style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                    TextButton(onClick = { set(rows.filterIndexed { j, _ -> j != i }) }) { Text("Remove") }
                }
                OutlinedTextField(row.str("question") ?: "", { update(i, "question", it.take(10)) }, label = { Text("Question no. (e.g. C5)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    (spec?.severities ?: listOf("Critical", "Major", "Minor")).forEach { sev -> FilterChip(selected = row.str("severity") == sev, onClick = { update(i, "severity", sev) }, label = { Text(sev) }) }
                }
                OutlinedTextField(row.str("description") ?: "", { update(i, "description", it) }, label = { Text("Description") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
                OutlinedTextField(row.str("action") ?: "", { update(i, "action", it) }, label = { Text("Action taken on the spot") }, modifier = Modifier.fillMaxWidth())
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    (spec?.referredTo ?: emptyList()).forEach { who -> FilterChip(selected = row.str("referred_to") == who, onClick = { update(i, "referred_to", if (row.str("referred_to") == who) null else who) }, label = { Text(who) }) }
                }
                OutlinedTextField(row.str("deadline") ?: "", { update(i, "deadline", it.take(10)) }, label = { Text("Deadline (YYYY-MM-DD)") }, singleLine = true, modifier = Modifier.fillMaxWidth(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
            } }
        }
        OutlinedButton(onClick = { set(rows + JsonObject(emptyMap())) }) { Text("Add issue") }
    }
}
