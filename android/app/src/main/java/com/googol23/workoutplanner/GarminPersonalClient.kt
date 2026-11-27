package com.googol23.workoutplanner

import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.time.LocalDate
import java.time.Instant
import java.time.format.DateTimeFormatter
import javax.net.ssl.HttpsURLConnection

data class GarminActivityPreview(
    val activityId: String,
    val name: String,
    val activityType: String,
    val localDate: String,
    val durationSeconds: Long?,
    val distanceMeters: Double?,
    val fitDetails: String,
)

data class GarminActivitySyncResult(
    val activities: List<GarminActivityPreview>,
    val export: JSONObject,
    val fitEnrichedActivityCount: Int,
)

object GarminPersonalClient {
    private const val HOST = "personal.connectapi.garmin.com"
    private const val TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
    private const val MAX_RESPONSE_BYTES = 2 * 1024 * 1024
    private const val MAX_FIT_ARCHIVE_BYTES = 34 * 1024 * 1024
    private const val MAX_SYNC_FIT_BYTES = 64 * 1024 * 1024
    private const val PAGE_SIZE = 20
    private const val MAX_SYNC_ACTIVITIES = 100
    private val privateField = Regex(
        "(?i)latitude|longitude|coordinate|polyline|geolocation|location|gps|position|" +
            "(^|[^a-z])(lat|lon|lng)([^a-z]|$)|lat$|lon$|lng$|point|map|" +
            "user|owner|person|account|profile|email|password|token|secret|credential|deviceid|activityid|" +
            "displayname|fullname|first(name)?|last(name)?|avatar|photo|image|url|address|ipaddress|externalid",
    )

    fun syncRecentActivities(apiKey: String, today: LocalDate = LocalDate.now()): GarminActivitySyncResult {
        val token = exchange(apiKey)
        val startDate = today.minusDays(13).toString()
        val endDate = today.toString()
        val listings = mutableListOf<JSONObject>()
        val seenIds = mutableSetOf<String>()
        var offset = 0
        var previousPageIds: List<String>? = null
        while (true) {
            val query = "start=$offset&limit=$PAGE_SIZE&startDate=${encode(startDate)}&endDate=${encode(endDate)}"
            val response = request(
                method = "GET",
                path = "/activitylist-service/activities/search/activities?$query",
                authorization = "Bearer $token",
                accept = "application/json",
            )
            val rows = try {
                JSONArray(response.toString(Charsets.UTF_8))
            } catch (_: Exception) {
                throw IllegalStateException("Garmin returned an unreadable activity list.")
            }
            val page = (0 until rows.length()).map { index ->
                rows.optJSONObject(index)
                    ?: throw IllegalStateException("Garmin returned an unexpected activity entry.")
            }
            val pageIds = page.mapNotNull { it.opt("activityId")?.toString() }
            if (page.size == PAGE_SIZE && pageIds == previousPageIds) {
                throw IllegalStateException("Garmin activity pagination repeated a page. Retry the sync later.")
            }
            previousPageIds = pageIds
            page.forEach { row ->
                if (row.optBoolean("inProgress", false)) return@forEach
                val id = row.opt("activityId")?.toString()
                    ?.takeIf { it.isNotEmpty() && it.all(Char::isDigit) }
                    ?: throw IllegalStateException("Garmin returned an activity without a valid ID.")
                if (seenIds.add(id)) listings += row
            }
            if (listings.size > MAX_SYNC_ACTIVITIES) {
                throw IllegalStateException("More than $MAX_SYNC_ACTIVITIES activities were found in 14 days. Narrow the sync window first.")
            }
            if (page.size < PAGE_SIZE) break
            offset += page.size
        }

        var fitBytesDownloaded = 0
        val exported = listings.map { listing ->
            val id = listing.get("activityId").toString()
            val detailBytes = request("GET", "/activity-service/activity/$id", "Bearer $token", "application/json")
            val detail = try {
                JSONObject(detailBytes.toString(Charsets.UTF_8))
            } catch (_: Exception) {
                throw IllegalStateException("Garmin returned unreadable detail for an activity.")
            }
            if (detail.opt("activityId")?.toString() != id || detail.optBoolean("inProgress", false)) {
                throw IllegalStateException("Garmin returned an unexpected or incomplete activity.")
            }
            val activityType = detail.optJSONObject("activityTypeDTO")?.optString("typeKey")
                ?: detail.optJSONObject("activityType")?.optString("typeKey")
                ?: listing.optJSONObject("activityTypeDTO")?.optString("typeKey")
                ?: listing.optJSONObject("activityType")?.optString("typeKey")
                ?: "unknown"
            val remainingFitBudget = MAX_SYNC_FIT_BYTES - fitBytesDownloaded
            val fitArchive = if (remainingFitBudget > 0) {
                request(
                    method = "GET",
                    path = "/download-service/files/activity/$id",
                    authorization = "Bearer $token",
                    accept = "application/zip, application/x-zip-compressed, application/octet-stream",
                    maxBytes = minOf(MAX_FIT_ARCHIVE_BYTES, remainingFitBudget),
                    optionalNotFound = true,
                ).also { fitBytesDownloaded += it.size }.takeIf { it.isNotEmpty() }
            } else {
                null
            }
            val fitSections = fitArchive?.let { archive ->
                runCatching { GarminFitParser.decodeArchive(archive, activityType) }.getOrNull()
            }
            makeExportRecord(id, listing, detail, activityType, fitSections)
        }
        val export = JSONObject()
            .put("schema_version", "1.0")
            .put("exported_at", DateTimeFormatter.ISO_INSTANT.format(Instant.now()))
            .put("activities", JSONArray(exported))
        val previews = exported.map(::previewFromExport)
        val fitCount = exported.count { record ->
            record.optJSONObject("splits") != null || record.optJSONArray("heart_rate_zones") != null ||
                record.optJSONArray("power_zones") != null || record.optJSONObject("exercise_sets") != null
        }
        return GarminActivitySyncResult(previews, export, fitCount)
    }

