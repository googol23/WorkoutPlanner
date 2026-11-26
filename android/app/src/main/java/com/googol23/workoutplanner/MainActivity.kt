package com.googol23.workoutplanner

import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { WorkoutPlannerApp() }
    }
}

@Composable
private fun WorkoutPlannerApp() {
    val context = LocalContext.current
    val store = remember { ProfileStore(context) }
    val scope = rememberCoroutineScope()
    var profiles by remember { mutableStateOf(emptyList<AthleteProfile>()) }
    var selectedName by rememberSaveable { mutableStateOf("") }
    var message by rememberSaveable { mutableStateOf("Profiles are stored on this phone.") }
    var draft by remember { mutableStateOf(AthleteProfile("running", ActivityTypes.RUNNING, "", "")) }
    var sportMenuOpen by remember { mutableStateOf(false) }
    var profileMenuOpen by remember { mutableStateOf(false) }

    fun select(profile: AthleteProfile) {
        selectedName = profile.name
        draft = profile
    }

    fun updateProfiles(updated: List<AthleteProfile>) {
        profiles = updated.sortedBy { it.name }
        if (selectedName.isNotEmpty() && profiles.none { it.name == selectedName }) {
            selectedName = ""
        }
    }

    val exportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/json"),
    ) { uri: Uri? ->
        if (uri != null) scope.launch {
            runCatching {
                val json = ProfileJson.encode(profiles)
                withContext(Dispatchers.IO) {
                    context.contentResolver.openOutputStream(uri)?.bufferedWriter(Charsets.UTF_8)?.use { it.write(json) }
                        ?: error("Could not open the selected file.")
                }
            }.onSuccess { message = "Profiles exported." }
                .onFailure { message = it.message ?: "Export failed." }
        }
    }
    val importLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri: Uri? ->
        if (uri != null) scope.launch {
            runCatching {
                val imported = withContext(Dispatchers.IO) {
                    context.contentResolver.openInputStream(uri)?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }
                        ?: error("Could not read the selected file.")
                }
                ProfileJson.decode(imported)
            }.onSuccess { imported ->
                runCatching { withContext(Dispatchers.IO) { store.save(imported) } }
                    .onSuccess {
                        updateProfiles(imported)
                        selectedName = ""
                        draft = AthleteProfile("", ActivityTypes.RUNNING, "", "")
                        message = "Imported ${imported.size} profile(s)."
                    }
                    .onFailure { message = it.message ?: "Could not save imported profiles." }
            }.onFailure { message = it.message ?: "Import failed; existing profiles were kept." }
        }
    }

    androidx.compose.runtime.LaunchedEffect(Unit) {
        runCatching { withContext(Dispatchers.IO) { store.load() } }
            .onSuccess { loaded ->
                profiles = loaded
                if (loaded.isNotEmpty()) select(loaded.first())
                else message = "Add a profile or import athlete_profiles.json."
            }
            .onFailure { message = it.message ?: "Could not load saved profiles." }
    }

    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            Column(
                modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text("WorkoutPlanner", style = MaterialTheme.typography.headlineMedium)
                Text("Manage your local athlete profiles", style = MaterialTheme.typography.titleMedium)
                Text(message, style = MaterialTheme.typography.bodyMedium)

                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = {
                            selectedName = ""
                            draft = AthleteProfile("", ActivityTypes.RUNNING, "", "")
                            message = "Enter a new profile name, goals and availability."
                        }) { Text("New profile") }
                        OutlinedButton(onClick = { importLauncher.launch(arrayOf("application/json", "text/*")) }) {
                            Text("Import JSON")
                        }
                    }
                    OutlinedButton(
                        onClick = { exportLauncher.launch("athlete_profiles.json") },
                        enabled = profiles.isNotEmpty(),
                    ) { Text("Export JSON") }
                }

                if (profiles.isNotEmpty()) {
                    Column {
                        OutlinedButton(onClick = { profileMenuOpen = true }, modifier = Modifier.fillMaxWidth()) {
                            Text(if (selectedName.isEmpty()) "Select a profile" else "Editing: $selectedName")
                        }
                        DropdownMenu(expanded = profileMenuOpen, onDismissRequest = { profileMenuOpen = false }) {
                            profiles.forEach { profile ->
                                DropdownMenuItem(
                                    text = { Text("${profile.name} · ${profile.activityType}") },
                                    onClick = { select(profile); profileMenuOpen = false },
                                )
                            }
                        }
                    }
                }

                OutlinedTextField(
                    value = draft.name,
                    onValueChange = { draft = draft.copy(name = it.trim().lowercase().replace(' ', '_')) },
                    label = { Text("Profile name (for example, running)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )

                Column {
                    OutlinedButton(onClick = { sportMenuOpen = true }, modifier = Modifier.fillMaxWidth()) {
                        Text("Activity: ${draft.activityType}")
                    }
                    DropdownMenu(expanded = sportMenuOpen, onDismissRequest = { sportMenuOpen = false }) {
                        ActivityTypes.supported.forEach { sport ->
                            DropdownMenuItem(
                                text = { Text(sport) },
                                onClick = {
                                    draft = draft.copy(
                                        activityType = sport,
                                        preferredMachines = if (sport == ActivityTypes.STRENGTH) draft.preferredMachines else emptyList(),
                                        preferredExercises = if (sport == ActivityTypes.STRENGTH) draft.preferredExercises else emptyList(),
                                    )
                                    sportMenuOpen = false
                                },
                            )
                        }
                    }
                }

                ProfileField("Goals", draft.goals) { draft = draft.copy(goals = it) }
                ProfileField("Availability", draft.availability) { draft = draft.copy(availability = it) }
                ProfileField("Equipment", draft.equipment) { draft = draft.copy(equipment = it) }
                ProfileField("Constraints", draft.constraints) { draft = draft.copy(constraints = it) }
                ProfileField("Preferences", draft.preferences) { draft = draft.copy(preferences = it) }
                ProfileField("Recent feedback", draft.recentFeedback) { draft = draft.copy(recentFeedback = it) }
                ProfileField("Training background", draft.trainingBackground) { draft = draft.copy(trainingBackground = it) }
                ProfileField("Benchmarks", draft.benchmarks) { draft = draft.copy(benchmarks = it) }

                if (draft.activityType == ActivityTypes.STRENGTH) {
                    ProfileField("Preferred machines (comma-separated)", draft.preferredMachines.joinToString(", ")) {
                        draft = draft.copy(preferredMachines = commaValues(it))
                    }
                    ProfileField("Preferred exercises (comma-separated)", draft.preferredExercises.joinToString(", ")) {
                        draft = draft.copy(preferredExercises = commaValues(it))
                    }
                }

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = {
                        runCatching {
                            ProfileJson.validate(draft)
                            val updated = profiles.filterNot { it.name == selectedName || it.name == draft.name } + draft
                            scope.launch {
                                runCatching { withContext(Dispatchers.IO) { store.save(updated) } }
                                    .onSuccess {
                                        updateProfiles(updated)
                                        selectedName = draft.name
                                        message = "Saved ${draft.name} on this phone."
                                    }
                                    .onFailure { message = it.message ?: "Save failed." }
                            }
                        }.onFailure { message = it.message ?: "Profile is invalid." }
                    }) { Text("Save profile") }
                    if (selectedName.isNotEmpty()) {
                        OutlinedButton(onClick = {
                            val updated = profiles.filterNot { it.name == selectedName }
                            scope.launch {
                                runCatching { withContext(Dispatchers.IO) { if (updated.isEmpty()) context.deleteFile("athlete_profiles.json") else store.save(updated) } }
                                    .onSuccess {
                                        updateProfiles(updated)
                                        draft = AthleteProfile("", ActivityTypes.RUNNING, "", "")
                                        message = "Profile removed from this phone."
                                    }
                                    .onFailure { message = it.message ?: "Could not remove profile." }
                            }
                        }) { Text("Delete") }
                    }
                }
                Spacer(Modifier.height(8.dp))
            }
        }
    }
}

@Composable
private fun ProfileField(label: String, value: String, onValueChange: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        modifier = Modifier.fillMaxWidth(),
        minLines = 1,
        maxLines = 4,
    )
}

private fun commaValues(value: String): List<String> =
    value.split(',').map(String::trim).filter(String::isNotEmpty).distinct()
