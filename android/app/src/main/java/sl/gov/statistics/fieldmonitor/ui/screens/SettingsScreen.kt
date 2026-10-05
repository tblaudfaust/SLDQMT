package sl.gov.statistics.fieldmonitor.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.launch
import sl.gov.statistics.fieldmonitor.BuildConfig
import sl.gov.statistics.fieldmonitor.data.repo.AuthRepository
import sl.gov.statistics.fieldmonitor.data.repo.ErrorRepository
import sl.gov.statistics.fieldmonitor.ui.LabelValue
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(private val auth: AuthRepository, errors: ErrorRepository) : ViewModel() {
    val fullName = auth.fullName
    val pending = errors.observePendingCount()
    fun changePin(pin: String) = auth.setPin(pin)
    fun lock() = auth.lock()
    fun logout(done: () -> Unit) { viewModelScope.launch { auth.logout(); done() } }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(onBack: () -> Unit, onLoggedOut: () -> Unit, vm: SettingsViewModel = hiltViewModel()) {
    val pending by vm.pending.collectAsStateWithLifecycle(initialValue = 0)
    var newPin by remember { mutableStateOf("") }
    var pinSaved by remember { mutableStateOf(false) }
    var confirmLogout by remember { mutableStateOf(false) }

    Scaffold(topBar = { TopAppBar(title = { Text("Settings") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } }) }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            LabelValue("Signed in as", vm.fullName)
            LabelValue("App version", BuildConfig.VERSION_NAME)
            LabelValue("Server", BuildConfig.API_BASE_URL)
            Text("Change PIN", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                newPin, { if (it.length <= 4 && it.all(Char::isDigit)) newPin = it }, label = { Text("New 4-digit PIN") }, singleLine = true,
                visualTransformation = PasswordVisualTransformation(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                modifier = Modifier.fillMaxWidth(),
            )
            Button(onClick = { if (newPin.length == 4) { vm.changePin(newPin); newPin = ""; pinSaved = true } }, enabled = newPin.length == 4) { Text("Save PIN") }
            if (pinSaved) Text("PIN updated.", color = MaterialTheme.colorScheme.tertiary)
            OutlinedButton(onClick = { vm.lock() }, modifier = Modifier.fillMaxWidth()) { Text("Lock app now") }
            OutlinedButton(onClick = { confirmLogout = true }, modifier = Modifier.fillMaxWidth()) { Text("Sign out") }
            if (pending > 0) Text("$pending record(s) have not been synced yet. Signing out keeps them on the tablet; they upload after the next sign-in.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
        }
    }

    if (confirmLogout) {
        AlertDialog(
            onDismissRequest = { confirmLogout = false },
            title = { Text("Sign out?") },
            text = { Text("You will need internet to sign in again. Records stay on this tablet.") },
            confirmButton = { TextButton(onClick = { confirmLogout = false; vm.logout(onLoggedOut) }) { Text("Sign out") } },
            dismissButton = { TextButton(onClick = { confirmLogout = false }) { Text("Cancel") } },
        )
    }
}
