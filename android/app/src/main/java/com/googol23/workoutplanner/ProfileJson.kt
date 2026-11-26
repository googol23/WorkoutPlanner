package com.googol23.workoutplanner

import org.json.JSONArray
import org.json.JSONObject

object ProfileJson {
    private val profileName = Regex("[a-z][a-z0-9_-]{0,47}")
    private val allowedFields = setOf(
        "goals", "availability", "constraints", "preferences", "recent_feedback",
        "training_background", "benchmarks", "equipment",
        "activity_type", "preferred_machines", "preferred_exercises",
    )

    fun encode(profiles: List<AthleteProfile>): String {
        require(profiles.isNotEmpty()) { "Add at least one profile before exporting." }
        require(profiles.map { it.name }.distinct().size == profiles.size) { "Profile names must be unique." }
        val root = JSONObject()
        profiles.forEach { profile ->
            validate(profile)
            val value = JSONObject()
                .put("activity_type", profile.activityType)
                .put("goals", profile.goals.trim())
                .put("availability", profile.availability.trim())
            listOf(
                "constraints" to profile.constraints,
                "preferences" to profile.preferences,
                "recent_feedback" to profile.recentFeedback,
                "training_background" to profile.trainingBackground,
                "benchmarks" to profile.benchmarks,
                "equipment" to profile.equipment,
            ).forEach { (key, text) -> if (text.isNotBlank()) value.put(key, text.trim()) }
            if (profile.activityType == ActivityTypes.STRENGTH) {
                putList(value, "preferred_machines", profile.preferredMachines)
                putList(value, "preferred_exercises", profile.preferredExercises)
            }
            root.put(profile.name, value)
        }
        return root.toString(2) + "\n"
    }

    fun decode(json: String): List<AthleteProfile> {
        val root = JSONObject(json)
        require(root.length() > 0) { "The profile file must contain at least one profile." }
        val profiles = mutableListOf<AthleteProfile>()
        val names = root.keys()
        while (names.hasNext()) {
            val name = names.next()
            require(profileName.matches(name)) { "Profile names must be lowercase letters, digits, _ or - (max 48 characters)." }
            val value = root.optJSONObject(name)
                ?: throw IllegalArgumentException("Profile '$name' must be a JSON object.")
            val unknown = value.keys().asSequence().filterNot { it in allowedFields }.toList()
            require(unknown.isEmpty()) { "Profile '$name' has unsupported fields: ${unknown.joinToString()}" }

            val sport = requiredText(value, "activity_type")
            require(sport in ActivityTypes.supported) { "Profile '$name' has an unsupported activity_type." }
            val profile = AthleteProfile(
                name = name,
                activityType = sport,
                goals = requiredText(value, "goals"),
                availability = requiredText(value, "availability"),
                constraints = optionalText(value, "constraints"),
                preferences = optionalText(value, "preferences"),
                recentFeedback = optionalText(value, "recent_feedback"),
                trainingBackground = optionalText(value, "training_background"),
                benchmarks = optionalText(value, "benchmarks"),
                equipment = optionalText(value, "equipment"),
                preferredMachines = stringList(value, "preferred_machines"),
                preferredExercises = stringList(value, "preferred_exercises"),
            )
            require(sport == ActivityTypes.STRENGTH ||
                ("preferred_machines" !in value && "preferred_exercises" !in value)) {
                "Machine and exercise preferences are only valid for strength profiles."
            }
            validate(profile)
            profiles += profile
        }
        return profiles.sortedBy { it.name }
    }

    fun validate(profile: AthleteProfile) {
        require(profileName.matches(profile.name)) {
            "Use a lowercase profile name such as 'running' or 'strength_gym'."
        }
        require(profile.activityType in ActivityTypes.supported) { "Choose running, cycling or strength training." }
        require(profile.goals.isNotBlank()) { "Goals are required." }
        require(profile.availability.isNotBlank()) { "Availability is required." }
        if (profile.activityType == ActivityTypes.STRENGTH) {
            require(profile.preferredMachines.none(String::isBlank)) { "Machine preferences cannot contain empty entries." }
            require(profile.preferredExercises.none(String::isBlank)) { "Exercise preferences cannot contain empty entries." }
        } else {
            require(profile.preferredMachines.isEmpty() && profile.preferredExercises.isEmpty()) {
                "Machine and exercise preferences are only available for strength training."
            }
        }
    }

    private fun putList(target: JSONObject, key: String, values: List<String>) {
        val cleaned = values.map(String::trim).filter(String::isNotEmpty).distinct()
        if (cleaned.isNotEmpty()) target.put(key, JSONArray(cleaned))
    }

    private fun requiredText(value: JSONObject, key: String): String {
        val text = optionalText(value, key)
        require(text.isNotBlank()) { "'$key' is required and must be nonempty text." }
        return text
    }

    private fun optionalText(value: JSONObject, key: String): String {
        if (!value.has(key)) return ""
        val raw = value.get(key)
        require(raw is String) { "'$key' must be text." }
        return raw
    }

    private fun stringList(value: JSONObject, key: String): List<String> {
        if (!value.has(key)) return emptyList()
        val array = value.get(key) as? JSONArray
            ?: throw IllegalArgumentException("'$key' must be a list of text values.")
        return (0 until array.length()).map { index ->
            val item = array.get(index) as? String
                ?: throw IllegalArgumentException("'$key' must contain only text values.")
            require(item.isNotBlank()) { "'$key' cannot contain empty values." }
            item.trim()
        }
    }
}
