"""Encode a validated planner workout as the JSON accepted by Garmin Connect."""

import math
from itertools import count

from workoutplanner.workout_schema import duration


STEP_IDS = {"warmup": 1, "cooldown": 2, "interval": 3, "recovery": 4, "rest": 5, "repeat": 6}
CONDITION_IDS = {"time": 2, "iterations": 7, "reps": 10}
TARGET_IDS = {"no.target": 1, "power.zone": 2, "heart.rate.zone": 4, "pace.zone": 6}
SPORT_IDS = {"running": 1, "cycling": 2, "strength_training": 5}


def step_header(kind, order, condition, value):
    step_id = STEP_IDS[kind]
    condition_id = CONDITION_IDS[condition]
    return {
        "type": "RepeatGroupDTO" if kind == "repeat" else "ExecutableStepDTO",
        "stepOrder": order,
        "stepType": {"stepTypeId": step_id, "stepTypeKey": kind, "displayOrder": step_id},
        "endCondition": {"conditionTypeId": condition_id, "conditionTypeKey": condition,
                         "displayOrder": condition_id, "displayable": condition != "iterations"},
        "endConditionValue": float(value),
    }


def target_fields(kind="no.target", bounds=None):
    fields = {"targetType": {"workoutTargetTypeId": TARGET_IDS[kind], "workoutTargetTypeKey": kind,
                             "displayOrder": 1}}
    if bounds is not None:
        fields["targetValueOne"], fields["targetValueTwo"] = map(float, bounds)
    return fields


def timed_steps(steps, orders):
    result = []
    for step in steps:
        kind = step["type"]
        order = next(orders)
        if kind == "repeat":
            item = step_header(kind, order, "iterations", step["count"])
            item.update(numberOfIterations=step["count"], smartRepeat=False,
                        workoutSteps=timed_steps(step["steps"], orders))
        else:
            item = step_header("interval" if kind in ("ride", "run") else kind,
                               order, "time", step["duration_seconds"])
            target = step.get("target") or {}
            if "power_watts" in step:
                watts = step["power_watts"]
                fields = target_fields("power.zone", (watts["min"], watts["max"]))
            elif target.get("type") == "pace":
                fields = target_fields("pace.zone", (1000 / target["slow_seconds_per_km"],
                                                     1000 / target["fast_seconds_per_km"]))
            elif target.get("type") == "heart_rate":
                fields = target_fields("heart.rate.zone", (target["min_bpm"], target["max_bpm"]))
            else:
                fields = target_fields()
            item.update(fields)
            description = step.get("effort", step.get("description"))
            if description:
                item["description"] = description
        result.append(item)
    return result


def build_workout(source, *, sport="running"):
    if sport == "strength_training":
        from workoutplanner.garmin.strength import strength_steps
        steps = strength_steps(source)
        seconds = source["estimated_duration_seconds"]
        description = source["warmup"]
    else:
        steps = timed_steps(source["steps"], count(1))
        seconds = duration(source["steps"])
        description = source.get("description")
    sport_type = {"sportTypeId": SPORT_IDS[sport], "sportTypeKey": sport}
    payload = {"workoutName": source["name"], "estimatedDurationInSecs": math.ceil(seconds), "author": {},
               "sportType": {**sport_type, "displayOrder": SPORT_IDS[sport]},
               "workoutSegments": [{"segmentOrder": 1, "sportType": sport_type, "workoutSteps": steps}]}
    if description is not None:
        payload["description"] = description
    return payload
