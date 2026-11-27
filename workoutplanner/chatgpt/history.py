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

COMMON_METRICS = (
    "duration", "movingDuration", "distance", "elevationGain", "elevationLoss",
    "averageHR", "maxHR", "trainingEffect", "aerobicTrainingEffect",
    "anaerobicTrainingEffect", "activityTrainingLoad",
)
SPORT_METRIC_GROUPS = {
    "running": (
        ("averagePace", "averageSpeed"),
        ("averageRunCadence", "avgRunCadence"),
        ("averagePower", "avgPower"),
        ("normalizedPower", "normPower"),
        ("maxPower",),
        ("strideLength", "averageStrideLength"),
        ("groundContactTime",),
        ("verticalOscillation",),
    ),
    "cycling": (
        ("averageSpeed",),
        ("maxSpeed",),
        ("averagePower", "avgPower"),
        ("normalizedPower", "normPower"),
        ("maxPower",),
        ("averageBikeCadence", "avgBikeCadence"),
    ),
    "strength_training": (
        ("totalSets",), ("activeSets",), ("totalReps",), ("totalVolume",),
    ),
}
ZONE_FIELDS = ("zoneNumber", "secsInZone", "zoneLowBoundary", "zoneHighBoundary")
SPLIT_BASE_FIELDS = ("duration", "distance", "elevationGain", "elevationLoss", "averageHR")
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


def sport_for_key(key):
    return next((sport for sport, keys in SPORT_TYPE_KEYS.items() if key in keys), None)


def select_metric_groups(source, groups):
    selected = {}
    for aliases in groups:
        values = select_scalars(source, aliases)
        if values:
            selected.update(list(values.items())[:1])
    return selected


def activity_metric_groups(key):
    return SPORT_METRIC_GROUPS.get(sport_for_key(key), ())


def summarize_splits(source, key):
    if isinstance(source, dict):
        source = source.get("lapDTOs")
    if not isinstance(source, list):
        return []
    rows = []
    for item in islice(source, 3):
        row = select_scalars(item, SPLIT_BASE_FIELDS)
        row.update(select_metric_groups(item, activity_metric_groups(key)))
        if row:
            rows.append(row)
    return rows


def summarize_exercise_sets(source):
    if isinstance(source, dict):
        source = source.get("exerciseSets")
    if not isinstance(source, list):
        return []
    rows = []
    for item in islice(source, 8):
        if not isinstance(item, dict):
            continue
        row = select_scalars(item, EXERCISE_FIELDS)
        unit = select_scalars(item.get("weightUnit"), ("unitKey", "displayName"))
        if unit:
            row["weightUnit"] = unit
        exercises = select_rows(item.get("exercises"), ("name", "category"), 2)
        if exercises:
            row["exercises"] = exercises
        if row:
            rows.append(row)
    return rows


def summarize_activity(activity):
    summary = activity["summary"]
    key = activity_type_key(activity)
    source = dict(summary)
    nested = summary.get("summaryDTO")
    if isinstance(nested, dict):
        source.update(nested)
    metrics = select_scalars(source, COMMON_METRICS)
    metrics.update(select_metric_groups(source, activity_metric_groups(key)))
    result = {}
    day = calendar_day(activity_date(activity))
    if day:
        result["activity_date"] = day
    if key:
        result["activity_type"] = key
    result["summary"] = metrics

    zones = (("heart_rate_zones", activity.get("heart_rate_zones")),
             ("power_zones", activity.get("power_zones")))
    for field, source_rows in zones:
        if field == "power_zones" and sport_for_key(key) not in ("running", "cycling"):
            continue
        rows = []
        for item in islice(source_rows if isinstance(source_rows, list) else [], 7):
            row = select_scalars(item, ZONE_FIELDS)
            seconds = row.get("secsInZone", row.get("secondsInZone", 0))
            if row and isinstance(seconds, (int, float)) and seconds > 0:
                rows.append(row)
        if rows:
            result[field] = rows

    rows = summarize_splits(activity.get("splits"), key)
    if rows:
        result["first_splits"] = rows

    exercise_sets = activity.get("exercise_sets", summary.get("exerciseSets"))
    rows = summarize_exercise_sets(exercise_sets)
    if rows:
        result["first_exercise_sets"] = rows

    feedback = select_scalars(activity.get("subjective_feedback"), FEEDBACK_FIELDS)
    if feedback:
        result["subjective_feedback"] = feedback
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