    private fun makeExportRecord(
        id: String,
        listing: JSONObject,
        detail: JSONObject,
        activityType: String,
        fit: GarminFitSections?,
    ): JSONObject {
        val start = detail.optString("startTimeLocal").ifBlank {
            detail.optJSONObject("summaryDTO")?.optString("startTimeLocal")?.ifBlank {
                listing.optString("startTimeLocal").ifBlank { detail.optString("startTimeGMT") }
            } ?: listing.optString("startTimeLocal")
        }
        val name = detail.optString("activityName").takeIf(String::isNotBlank)
            ?: listing.optString("activityName").takeIf(String::isNotBlank)
        val missing = JSONArray()
        missing.put("time_series")
        missing.put("workout_steps")
        missing.put("weather")
        if (fit?.exerciseSets == null) missing.put("exercise_sets")
        if (fit == null) missing.put("original_fit")
        if (fit?.splits == null) missing.put("splits")
        if (fit?.heartRateZones == null) missing.put("heart_rate_zones")
        if (fit?.powerZones == null) missing.put("power_zones")
        if (activityType == ActivityTypes.STRENGTH && fit?.exerciseSets == null) missing.put("exercise_sets")
        val exportDate: Any = start.takeIf(String::isNotBlank) ?: JSONObject.NULL
        val record = JSONObject()
            .put("activity_id", id)
            .put("activity_name", name ?: JSONObject.NULL)
            .put("activity_date", exportDate)
            .put("summary", safeJson(detail) as JSONObject)
            .put("time_series", JSONObject.NULL)
            .put("splits", fit?.splits ?: JSONObject.NULL)
            .put("workout_steps", JSONObject.NULL)
            .put("heart_rate_zones", fit?.heartRateZones ?: JSONObject.NULL)
            .put("power_zones", fit?.powerZones ?: JSONObject.NULL)
            .put("exercise_sets", fit?.exerciseSets ?: JSONObject.NULL)
            .put("weather", JSONObject.NULL)
            .put("subjective_feedback", JSONObject.NULL)
            .put("unavailable_fields", missing)
        return record
    }

