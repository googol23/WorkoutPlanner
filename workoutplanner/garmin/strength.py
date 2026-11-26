"""Resolve catalog names and encode strength sets using local Garmin identifiers."""

from difflib import get_close_matches
from functools import cache
import json
from pathlib import Path

from workoutplanner.garmin.encoding import step_header, target_fields
from workoutplanner.workout_schema import InputError


@cache
def exercise_catalog():
    directory = Path(__file__).resolve().parents[2] / "skills/workout-planner/references"
    groups = json.loads((directory / "garmin-strength-exercises.json").read_text())
    overrides = json.loads((directory / "garmin-exercise-id-overrides.json").read_text())
    return {name: {"name": name, "category": category,
                   "exercise": overrides.get(name, name.upper().replace(" ", "_"))}
            for category, names in groups.items() for name in names}


def resolve_exercise(name):
    catalog_name = "Hip Raise" if name.strip().casefold() == "glute bridge" else name
    entries = exercise_catalog()
    if catalog_name in entries:
        return entries[catalog_name]
    suggestions = get_close_matches(name, entries, n=3, cutoff=0.6)
    hint = f" Catalog matches: {', '.join(suggestions)}." if suggestions else ""
    raise InputError(f"Unknown Garmin exercise name {name!r}; use an exact catalog name.{hint}")


def strength_steps(source):
    steps = []
    for exercise in source["exercises"]:
        entry = resolve_exercise(exercise["name"])
        reps = exercise["reps"]
        load = exercise.get("load")
        for index in range(exercise["sets"]):
            item = step_header("interval", len(steps) + 1, "reps", reps["min"])
            item.update(target_fields(), category=entry["category"], exerciseName=entry["exercise"],
                        description=f'{reps["min"]}–{reps["max"]} reps. {exercise["effort"]}')
            if load:
                kg = load["value"] * (0.45359237 if load["unit"] == "lb" else 1)
                item.update(weightValue=kg * 1000, weightUnit={"unitId": 8, "unitKey": "kilogram", "factor": 1000.0})
            steps.append(item)
            if index + 1 < exercise["sets"] and exercise["rest_seconds"]:
                rest = step_header("rest", len(steps) + 1, "time", exercise["rest_seconds"])
                steps.append({**rest, **target_fields()})
    return steps
