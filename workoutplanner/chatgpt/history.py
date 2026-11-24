"""Select bounded activity context for a workout-generation prompt."""

from datetime import date
from itertools import islice


MAX_ACTIVITIES = 12
MAX_OTHER_ACTIVITIES = 3
SPORT_TYPE_KEYS = {
    "running": {"running", "trail_running", "treadmill_running", "track_running",
                "indoor_running", "ultra_run", "virtual_running"},
    "cycling": {"cycling", "road_biking", "mountain_biking", "gravel_cycling",
                "indoor_cycling", "virtual_ride", "cyclocross", "track_cycling",
                "e_bike_fitness", "e_bike_mountain", "bmx"},
    "strength_training": {"strength_training"},
}

METRICS = (
    "duration", "movingDuration", "elapsedDuration", "distance", "elevationGain",
    "elevationLoss", "averageSpeed", "maxSpeed", "averagePace", "averageHR", "maxHR",
    "averagePower", "avgPower", "maxPower", "normalizedPower", "normPower",
    "avgRunCadence", "averageRunCadence", "averageBikeCadence", "avgBikeCadence",
    "averageStrideLength", "groundContactTime", "verticalOscillation",
    "totalSets", "activeSets", "totalReps", "totalVolume",
    "aerobicTrainingEffect", "anaerobicTrainingEffect", "activityTrainingLoad",
    "temperature", "averageTemperature",
)
ZONE_FIELDS = ("zone", "zoneNumber", "secsInZone", "secondsInZone", "zoneLowBoundary",
               "zoneHighBoundary", "lowerBoundary", "upperBoundary")
EXERCISE_FIELDS = ("exerciseName", "name", "category", "setType", "reps", "repetitionCount",
                   "weight", "weightUnit", "weightInGrams", "load", "loadUnit", "duration")
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


def activity_type_key(activity):
    for field in ("activityTypeDTO", "activityType"):
        kind = select_scalars(activity["summary"].get(field), ("typeKey",))
        if kind and kind["typeKey"]:
            return kind["typeKey"]
    return None


def summarize_exercise_sets(source):
    if isinstance(source, dict):
        source = source.get("exerciseSets")
    if not isinstance(source, list):
        return []
    rows = []
    for item in islice(source, 12):
        if not isinstance(item, dict):
            continue
        row = select_scalars(item, EXERCISE_FIELDS)
        unit = select_scalars(item.get("weightUnit"), ("unitKey", "displayName", "factor"))
        if unit:
            row["weightUnit"] = unit
        exercises = select_rows(item.get("exercises"), ("name", "category"), 3)
        if exercises:
            row["exercises"] = exercises
        if row:
            rows.append(row)
    return rows


def summarize_activity(activity):
    summary = activity["summary"]
    metrics = select_scalars(summary, METRICS)
    metrics.update(select_scalars(summary.get("summaryDTO"), METRICS))
    result = {}
    day = calendar_day(activity_date(activity))
    if day:
        result["activity_date"] = day
    key = activity_type_key(activity)
    if key:
        result["activity_type"] = key
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
    rows = summarize_exercise_sets(exercise_sets)
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


def calendar_day(value):
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return None


def compact_history(history, sport):
    activities = history["activities"]
    recent = sorted(activities, key=activity_date, reverse=True)
    sport_keys = SPORT_TYPE_KEYS[sport]
    target, other = [], []
    for activity in recent:
        if activity_type_key(activity) in sport_keys:
            target.append(activity)
        else:
            other.append(activity)
    # Keep target sessions first so reducing the byte budget drops other sports first.
    selected_other = other[:MAX_OTHER_ACTIVITIES]
    selected = target[:MAX_ACTIVITIES - len(selected_other)] + selected_other
    summaries = []
    for number, activity in enumerate(selected, start=1):
        summary = summarize_activity(activity)
        summary["session"] = number
        summary["history_role"] = "target_sport" if summary.get("activity_type") in sport_keys else "other"
        summaries.append(summary)
    return {
        "schema_version": history["schema_version"],
        "exported_on": calendar_day(history["exported_at"]),
        "exported_activity_count": len(activities),
        "target_activity_count": len(target),
        "activities": summaries,
    }