    private fun safeJson(value: Any?): Any? = when (value) {
        is JSONObject -> JSONObject().also { output ->
            val keys = value.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                if (!privateField.containsMatchIn(key)) output.put(key, safeJson(value.get(key)))
            }
        }
        is JSONArray -> JSONArray().also { output ->
            for (index in 0 until value.length()) output.put(safeJson(value.get(index)))
        }
        else -> value
    }

    private fun previewFromExport(record: JSONObject): GarminActivityPreview {
        val summary = record.getJSONObject("summary")
        val type = summary.optJSONObject("activityTypeDTO")?.optString("typeKey")
            ?: summary.optJSONObject("activityType")?.optString("typeKey")
            ?: "unknown"
        val summaryDto = summary.optJSONObject("summaryDTO")
        val date = record.optString("activity_date").take(10).ifBlank { "Date unavailable" }
        val fitNotes = mutableListOf<String>()
        record.optJSONObject("splits")?.optJSONArray("lapDTOs")?.length()?.takeIf { it > 0 }?.let { fitNotes += "$it laps" }
        record.optJSONArray("heart_rate_zones")?.length()?.takeIf { it > 0 }?.let { fitNotes += "$it HR zones" }
        record.optJSONArray("power_zones")?.length()?.takeIf { it > 0 }?.let { fitNotes += "$it power zones" }
        record.optJSONObject("exercise_sets")?.optJSONArray("exerciseSets")?.length()?.takeIf { it > 0 }?.let { fitNotes += "$it sets" }
        return GarminActivityPreview(
            activityId = record.getString("activity_id"),
            name = record.optString("activity_name").takeIf(String::isNotBlank) ?: "Garmin activity",
            activityType = type,
            localDate = date,
            durationSeconds = summary.numberAsLong("duration") ?: summaryDto?.numberAsLong("duration"),
            distanceMeters = summary.numberAsDouble("distance") ?: summaryDto?.numberAsDouble("distance"),
            fitDetails = fitNotes.joinToString(", "),
        )
    }

    private fun exchange(apiKey: String): String {
        require(apiKey.isNotBlank() && apiKey.all { it.code in 0x21..0x7e } && apiKey.none(Char::isWhitespace)) {
            "Enter a valid Garmin Personal API key."
        }
        val response = request("POST", TOKEN_PATH, "ApiKey $apiKey", accept = "*/*")
        val token = response.toString(Charsets.US_ASCII).trim()
        require(TOKEN_PATTERN.matches(token)) {
            "Garmin did not return a valid access token. Check the Personal API key and its expiry."
        }
        return token
    }

    private fun request(
        method: String,
        path: String,
        authorization: String,
        accept: String,
        maxBytes: Int = MAX_RESPONSE_BYTES,
        optionalNotFound: Boolean = false,
    ): ByteArray {
        val connection = URL("https://$HOST$path").openConnection() as HttpsURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 20_000
            connection.readTimeout = 30_000
            connection.setRequestProperty("Authorization", authorization)
            connection.setRequestProperty("Accept", accept)
            val status = connection.responseCode
            if (optionalNotFound && status in listOf(HttpURLConnection.HTTP_NO_CONTENT, HttpURLConnection.HTTP_NOT_FOUND)) {
                return ByteArray(0)
            }
            if (status == HttpURLConnection.HTTP_UNAUTHORIZED || status == HttpURLConnection.HTTP_FORBIDDEN) {
                throw IllegalStateException("Garmin denied access. Check that the Personal API key is valid and has not expired.")
            }
            if (status !in 200..299) throw IllegalStateException("Garmin returned HTTP $status.")
            return connection.inputStream.use { input ->
                val output = ByteArrayOutputStream()
                val buffer = ByteArray(8 * 1024)
                var total = 0
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    total += count
                    if (total > maxBytes) {
                        throw IllegalStateException("Garmin response exceeded the ${maxBytes / (1024 * 1024)} MB size limit.")
                    }
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
        } catch (error: IllegalStateException) {
            throw error
        } catch (error: IllegalArgumentException) {
            throw IllegalStateException(error.message ?: "Garmin returned invalid data.")
        } catch (_: Exception) {
            throw IllegalStateException("Could not connect to Garmin. Check the phone's internet connection and try again.")
        } finally {
            connection.disconnect()
        }
    }

    private fun encode(value: String): String = URLEncoder.encode(value, Charsets.UTF_8.name())

    private fun JSONObject.numberAsLong(key: String): Long? = when (val value = opt(key)) {
        is Number -> value.toLong()
        else -> null
    }

    private fun JSONObject.numberAsDouble(key: String): Double? = when (val value = opt(key)) {
        is Number -> value.toDouble().takeIf(Double::isFinite)
        else -> null
    }

    private val TOKEN_PATTERN = Regex("[A-Za-z0-9_-]+(?:\\.[A-Za-z0-9_-]+){2}")
}
