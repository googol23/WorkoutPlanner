package com.googol23.workoutplanner

import com.garmin.fit.ExerciseCategory
import com.garmin.fit.FitDecoder
import com.garmin.fit.FitMessages
import com.garmin.fit.LapMesg
import com.garmin.fit.SetMesg
import com.garmin.fit.SetType
import com.garmin.fit.Sport
import com.garmin.fit.TimeInZoneMesg
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.util.zip.ZipInputStream

data class GarminFitSections(
    val splits: JSONObject?,
    val heartRateZones: JSONArray?,
    val powerZones: JSONArray?,
    val exerciseSets: JSONObject?,
) {
    fun anyAvailable(): Boolean =
        splits != null || heartRateZones != null || powerZones != null || exerciseSets != null
}

/** Decodes only planner-relevant summaries from an original Garmin FIT archive. */
object GarminFitParser {
    private const val MAX_FIT_BYTES = 32 * 1024 * 1024
    private const val MAX_ARCHIVE_EXPANDED_BYTES = 34 * 1024 * 1024
    private const val SESSION_REFERENCE_MESG = 18

    fun decodeArchive(archive: ByteArray, activityType: String): GarminFitSections {
        val fitBytes = if (archive.startsWithZipSignature()) extractSingleFitFile(archive) else archive
        if (fitBytes.isEmpty() || fitBytes.size > MAX_FIT_BYTES) {
            throw IllegalStateException("Garmin FIT activity is empty or exceeds the 32 MB limit.")
        }
        val messages = try {
            FitDecoder().decode(ByteArrayInputStream(fitBytes))
        } catch (_: Exception) {
            throw IllegalStateException("Garmin returned a FIT activity that could not be decoded.")
        }
        val sessions = messages.sessionMesgs
        val singleSession = sessions.size == 1
        val splits = if (singleSession) splitRows(messages.lapMesgs, sessions[0].sport) else null
        val heartZones = if (singleSession) zones(messages.timeInZoneMesgs, sessions[0], true) else null
        val powerZones = if (singleSession) zones(messages.timeInZoneMesgs, sessions[0], false) else null
        val exerciseSets = if (activityType == ActivityTypes.STRENGTH) setRows(messages.setMesgs) else null
        return GarminFitSections(splits, heartZones, powerZones, exerciseSets)
    }

    private fun extractSingleFitFile(archive: ByteArray): ByteArray {
        var found: ByteArray? = null
        var fitCount = 0
        var expandedBytes = 0
        try {
            ZipInputStream(ByteArrayInputStream(archive)).use { zip ->
                while (true) {
                    val entry = zip.nextEntry ?: break
                    if (!entry.isDirectory) {
                        val buffer = ByteArray(8 * 1024)
                        val isFit = entry.name.lowercase().endsWith(".fit")
                        if (isFit) {
                            fitCount++
                            if (fitCount > 1) throw IllegalStateException("Expected one FIT file in Garmin's activity archive.")
                        }
                        val output = if (isFit) ByteArrayOutputStream() else null
                        while (true) {
                            val count = zip.read(buffer)
                            if (count < 0) break
                            expandedBytes += count
                            if (expandedBytes > MAX_ARCHIVE_EXPANDED_BYTES) {
                                throw IllegalStateException("Garmin FIT archive exceeds the 34 MB expanded size limit.")
                            }
                            if (isFit && output!!.size() + count > MAX_FIT_BYTES) {
                                throw IllegalStateException("Garmin FIT activity exceeds the 32 MB limit.")
                            }
                            output?.write(buffer, 0, count)
                        }
                        if (isFit) found = output!!.toByteArray()
                    }
                    zip.closeEntry()
                }
            }
        } catch (error: IllegalStateException) {
            throw error
        } catch (_: Exception) {
            throw IllegalStateException("Garmin returned an invalid FIT activity archive.")
        }
        if (fitCount != 1 || found == null) throw IllegalStateException("Expected one FIT file in Garmin's activity archive.")
        return found!!
    }

    private fun ByteArray.startsWithZipSignature(): Boolean =
        size >= 4 && this[0] == 0x50.toByte() && this[1] == 0x4b.toByte() &&
            (this[2] == 0x03.toByte() || this[2] == 0x05.toByte() || this[2] == 0x07.toByte()) &&
            (this[3] == 0x04.toByte() || this[3] == 0x06.toByte() || this[3] == 0x08.toByte())

