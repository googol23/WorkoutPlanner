package com.googol23.workoutplanner

import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.time.LocalDate
import java.util.Locale
import javax.net.ssl.HttpsURLConnection

data class GarminActivityPreview(
    val name: String,
    val activityType: String,
    val localDate: String,
    val durationSeconds: Long?,
    val distanceMeters: Double?,
)

object GarminPersonalClient {
    private const val HOST = "personal.connectapi.garmin.com"
    private const val TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
    private const val MAX_RESPONSE_BYTES = 2 * 1024 * 1024

    fun fetchRecentPreview(apiKey: String, today: LocalDate = LocalDate.now()): List<GarminActivityPreview> {
        val token = exchange(apiKey)
        val startDate = today.minusDays(13).toString()
        val endDate = today.toString()
        val query = "start=0&limit=20&startDate=${encode(startDate)}&endDate=${encode(endDate)}"
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
        return (0 until rows.length()).mapNotNull { index ->
            val row = rows.optJSONObject(index)
                ?: throw IllegalStateException("Garmin returned an unexpected activity entry.")
            if (row.optBoolean("inProgress", false)) return@mapNotNull null
            val type = row.optJSONObject("activityTypeDTO")?.optString("typeKey")
                ?: row.optJSONObject("activityType")?.optString("typeKey")
                ?: "unknown"
            GarminActivityPreview(
                name = row.optString("activityName").takeIf(String::isNotBlank) ?: "Garmin activity",
                activityType = type,
                localDate = row.optString("startTimeLocal").take(10).ifBlank { "Date unavailable" },
                durationSeconds = row.numberAsLong("duration"),
                distanceMeters = row.numberAsDouble("distance"),
            )
        }
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

    private fun request(method: String, path: String, authorization: String, accept: String): ByteArray {
        val connection = URL("https://$HOST$path").openConnection() as HttpsURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 20_000
            connection.readTimeout = 30_000
            connection.setRequestProperty("Authorization", authorization)
            connection.setRequestProperty("Accept", accept)
            val status = connection.responseCode
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
                    if (total > MAX_RESPONSE_BYTES) {
                        throw IllegalStateException("Garmin response exceeded the 2 MB preview limit.")
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
