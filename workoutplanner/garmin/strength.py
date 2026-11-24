"""Convert validated gym plans to typed Garmin strength workouts."""

import math
from difflib import get_close_matches

from garminconnect.exercises import BY_NAME, resolve
from garminconnect.workout import (
    StrengthWorkout,
    WorkoutSegment,
    create_strength_exercise_step,
    create_strength_rest_step,
)

from workoutplanner.workout_schema import InputError


def resolve_exercise(name):
    # Garmin uses “Hip Raise” for the standard floor glute bridge.
    catalog_name = "Hip Raise" if name.strip().casefold() == "glute bridge" else name
    entry = resolve(catalog_name)
    if entry is not None:
        return entry
    suggestions = get_close_matches(name, BY_NAME, n=3, cutoff=0.6)
    hint = f" Catalog matches: {', '.join(suggestions)}." if suggestions else ""
    raise InputError(f"Unknown Garmin exercise name {name!r}; use an exact catalog name.{hint}")


def build_strength_workout(source):
    steps = []
    for exercise in source["exercises"]:
        entry = resolve_exercise(exercise["name"])
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
