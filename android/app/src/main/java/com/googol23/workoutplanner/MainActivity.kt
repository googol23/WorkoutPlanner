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
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalDate

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
    var screen by rememberSaveable { mutableStateOf("profiles") }
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
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { screen = "profiles" }) { Text("Profiles") }
                    OutlinedButton(onClick = { screen = "garmin" }) { Text("Garmin") }
                    OutlinedButton(onClick = { screen = "planning" }) { Text("Plan") }
                }

                if (screen == "garmin") {
                    GarminConnectionScreen()
                } else if (screen == "planning") {
                    PlanningPreviewScreen(profiles)
                } else {
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
}

@Composable
private fun PlanningPreviewScreen(profiles: List<AthleteProfile>) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val activityStore = remember { GarminActivityStore(context) }
    var input by remember { mutableStateOf("") }
    var prompt by remember { mutableStateOf("") }
    var generated by remember { mutableStateOf("") }
    var status by rememberSaveable { mutableStateOf("Preview stays on this phone. Nothing is sent to ChatGPT.") }
    var loading by remember { mutableStateOf(false) }
    var connected by remember { mutableStateOf(ChatGptPlanClient.hasCredentials(context)) }
    var accountEmail by remember { mutableStateOf(ChatGptPlanClient.email(context).orEmpty()) }
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Review planning input", style = MaterialTheme.typography.titleMedium)
        Text("Builds one shared 14-day activity history and one workout request for every saved profile. This preview is local only.")
        Button(onClick = {
            scope.launch {
                loading = true
                runCatching {
                    withContext(Dispatchers.IO) {
                        val built = PlanningPrompt.build(profiles, activityStore.load())
                        built
                    }
                }.onSuccess { (json, draftPrompt) ->
                    input = json
                    prompt = draftPrompt
                    status = "Preview ready: ${profiles.size} profile(s), ${runCatching { org.json.JSONObject(json).getJSONArray("recent_activities").length() }.getOrDefault(0)} recent activity record(s)."
                }.onFailure { status = it.message ?: "Could not build the preview." }
                loading = false
            }
        }, enabled = !loading && profiles.isNotEmpty()) { Text(if (loading) "Building…" else "Build preview") }
        Text(status, style = MaterialTheme.typography.bodyMedium)
        if (profiles.isEmpty()) Text("Save at least one profile in Profiles first.")
        Text("ChatGPT plan connection", style = MaterialTheme.typography.titleSmall)
        Text("Uses ChatGPT plan allowance when OpenAI enables it for this app and account. No API key or separate API billing fallback is used. Your profiles and activity metrics are sent to OpenAI only when you tap Generate.")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = {
                scope.launch {
                    loading = true
                    runCatching { ChatGptPlanClient.signIn(context) { step -> status = step } }
                        .onSuccess { connected = true; accountEmail = it.email; status = "ChatGPT connected. Plan usage permission was granted." }
                        .onFailure { status = it.message ?: "ChatGPT sign-in failed." }
                    loading = false
                }
            }, enabled = !loading) { Text(if (loading) "Connecting…" else if (connected) "Reconnect ChatGPT" else "Continue with ChatGPT") }
            if (connected) OutlinedButton(onClick = {
                runCatching { ChatGptPlanClient.disconnect(context) }
                    .onSuccess { connected = false; accountEmail = ""; generated = ""; status = "ChatGPT connection removed from this phone." }
                    .onFailure { status = it.message ?: "Could not remove ChatGPT connection." }
            }, enabled = !loading) { Text("Disconnect") }
        }
        if (connected) Text("Connected${accountEmail.takeIf(String::isNotBlank)?.let { ": $it" }.orEmpty()}")
        if (input.isNotEmpty()) {
            Text("Compact planning input", style = MaterialTheme.typography.titleSmall)
            OutlinedTextField(input, {}, readOnly = true, modifier = Modifier.fillMaxWidth(), minLines = 6, maxLines = 12)
            Text("Draft prompt", style = MaterialTheme.typography.titleSmall)
            OutlinedTextField(prompt, {}, readOnly = true, modifier = Modifier.fillMaxWidth(), minLines = 10, maxLines = 20)
            Button(onClick = {
                scope.launch {
                    loading = true
                    status = "Sending the preview to OpenAI with ChatGPT plan usage…"
                    runCatching { ChatGptPlanClient.generate(context, prompt) }
                        .onSuccess { generated = it; status = "Response received. Review it before using it; no Garmin upload was performed." }
                        .onFailure { status = it.message ?: "ChatGPT generation failed." }
                    loading = false
                }
            }, enabled = connected && !loading && prompt.isNotBlank()) { Text(if (loading) "Generating…" else "Generate with ChatGPT plan") }
            if (generated.isNotBlank()) {
                Text("Workout response for review", style = MaterialTheme.typography.titleSmall)
                OutlinedTextField(generated, {}, readOnly = true, modifier = Modifier.fillMaxWidth(), minLines = 8, maxLines = 24)
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

@Composable
private fun GarminConnectionScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val secretStore = remember { GarminSecretStore(context) }
    val activityStore = remember { GarminActivityStore(context) }
    var keyInput by rememberSaveable { mutableStateOf("") }
    var hasKey by remember { mutableStateOf(false) }
    var syncedCount by remember { mutableStateOf(0) }
    var loading by remember { mutableStateOf(false) }
    var status by rememberSaveable { mutableStateOf("Garmin Personal API key is stored only on this phone.") }
    var activities by remember { mutableStateOf(emptyList<GarminActivityPreview>()) }

    androidx.compose.runtime.LaunchedEffect(Unit) {
        hasKey = withContext(Dispatchers.IO) { secretStore.hasKey() }
        syncedCount = withContext(Dispatchers.IO) { activityStore.activityCount() }
        if (syncedCount > 0) status = "$syncedCount activity record(s) are saved on this phone."
    }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Garmin Personal API", style = MaterialTheme.typography.titleMedium)
        Text(
            "Enter the Personal API key from Garmin Connect. WorkoutPlanner encrypts it with Android Keystore. " +
                "Sync reads completed activities from the last 14 days, downloads available FIT files, and saves " +
                "summary metrics, laps, zones and strength sets locally. Garmin may not provide every FIT file. " +
                "No workouts are uploaded.",
            style = MaterialTheme.typography.bodyMedium,
        )
        OutlinedTextField(
            value = keyInput,
            onValueChange = { keyInput = it },
            label = { Text("Garmin Personal API key") },
            visualTransformation = PasswordVisualTransformation(),
            singleLine = true,
            enabled = !loading,
            modifier = Modifier.fillMaxWidth(),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                val candidate = keyInput.trim()
                scope.launch {
                    loading = true
                    runCatching { withContext(Dispatchers.IO) { secretStore.save(candidate) } }
                        .onSuccess {
                            keyInput = ""
                            hasKey = true
                            status = "Encrypted Garmin key saved on this phone."
                        }
                        .onFailure { status = it.message ?: "Could not save the key." }
                    loading = false
                }
            }, enabled = !loading && keyInput.isNotBlank()) { Text("Save key") }
            OutlinedButton(onClick = {
                scope.launch {
                    loading = true
                    runCatching {
                        withContext(Dispatchers.IO) {
                            val key = secretStore.read()
                            val synced = GarminPersonalClient.syncRecentActivities(key, LocalDate.now())
                            activityStore.save(synced.export)
                            synced
                        }
                    }.onSuccess { result ->
                        activities = result.activities
                        syncedCount = result.activities.size
                        status = "Synced ${result.activities.size} completed activity record(s); FIT details decoded for " +
                            "${result.fitEnrichedActivityCount} record(s). Saved to app-private storage."
                    }.onFailure { status = it.message ?: "Garmin connection failed." }
                    loading = false
                }
            }, enabled = !loading && hasKey) {
                Text(if (loading) "Syncing…" else "Sync last 14 days")
            }
        }
        if (hasKey) {
            OutlinedButton(onClick = {
                scope.launch {
                    loading = true
                    runCatching { withContext(Dispatchers.IO) { secretStore.clear() } }
                        .onSuccess {
                            hasKey = false
                            activities = emptyList()
                            status = "Garmin key removed from this phone."
                        }
                        .onFailure { status = it.message ?: "Could not remove the key." }
                    loading = false
                }
            }, enabled = !loading) { Text("Remove saved key") }
        }
        if (syncedCount > 0) {
            OutlinedButton(onClick = {
                scope.launch {
                    loading = true
                    runCatching { withContext(Dispatchers.IO) { activityStore.clear() } }
                        .onSuccess {
                            syncedCount = 0
                            activities = emptyList()
                            status = "Synced activity history removed from this phone."
                        }
                        .onFailure { status = it.message ?: "Could not remove synced history." }
                    loading = false
                }
            }, enabled = !loading) { Text("Remove synced history") }
        }
        Text(status, style = MaterialTheme.typography.bodyMedium)
        if (activities.isNotEmpty()) {
            Text("Recent preview", style = MaterialTheme.typography.titleSmall)
            activities.forEach { activity ->
                val duration = activity.durationSeconds?.let { seconds ->
                    val minutes = seconds / 60
                    if (minutes >= 60) " · ${minutes / 60}h ${minutes % 60}m" else " · ${minutes}m"
                }.orEmpty()
                val distance = activity.distanceMeters?.let { " · ${"%.1f".format(it / 1000.0)} km" }.orEmpty()
                val fitDetails = activity.fitDetails.takeIf(String::isNotBlank)?.let { " · FIT: $it" }.orEmpty()
                Text("${activity.localDate} · ${activity.activityType}: ${activity.name}$duration$distance$fitDetails")
            }
            Text(
                "The local JSON keeps the summary and available FIT-derived laps, zones and strength exercise sets. " +
                    "FIT coverage depends on Garmin availability; unavailable fields stay marked in the export.",
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}
