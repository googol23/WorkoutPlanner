package com.googol23.workoutplanner

import android.content.Context
import android.util.AtomicFile
import org.json.JSONObject
import java.io.File

/** Keeps the synced Garmin export in app-private storage for later planning steps. */
class GarminActivityStore(context: Context) {
    private val file = AtomicFile(File(context.filesDir, "recent_activities.json"))

    fun save(export: JSONObject) {
        val bytes = (export.toString(2) + "\n").toByteArray(Charsets.UTF_8)
        var stream: java.io.FileOutputStream? = null
        try {
            stream = file.startWrite()
            stream.write(bytes)
            file.finishWrite(stream)
        } catch (error: Exception) {
            stream?.let(file::failWrite)
            throw error
        }
    }

    fun activityCount(): Int {
        if (!file.baseFile.exists()) return 0
        return try {
            file.openRead().bufferedReader(Charsets.UTF_8).use { reader ->
                JSONObject(reader.readText()).optJSONArray("activities")?.length() ?: 0
            }
        } catch (_: Exception) {
            0
        }
    }

    fun clear() {
        file.delete()
    }
}
