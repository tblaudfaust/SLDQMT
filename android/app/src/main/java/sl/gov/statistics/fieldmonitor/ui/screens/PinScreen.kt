package sl.gov.statistics.fieldmonitor.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.launch
import sl.gov.statistics.fieldmonitor.data.SessionStore
import sl.gov.statistics.fieldmonitor.data.repo.AuthRepository
import sl.gov.statistics.fieldmonitor.ui.CensusLogo
import javax.inject.Inject

@HiltViewModel
class PinViewModel @Inject constructor(private val auth: AuthRepository) : ViewModel() {
    val hasPin: Boolean get() = auth.hasPin
    val fullName: String get() = auth.fullName

    fun setPin(pin: String) = auth.setPin(pin)
    fun unlock(pin: String) = auth.unlockWithPin(pin)
    fun checkExpired(onExpired: () -> Unit) {
        viewModelScope.launch { if (auth.offlineSessionExpired()) onExpired() }
    }
    fun logoutForExpiry() {
        viewModelScope.launch { auth.logout() }
    }
}

@Composable
fun PinScreen(onUnlocked: () -> Unit, onWiped: () -> Unit, vm: PinViewModel = hiltViewModel()) {
    var pin by rememberSaveable { mutableStateOf("") }
    var confirm by rememberSaveable { mutableStateOf("") }
    var message by rememberSaveable { mutableStateOf<String?>(null) }
    val settingUp = !vm.hasPin

    Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
        Column(Modifier.width(380.dp), verticalArrangement = Arrangement.spacedBy(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            CensusLogo(size = 120.dp)
            Text(vm.fullName, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
            Text(if (settingUp) "Choose a 6-digit PIN" else "Enter your PIN", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            if (settingUp) Text("You will use this PIN to open the app when there is no internet.", style = MaterialTheme.typography.bodyMedium)
            OutlinedTextField(
                value = pin, onValueChange = { if (it.length <= 6 && it.all(Char::isDigit)) pin = it }, label = { Text("PIN") },
                singleLine = true, visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword), modifier = Modifier.fillMaxWidth(),
            )
            if (settingUp) {
                OutlinedTextField(
                    value = confirm, onValueChange = { if (it.length <= 6 && it.all(Char::isDigit)) confirm = it }, label = { Text("Confirm PIN") },
                    singleLine = true, visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword), modifier = Modifier.fillMaxWidth(),
                )
            }
            message?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button(
                modifier = Modifier.fillMaxWidth(),
                onClick = {
                    if (pin.length != 6) { message = "The PIN must be 6 digits"; return@Button }
                    if (settingUp) {
                        if (pin != confirm) { message = "PINs do not match"; return@Button }
                        vm.setPin(pin)
                        vm.unlock(pin)
                        onUnlocked()
                    } else {
                        when (val r = vm.unlock(pin)) {
                            SessionStore.PinResult.Ok -> {
                                // Unlock now; if the offline window has lapsed, force an online sign-in instead.
                                vm.checkExpired(
                                    onExpired = {
                                        vm.logoutForExpiry()
                                        onWiped()
                                    }
                                )
                                onUnlocked()
                            }
                            SessionStore.PinResult.Wiped -> { message = "Too many wrong PINs. Sign in again."; onWiped() }
                            is SessionStore.PinResult.Wrong -> { message = "Wrong PIN. ${r.attemptsLeft} attempts left."; pin = "" }
                            SessionStore.PinResult.NoPin -> onWiped()
                        }
                    }
                },
            ) { Text(if (settingUp) "Save PIN" else "Unlock") }
        }
    }
}
