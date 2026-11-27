package com.googol23.workoutplanner

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate

/** Builds a compact, local-only planning input and review prompt. */
object PlanningPrompt {
    fun build(context: Context, profiles: List<AthleteProfile>, export: JSONObject?, today: LocalDate = LocalDate.now()): Pair<String, String> {
        require(profiles.isNotEmpty()) { "Save at least one athlete profile first." }
        val start = today.minusDays(13)
        val activities = export?.optJSONArray("activities") ?: JSONArray()
        val selected = mutableListOf<Pair<LocalDate, JSONObject>>()
        for (i in 0 until activities.length()) {
            val row = activities.optJSONObject(i) ?: continue
            val day = row.optString("activity_date").take(10)
            val date = runCatching { LocalDate.parse(day) }.getOrNull() ?: continue
            if (date < start || date > today) continue
            val summary = row.optJSONObject("summary") ?: JSONObject()
            val compact = JSONObject().put("date", day)
                .put("activity_type", summary.optJSONObject("activityTypeDTO")?.optString("typeKey") ?: "unknown")
                .put("name", row.optString("activity_name"))
            val metrics = JSONObject()
            listOf("duration", "movingDuration", "distance", "averageHR", "maxHR", "averagePower", "maxPower", "normalizedPower", "elevationGain", "aerobicTrainingEffect", "anaerobicTrainingEffect", "activityTrainingLoad", "totalSets", "activeSets", "totalReps", "totalVolume").forEach { key ->
                if (summary.has(key)) metrics.put(key, summary.opt(key))
                summary.optJSONObject("summaryDTO")?.let { if (it.has(key)) metrics.put(key, it.opt(key)) }
            }
            compact.put("summary", metrics)
            row.optJSONObject("splits")?.optJSONArray("lapDTOs")?.let { compact.put("laps", JSONArray((0 until minOf(6, it.length())).map(it::getJSONObject))) }
            row.optJSONArray("heart_rate_zones")?.let { compact.put("heart_rate_zones", JSONArray((0 until minOf(10, it.length())).map(it::getJSONObject))) }
            row.optJSONArray("power_zones")?.let { compact.put("power_zones", JSONArray((0 until minOf(10, it.length())).map(it::getJSONObject))) }
            row.optJSONObject("exercise_sets")?.optJSONArray("exerciseSets")?.let { sets ->
                compact.put("exercise_sets", JSONArray((0 until minOf(12, sets.length())).map(sets::getJSONObject)))
            }
            row.optJSONArray("unavailable_fields")?.let { compact.put("unavailable_fields", it) }
            row.optJSONObject("subjective_feedback")?.let { compact.put("subjective_feedback", it) }
            selected += date to compact
        }
        // Keep the newest 42 records regardless of Garmin's returned ordering.
        val recent = JSONArray(selected.sortedByDescending { it.first }.take(42).map { it.second })
        val profileJson = JSONObject()
        profiles.forEach { profile ->
            val root = JSONObject(ProfileJson.encode(listOf(profile))).getJSONObject(profile.name)
            profileJson.put(profile.name, root)
        }
        val input = JSONObject().put("schema_version", "1.0")
            .put("as_of", today.toString()).put("history_start", start.toString())
            .put("profiles", profileJson).put("recent_activities", recent)
        val sports = profiles.map { it.activityType }.distinct()
        val outputReferences = mapOf(
            ActivityTypes.RUNNING to "references/running-output.md",
            ActivityTypes.CYCLING to "references/cycling-output.md",
            ActivityTypes.STRENGTH to "references/strength_training-output.md",
        )
        val skillPaths = buildList {
            add("SKILL.md")
            sports.forEach { sport ->
                require(outputReferences.containsKey(sport)) { "Unsupported activity type: $sport" }
                add("subskills/$sport/SKILL.md")
                add("references/${sport}-evidence.md")
                add(outputReferences.getValue(sport))
            }
        }
        val skillText = skillPaths.joinToString("\\n\\n") { path ->
            runCatching {
                context.assets.open(path).bufferedReader(Charsets.UTF_8).use { it.readText() }
            }.getOrElse { error ->
                throw IllegalStateException("WorkoutPlanner skill file is missing: $path", error)
            }
        }
        val prompt = "Follow the WorkoutPlanner coordinator and each profile's activity skill below. " +
            "Use the shared 14-day history across all activity types to judge load and recovery, then generate one next-session option per profile for the coming seven-day planning window. " +
            "The athlete may choose none or one option; do not assume every option will be performed. Respect each profile's goals, time, equipment, constraints and preferences. " +
            "Do not invent missing metrics. Treat study findings as bounded evidence, cite relevant source IDs and links in the rationale, and follow each exact JSON output contract. " +
            "Return rationale separately from a JSON workout bundle with priority and one plan (or null if deferred) per profile. Do not schedule or upload anything.\\n\\n" +
            skillText + "\\n\\n# Input data\\n" + input.toString(2)
        return input.toString(2) to prompt
    }
}
