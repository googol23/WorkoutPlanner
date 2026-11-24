"""Select bounded activity context for a workout-generation prompt."""

from itertools import islice


MAX_ACTIVITIES = 12

METRICS = (
    "duration", "movingDuration", "elapsedDuration", "distance", "elevationGain",
    "elevationLoss", "averageSpeed", "maxSpeed", "averagePace", "averageHR", "maxHR",
    "averagePower", "avgPower", "maxPower", "normalizedPower", "normPower",
    "avgRunCadence", "averageRunCadence", "averageBikeCadence", "avgBikeCadence",
    "averageStrideLength", "groundContactTime", "verticalOscillation",
    "totalSets", "activeSets", "totalReps", "totalVolume",
    "aerobicTrainingEffect", "anaerobicTrainingEffect", "activityTrainingLoad",
    "startTimeLocal", "startTimeGMT", "temperature", "averageTemperature",
)
ZONE_FIELDS = ("zone", "zoneNumber", "secsInZone", "secondsInZone", "zoneLowBoundary",
               "zoneHighBoundary", "lowerBoundary", "upperBoundary")
EXERCISE_FIELDS = ("exerciseName", "name", "category", "setType", "reps", "repetitionCount",
                   "weight", "weightUnit", "load", "loadUnit", "duration")
FEEDBACK_FIELDS = ("perceived_effort", "fatigue", "pain", "comments")


def select_scalars(source, keys):
    if not isinstance(source, dict):
        return {}
    selected = {}
    for key in keys:
        value = source.get(key)
        if isinstance(value, str):
            selected[key] = value if len(value) <= 280 else value[:277] + "..."
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            selected[key] = value
    return selected


def select_rows(source, keys, limit):
    if not isinstance(source, list):
        return []
    return [row for item in islice(source, limit) if (row := select_scalars(item, keys))]


def summarize_activity(activity):
    summary = activity["summary"]
    metrics = select_scalars(summary, METRICS)
    metrics.update(select_scalars(summary.get("summaryDTO"), METRICS))
    result = select_scalars(activity, ("activity_id", "activity_date"))
    for field in ("activityTypeDTO", "activityType"):
        kind = select_scalars(summary.get(field), ("typeKey",))
        if kind:
            result["activity_type"] = kind["typeKey"]
            break
    result["summary"] = metrics
    for field in ("heart_rate_zones", "power_zones"):
        rows = select_rows(activity.get(field), ZONE_FIELDS, 10)
        if rows:
            result[field] = rows

    splits = activity.get("splits")
    if isinstance(splits, dict):
        splits = splits.get("lapDTOs")
    rows = select_rows(splits, METRICS, 6)
    if rows:
        result["first_splits"] = rows

    exercise_sets = activity.get("exercise_sets", summary.get("exerciseSets"))
    if isinstance(exercise_sets, dict):
        exercise_sets = exercise_sets.get("exerciseSets")
    rows = select_rows(exercise_sets, EXERCISE_FIELDS, 12)
    if rows:
        result["first_exercise_sets"] = rows

    feedback = select_scalars(activity.get("subjective_feedback"), FEEDBACK_FIELDS)
    if feedback:
        result["subjective_feedback"] = feedback
    unavailable = activity.get("unavailable_fields")
    if isinstance(unavailable, list):
        result["unavailable_fields"] = [
            field[:80] for field in unavailable[:16] if isinstance(field, str)
        ]
    return result


def activity_date(activity):
    summary = activity["summary"]
    nested = summary.get("summaryDTO")
    nested = nested if isinstance(nested, dict) else {}
    for value in (activity.get("activity_date"), summary.get("startTimeLocal"),
                  nested.get("startTimeLocal"), summary.get("startTimeGMT"),
                  nested.get("startTimeGMT")):
        if isinstance(value, str) and value:
            return value
    return ""


def compact_history(history):
    activities = history["activities"]
    recent = sorted(activities, key=activity_date, reverse=True)[:MAX_ACTIVITIES]
    return {
        "schema_version": history["schema_version"],
        "exported_at": history["exported_at"],
        "exported_activity_count": len(activities),
        "activities": [summarize_activity(activity) for activity in recent],
    }
