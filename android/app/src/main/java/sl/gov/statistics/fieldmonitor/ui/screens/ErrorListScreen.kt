package sl.gov.statistics.fieldmonitor.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import sl.gov.statistics.fieldmonitor.data.local.ErrorEntity
import sl.gov.statistics.fieldmonitor.data.repo.ErrorRepository
import sl.gov.statistics.fieldmonitor.data.repo.ReferenceRepository
import sl.gov.statistics.fieldmonitor.ui.StatusChip
import sl.gov.statistics.fieldmonitor.util.Time
import javax.inject.Inject

data class ListFilters(
    val search: String = "",
    val status: String? = null, // UNRESOLVED | RESOLVED | OVERDUE
    val districtId: Int? = null,
    val teamId: Int? = null,
    val categoryId: Int? = null,
    val eaId: Int? = null,
    val dateFrom: String? = null,
    val dateTo: String? = null,
)

data class Lookups(
    val districts: Map<Int, String> = emptyMap(),
    val teams: Map<Int, String> = emptyMap(),
    val categories: Map<Int, String> = emptyMap(),
    val eas: Map<Int, String> = emptyMap(),
)

@HiltViewModel
class ErrorListViewModel @Inject constructor(errors: ErrorRepository, reference: ReferenceRepository) : ViewModel() {
    val filters = MutableStateFlow(ListFilters())

    val lookups = combine(reference.districts(), reference.allTeams(), reference.categories(), reference.allEas()) { d, t, c, e ->
        Lookups(d.associate { it.id to it.name }, t.associate { it.id to "${it.code} ${it.name}" }, c.associate { it.id to it.name }, e.associate { it.id to it.code })
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), Lookups())

    val items = combine(errors.observeAll(), filters, lookups) { all, f, lk ->
        all.filter { e ->
            val overdue = Time.isOverdue(e.nextFollowUpAt, e.status)
            (f.status == null || (f.status == "OVERDUE" && overdue) || e.status == f.status) &&
                (f.districtId == null || e.districtId == f.districtId) &&
                (f.teamId == null || e.teamId == f.teamId) &&
                (f.categoryId == null || e.categoryId == f.categoryId) &&
                (f.eaId == null || e.eaId == f.eaId) &&
                (f.dateFrom == null || e.dateReceived >= f.dateFrom) &&
                (f.dateTo == null || e.dateReceived <= f.dateTo) &&
                (f.search.isBlank() || listOfNotNull(e.displayId, e.description, e.supervisorName, e.enumeratorName, e.actionTaken, lk.teams[e.teamId], lk.eas[e.eaId], lk.categories[e.categoryId])
                    .any { it.contains(f.search, ignoreCase = true) })
        }
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    fun update(block: ListFilters.() -> ListFilters) { filters.value = filters.value.block() }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ErrorListScreen(onOpen: (String) -> Unit, onNew: () -> Unit, onBack: () -> Unit, vm: ErrorListViewModel = hiltViewModel()) {
    val items by vm.items.collectAsStateWithLifecycle()
    val filters by vm.filters.collectAsStateWithLifecycle()
    val lookups by vm.lookups.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Errors (${items.size})") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
                actions = { IconButton(onClick = onNew) { Icon(Icons.Default.Add, "New error") } },
            )
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            OutlinedTextField(
                value = filters.search, onValueChange = { s -> vm.update { copy(search = s) } },
                label = { Text("Search error ID, description, supervisor, enumerator, EA") }, singleLine = true,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
            )
            Row(Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(null to "All", "UNRESOLVED" to "Unresolved", "OVERDUE" to "Overdue", "RESOLVED" to "Resolved").forEach { (value, label) ->
                    FilterChip(selected = filters.status == value, onClick = { vm.update { copy(status = value) } }, label = { Text(label) })
                }
                lookups.districts.forEach { (id, name) ->
                    FilterChip(selected = filters.districtId == id, onClick = { vm.update { copy(districtId = if (districtId == id) null else id, teamId = null) } }, label = { Text(name) })
                }
                lookups.categories.forEach { (id, name) ->
                    FilterChip(selected = filters.categoryId == id, onClick = { vm.update { copy(categoryId = if (categoryId == id) null else id) } }, label = { Text(name) })
                }
            }
            if (filters.districtId != null) {
                Row(Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    lookups.teams.forEach { (id, name) ->
                        FilterChip(selected = filters.teamId == id, onClick = { vm.update { copy(teamId = if (teamId == id) null else id) } }, label = { Text(name) })
                    }
                }
            }
            HorizontalDivider(Modifier.padding(top = 8.dp))
            LazyColumn(Modifier.fillMaxSize(), contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(items, key = { it.id }) { e -> ErrorRow(e, lookups, onOpen) }
                if (items.isEmpty()) item { Text("No errors match.", modifier = Modifier.padding(16.dp)) }
            }
        }
    }
}

@Composable
fun ErrorRow(e: ErrorEntity, lk: Lookups, onOpen: (String) -> Unit) {
    val overdue = Time.isOverdue(e.nextFollowUpAt, e.status)
    Card(Modifier.fillMaxWidth().clickable { onOpen(e.id) }) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(e.displayId, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                StatusChip(e.status, overdue)
            }
            Text(lk.categories[e.categoryId] ?: "Category ${e.categoryId}", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            Text(e.description, style = MaterialTheme.typography.bodyMedium, maxLines = 2)
            Text(
                listOfNotNull(lk.districts[e.districtId], lk.teams[e.teamId], lk.eas[e.eaId]?.let { "EA $it" }, e.supervisorName?.let { "Sup: $it" }, e.enumeratorName?.let { "Enum: $it" }).joinToString(" · "),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                "Received ${Time.formatDate(e.dateReceived)} · " + when {
                    e.status == "RESOLVED" -> "Resolved ${Time.format(e.resolvedAt)}"
                    overdue -> "Follow-up was due ${Time.format(e.nextFollowUpAt)}"
                    else -> "Next follow-up ${Time.format(e.nextFollowUpAt)}"
                } + if (e.pending) " · not yet synced" else "",
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}
