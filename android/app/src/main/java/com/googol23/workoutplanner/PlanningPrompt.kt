package com.googol23.workoutplanner

import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate

/** Builds a compact, local-only planning input and review prompt. */
object PlanningPrompt {
    fun build(profiles: List<AthleteProfile>, export: JSONObject?, today: LocalDate = LocalDate.now()): Pair<String, String> {
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
        val prompt = "Create one safe, science-informed next workout for every profile below. " +
            "Use the shared 14-day history across all activity types to account for recent load and recovery. " +
            "Respect goals, time, equipment, constraints and preferences. Avoid inventing missing metrics. " +
            "Return rationale and one structured workout per profile; do not schedule or upload anything.\n\n" +
            input.toString(2)
        return input.toString(2) to prompt
    }
}
