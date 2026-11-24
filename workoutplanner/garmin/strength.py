"""Convert validated gym plans to typed Garmin strength workouts."""

import math

from garminconnect.exercises import resolve
from garminconnect.workout import (
    StrengthWorkout,
    WorkoutSegment,
    create_strength_exercise_step,
    create_strength_rest_step,
)

from workoutplanner.workout_schema import InputError


def build_strength_workout(source):
    steps = []
    for exercise in source["exercises"]:
        name = exercise["name"]
        entry = resolve(name)
        if entry is None:
            raise InputError(f"Unknown Garmin exercise name {name!r}; use an exact catalog name")
        reps = exercise["reps"]
        load = exercise.get("load")
        weight_kg = None if load is None else load["value"] * (0.45359237 if load["unit"] == "lb" else 1)
        description = f'{reps["min"]}–{reps["max"]} reps. {exercise["effort"]}'
        for index in range(exercise["sets"]):
            steps.append(create_strength_exercise_step(
                entry["category"], len(steps) + 1, reps["min"],
                exercise_name=entry["exercise"], weight_kg=weight_kg,
                description=description,
            ))
            if index + 1 < exercise["sets"] and exercise["rest_seconds"]:
                steps.append(create_strength_rest_step(exercise["rest_seconds"], len(steps) + 1))
    return StrengthWorkout(
        workoutName=source["name"],
        description=source["warmup"],
        estimatedDurationInSecs=math.ceil(source["estimated_duration_seconds"]),
        workoutSegments=[WorkoutSegment(
            segmentOrder=1,
            sportType={"sportTypeId": 5, "sportTypeKey": "strength_training"},
            workoutSteps=steps,
        )],
    )
