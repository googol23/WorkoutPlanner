package com.googol23.workoutplanner

import android.content.Context
import android.util.AtomicFile
import java.io.File

class ProfileStore(context: Context) {
    private val file = AtomicFile(File(context.filesDir, "athlete_profiles.json"))

    fun load(): List<AthleteProfile> {
        if (!file.baseFile.exists()) return emptyList()
        return ProfileJson.decode(file.openRead().bufferedReader(Charsets.UTF_8).use { it.readText() })
    }

    fun save(profiles: List<AthleteProfile>) {
        val bytes = ProfileJson.encode(profiles).toByteArray(Charsets.UTF_8)
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
}
