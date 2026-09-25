package sl.gov.statistics.fieldmonitor.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
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
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import sl.gov.statistics.fieldmonitor.data.repo.ErrorRepository
import sl.gov.statistics.fieldmonitor.data.repo.ReferenceRepository
import sl.gov.statistics.fieldmonitor.util.Time
import javax.inject.Inject

@HiltViewModel
class FollowUpsDueViewModel @Inject constructor(errors: ErrorRepository, reference: ReferenceRepository) : ViewModel() {
    val lookups = combine(reference.districts(), reference.allTeams(), reference.categories(), reference.allEas()) { d, t, c, e ->
        Lookups(d.associate { it.id to it.name }, t.associate { it.id to "${it.code} ${it.name}" }, c.associate { it.id to it.name }, e.associate { it.id to it.code })
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), Lookups())
    val due = errors.observeDue().stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FollowUpsDueScreen(onOpen: (String) -> Unit, onBack: () -> Unit, vm: FollowUpsDueViewModel = hiltViewModel()) {
    val due by vm.due.collectAsStateWithLifecycle()
    val lookups by vm.lookups.collectAsStateWithLifecycle()
    val overdue = due.filter { Time.isOverdue(it.nextFollowUpAt, it.status) }
    val upcoming = due - overdue.toSet()

    Scaffold(topBar = { TopAppBar(title = { Text("Follow-ups due") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } }) }) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item { Text("Overdue (${overdue.size})", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.error) }
            if (overdue.isEmpty()) item { Text("Nothing overdue. Well done.", Modifier.padding(bottom = 8.dp)) }
            items(overdue, key = { it.id }) { ErrorRow(it, lookups, onOpen) }
            item { Text("Coming up (${upcoming.size})", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 12.dp)) }
            items(upcoming, key = { it.id }) { ErrorRow(it, lookups, onOpen) }
        }
    }
}
