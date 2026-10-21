package sl.gov.statistics.fieldmonitor.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.foundation.Image
import androidx.compose.ui.res.painterResource
import sl.gov.statistics.fieldmonitor.R
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import sl.gov.statistics.fieldmonitor.ui.theme.Amber
import sl.gov.statistics.fieldmonitor.ui.theme.Green
import sl.gov.statistics.fieldmonitor.ui.theme.Red

@Composable
fun StatusChip(status: String, overdue: Boolean = false) {
    val (label, color) = when {
        status == "RESOLVED" -> "Resolved" to Green
        overdue -> "Overdue" to Red
        else -> "Unresolved" to Amber
    }
    Text(
        text = label,
        color = if (color == Amber) Color.Black else Color.White,
        style = MaterialTheme.typography.labelMedium,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier
            .background(color, RoundedCornerShape(12.dp))
            .padding(horizontal = 10.dp, vertical = 4.dp),
    )
}

@Composable
fun StatTile(label: String, value: Int, color: Color, modifier: Modifier = Modifier, onClick: (() -> Unit)? = null) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.12f)),
        onClick = onClick ?: {},
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(value.toString(), style = MaterialTheme.typography.displaySmall, color = color, fontWeight = FontWeight.Bold)
            Text(label, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
fun LabelValue(label: String, value: String?) {
    if (value.isNullOrBlank()) return
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Text(label, style = MaterialTheme.typography.labelLarge, modifier = Modifier.width(150.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyLarge)
    }
}

data class Option(val id: Int?, val label: String)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DropdownField(
    label: String,
    options: List<Option>,
    selected: Int?,
    onSelect: (Option) -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    isError: Boolean = false,
) {
    var expanded by remember { mutableStateOf(false) }
    val current = options.firstOrNull { it.id == selected }?.label ?: ""
    ExposedDropdownMenuBox(expanded = expanded && enabled, onExpandedChange = { expanded = it }, modifier = modifier) {
        OutlinedTextField(
            value = current,
            onValueChange = {},
            readOnly = true,
            enabled = enabled,
            isError = isError,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.menuAnchor().fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = expanded && enabled, onDismissRequest = { expanded = false }) {
            options.forEach { opt ->
                DropdownMenuItem(text = { Text(opt.label) }, onClick = { onSelect(opt); expanded = false })
            }
        }
    }
}

/** A dropdown with a filter box: type part of the code or name to narrow a long list (hundreds of SAs). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SearchableDropdownField(
    label: String,
    options: List<Option>,
    selected: Int?,
    onSelect: (Option) -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    placeholder: String = "Type to filter",
    maxItems: Int = 80,
) {
    var expanded by remember { mutableStateOf(false) }
    val selectedLabel = options.firstOrNull { it.id != null && it.id == selected }?.label ?: ""
    var query by remember(selected, options) { mutableStateOf(selectedLabel) }
    val filtered = remember(query, options, selectedLabel) {
        val q = query.trim().lowercase()
        if (q.isEmpty() || q == selectedLabel.lowercase()) options.take(maxItems) else options.filter { it.label.lowercase().contains(q) }.take(maxItems)
    }
    ExposedDropdownMenuBox(expanded = expanded && enabled, onExpandedChange = { expanded = it }, modifier = modifier) {
        OutlinedTextField(
            value = query,
            onValueChange = { query = it; expanded = true },
            enabled = enabled,
            singleLine = true,
            label = { Text(label) },
            placeholder = { Text(placeholder) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryEditable, enabled).fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = expanded && enabled, onDismissRequest = { expanded = false; query = selectedLabel }) {
            if (filtered.isEmpty()) DropdownMenuItem(text = { Text("No match") }, onClick = { expanded = false }, enabled = false)
            filtered.forEach { opt ->
                DropdownMenuItem(text = { Text(opt.label) }, onClick = { onSelect(opt); query = opt.label; expanded = false })
            }
            if (options.size > filtered.size && query.trim().isEmpty()) DropdownMenuItem(text = { Text("${options.size - filtered.size} more: type to filter") }, onClick = {}, enabled = false)
        }
    }
}

@Composable
fun VSpace(dp: Int = 12) = Spacer(Modifier.height(dp.dp))

/** The 2026 Population and Housing Census emblem. */
@Composable
fun CensusLogo(size: Dp, modifier: Modifier = Modifier) {
    Image(
        painter = painterResource(R.drawable.census_logo),
        contentDescription = "2026 Population and Housing Census",
        modifier = modifier.size(size),
    )
}
