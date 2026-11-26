package com.googol23.workoutplanner

data class AthleteProfile(
    val name: String,
    val activityType: String,
    val goals: String,
    val availability: String,
    val constraints: String = "",
    val preferences: String = "",
    val recentFeedback: String = "",
    val trainingBackground: String = "",
    val benchmarks: String = "",
    val equipment: String = "",
    val preferredMachines: List<String> = emptyList(),
    val preferredExercises: List<String> = emptyList(),
)

object ActivityTypes {
    const val RUNNING = "running"
    const val CYCLING = "cycling"
    const val STRENGTH = "strength_training"

    val supported = listOf(RUNNING, CYCLING, STRENGTH)
}