    private fun splitRows(laps: List<LapMesg>, sessionSport: Sport?): JSONObject? {
        val rows = JSONArray()
        laps.forEach { lap ->
            val row = JSONObject()
            put(row, "distance", lap.totalDistance)
            put(row, "duration", lap.totalTimerTime)
            put(row, "elapsedDuration", lap.totalElapsedTime)
            put(row, "movingDuration", lap.totalMovingTime)
            put(row, "elevationGain", lap.totalAscent)
            put(row, "elevationLoss", lap.totalDescent)
            put(row, "averageHR", lap.avgHeartRate)
            put(row, "maxHR", lap.maxHeartRate)
            put(row, "averagePower", lap.avgPower)
            put(row, "maxPower", lap.maxPower)
            put(row, "normalizedPower", lap.normalizedPower)
            put(row, "averageSpeed", lap.enhancedAvgSpeed ?: lap.avgSpeed)
            put(row, "maxSpeed", lap.enhancedMaxSpeed ?: lap.maxSpeed)

            val sport = lap.sport ?: sessionSport
            val sportKey = sport?.let { Sport.getStringFromValue(it).lowercase() }
            var cadence = lap.avgRunningCadence
            if (cadence == null && sportKey == "running") cadence = lap.avgCadence
            if (cadence != null && (sportKey == null || sportKey == "running")) {
                put(row, "averageRunCadence", 2.0 * (cadence.toDouble() + (lap.avgFractionalCadence?.toDouble() ?: 0.0)))
            }
            if (row.length() > 0) rows.put(row)
        }
        return if (rows.length() > 0) JSONObject().put("lapDTOs", rows) else null
    }

    private fun zones(messages: List<TimeInZoneMesg>, session: com.garmin.fit.SessionMesg, heartRate: Boolean): JSONArray? {
        val referenceRows = messages.filter { message ->
            message.referenceMesg == SESSION_REFERENCE_MESG && zoneTimes(message, heartRate) != null
        }
        val times = when {
            referenceRows.size == 1 -> zoneTimes(referenceRows.single(), heartRate)
            else -> sessionZoneTimes(session, heartRate)
        } ?: return null
        val result = JSONArray()
        for (zone in 1 until times.size) {
            val seconds = times[zone] ?: continue
            result.put(JSONObject().put("zoneNumber", zone).put("secsInZone", seconds))
        }
        return result.takeIf { it.length() > 0 }
    }

    private fun zoneTimes(message: TimeInZoneMesg, heartRate: Boolean): Array<Float?>? =
        if (heartRate) message.timeInHrZone else message.timeInPowerZone

    private fun sessionZoneTimes(session: com.garmin.fit.SessionMesg, heartRate: Boolean): Array<Float?>? =
        if (heartRate) session.timeInHrZone else session.timeInPowerZone

    private fun setRows(sets: List<SetMesg>): JSONObject? {
        if (sets.isEmpty()) return null
        val records = JSONArray()
        sets.forEach { set ->
            val row = JSONObject()
            set.repetitions?.let { row.put("repetitionCount", it) }
            set.duration?.let { row.put("duration", it) }
            val categoryId = set.category?.firstOrNull()
            val subtypeId = set.categorySubtype?.firstOrNull()
            categoryId?.let {
                row.put("category", it)
                val category = ExerciseCategory.getStringFromValue(it)
                if (category.isNotBlank()) row.put("categoryName", category)
            }
            subtypeId?.let { row.put("categorySubtype", it) }
            if (categoryId != null && subtypeId != null) {
                exerciseName(categoryId, subtypeId)?.let { row.put("exerciseName", it) }
            }
            set.setType?.let { type ->
                SetType.getStringFromValue(type).takeIf(String::isNotBlank)?.let { row.put("setType", it) }
            }
            set.weight?.let {
                row.put("load", it)
                row.put("loadUnit", "kg")
            }
            if (row.length() > 0) records.put(row)
        }
        return if (records.length() > 0) JSONObject().put("source", "original_fit").put("exerciseSets", records) else null
    }

    private fun exerciseName(categoryId: Int, subtypeId: Int): String? {
        return try {
            val categoryName = ExerciseCategory.getStringFromValue(categoryId)
            if (categoryName.isBlank()) return null
            val className = categoryName.lowercase().split('_').joinToString("") { part ->
                part.replaceFirstChar { it.uppercase() }
            } + "ExerciseName"
            val enumClass = Class.forName("com.garmin.fit.$className")
            val method = enumClass.getMethod("getStringFromValue", Integer::class.java)
            val raw = method.invoke(null, subtypeId) as? String ?: return null
            raw.takeIf(String::isNotBlank)?.lowercase()?.split('_')?.joinToString(" ") { part ->
                part.replaceFirstChar { it.uppercase() }
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun put(target: JSONObject, key: String, value: Number?) {
        if (value != null && value.toDouble().isFinite()) target.put(key, value)
    }
}
