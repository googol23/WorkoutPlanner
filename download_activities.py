#!/usr/bin/env python3
"""Export completed Garmin activities as privacy-filtered JSON for offline analysis."""

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from garminconnect import (
    GarminConnectAuthenticationError, GarminConnectConnectionError,
    GarminConnectNotFoundError, GarminConnectTooManyRequestsError,
)

from upload_workouts import authenticate


# Drop structured identity, location and credential data at every nesting level.
PRIVATE_KEY = re.compile(
    r"latitude|longitude|coordinate|polyline|geolocation|location|gps|position|"
    r"(^|[^a-z])(lat|lon|lng)([^a-z]|$)|lat$|lon$|lng$|point|map|"
    r"user|owner|person|account|"
    r"profile|email|password|token|secret|credential|deviceid|activityid|"
    r"displayname|fullname|first(name)?|last(name)?|avatar|photo|image|"
    r"url|address|ipaddress|externalid",
    re.IGNORECASE,
)


def safe(value):
    """Remove private structured fields without changing recorded metric values."""
    if isinstance(value, dict):
        return {key: safe(item) for key, item in value.items()
                if isinstance(key, str) and not PRIVATE_KEY.search(key)}
    if isinstance(value, list):
        return [safe(item) for item in value]
    return value


def type_key(activity):
    for field in ("activityTypeDTO", "activityType"):
        kind = activity.get(field)
        key = kind.get("typeKey") if isinstance(kind, dict) else None
        if isinstance(key, str) and key:
            return key
    return None


def matches_type(key, activity_type):
    return key is not None and (activity_type == "all" or key == activity_type)


def collect_activities(page, activity_type, seen, bounds=None):
    if not isinstance(page, list):
        raise RuntimeError("Unexpected Garmin activities list response")
    for item in page:
        if not isinstance(item, dict):
            raise RuntimeError("Unexpected Garmin activity entry")
        activity_id = item.get("activityId")
        if not activity_id or item.get("inProgress") or not matches_type(type_key(item), activity_type):
            continue
        if bounds:
            local_start = item.get("startTimeLocal")
            if not isinstance(local_start, str):
                raise RuntimeError(f"Missing local start time for activity {activity_id}")
            if not bounds[0] <= datetime.fromisoformat(local_start).date() <= bounds[1]:
                continue
        if str(activity_id) not in seen:
            seen.add(str(activity_id))
            yield item


def recent_activities(api, limit, activity_type):
    activities = []
    seen = set()
    start = 0
    page_size = 20
    # The existing running command uses Garmin's server-side running filter.
    server_type = "running" if activity_type == "running" else None
    while True:
        page = api.get_activities(start=start, limit=page_size, activitytype=server_type)
        for item in collect_activities(page, activity_type, seen):
            activities.append(item)
            if len(activities) == limit:
                return activities
        if len(page) < page_size:
            return activities
        start += len(page)


def recent_runs(api, limit):
    return recent_activities(api, limit, "running")


def activities_in_range(api, bounds, activity_type):
    start, end = bounds
    page = api.get_activities_by_date(start.isoformat(), end.isoformat())
    return list(collect_activities(page, activity_type, set(), bounds))


def parse_time_range(value):
    parts = value.split("..")
    if len(parts) != 2 or any(not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", part) for part in parts):
        raise argparse.ArgumentTypeError("use YYYY-MM-DD..YYYY-MM-DD")
    try:
        start, end = map(date.fromisoformat, parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("time range dates must be valid calendar dates") from exc
    if start > end:
        raise argparse.ArgumentTypeError("time range start must be on or before its end")
    return start, end


def series(details):
    if not isinstance(details, dict):
        return None
    descriptors = details.get("metricDescriptors")
    samples = details.get("activityDetailMetrics")
    if not isinstance(descriptors, list) or not isinstance(samples, list):
        return None
    metrics = {}
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            continue
        name, index = descriptor.get("key"), descriptor.get("metricsIndex")
        if not isinstance(name, str) or PRIVATE_KEY.search(name) or type(index) is not int or index < 0:
            continue
        metrics[index] = safe(descriptor)
    return {
        "metric_descriptors": list(metrics.values()),
        "samples": [
            {"metrics": {metrics[i]["key"]: value for i, value in enumerate(row["metrics"])
                         if i in metrics and value is not None}}
            for row in samples if isinstance(row, dict) and isinstance(row.get("metrics"), list)
        ],
    }


def optional(api, method, activity_id, unavailable, **kwargs):
    call = getattr(api, method, None)
    if call is None:
        unavailable.append(method)
        return None
    try:
        result = call(activity_id, **kwargs)
    except GarminConnectNotFoundError:
        unavailable.append(method)
        return None
    if result is None or result == {} or result == []:
        unavailable.append(method)
        return None
    return result


def export_activity(api, listing, feedback=None, *, activity_type="running"):
    activity_id = listing["activityId"]
    unavailable = []
    summary = api.get_activity(str(activity_id))
    if not isinstance(summary, dict):
        raise RuntimeError(f"Unexpected activity summary for {activity_id}")
    key = type_key(summary) or type_key(listing)
    if not matches_type(key, activity_type) or summary.get("inProgress"):
        description = "activity" if activity_type == "all" else f"{activity_type} activity"
        raise RuntimeError(f"Activity {activity_id} is not a completed {description}")
    details = optional(api, "get_activity_details", str(activity_id), unavailable, maxpoly=0)
    time_series = series(details)
    if time_series is None:
        unavailable.append("time_series")
    sections = {
        "splits": "get_activity_splits",
        "workout_steps": "get_activity_step_details",
        "heart_rate_zones": "get_activity_hr_in_timezones",
        "power_zones": "get_activity_power_in_timezones",
        "weather": "get_activity_weather",
    }
    data = {key: optional(api, method, str(activity_id), unavailable) for key, method in sections.items()}
    if key == "strength_training":
        method = "get_activity_exercise_sets"
        exercise_sets = optional(api, method, str(activity_id), unavailable)
        if isinstance(exercise_sets, dict) and exercise_sets.get("exerciseSets") == []:
            unavailable.append(method)
            exercise_sets = None
        data["exercise_sets"] = exercise_sets
    summary_fields = summary.get("summaryDTO")
    if not isinstance(summary_fields, dict):
        summary_fields = {}
    return {
        "activity_id": activity_id,
        "activity_name": summary.get("activityName") or listing.get("activityName"),
        "activity_date": (summary.get("startTimeLocal") or summary_fields.get("startTimeLocal")
                          or listing.get("startTimeLocal") or summary.get("startTimeGMT")
                          or summary_fields.get("startTimeGMT") or listing.get("startTimeGMT")),
        "summary": safe(summary),
        **{key: safe(value) for key, value in data.items()},
        "time_series": time_series,
        "subjective_feedback": feedback,
        "unavailable_fields": unavailable,
    }


def feedback_from_args(args):
    feedback = {}
    for key in ("perceived_effort", "fatigue", "pain", "comments"):
        value = getattr(args, key)
        if value is not None:
            feedback[key] = value
    return feedback or None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--limit", type=int, default=1, help="number of recent completed activities")
    selection.add_argument("--activity-id", type=int, help="export one completed activity")
    selection.add_argument("--time-range", type=parse_time_range, metavar="START..END",
                           help="inclusive activity-local dates, in YYYY-MM-DD format")
    parser.add_argument("--activity-type", default="running", metavar="KEY",
                        help="exact Garmin type key or all (default: running)")
    parser.add_argument("--output", help="output JSON path (default: <activity-type>_activities.json)")
    parser.add_argument("--perceived-effort", type=int, help="perceived effort from 1 to 10")
    parser.add_argument("--fatigue", help="optional fatigue notes")
    parser.add_argument("--pain", help="optional pain notes")
    parser.add_argument("--comments", help="optional comments")
    args = parser.parse_args(argv)
    if args.limit < 1 or args.activity_id is not None and args.activity_id < 1:
        parser.error("--limit and --activity-id must be positive")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", args.activity_type):
        parser.error("--activity-type must be a lowercase Garmin type key or all")
    if args.perceived_effort is not None and not 1 <= args.perceived_effort <= 10:
        parser.error("--perceived-effort must be from 1 to 10")
    try:
        api = authenticate()
        if args.activity_id is not None:
            listings = [{"activityId": args.activity_id}]
        elif args.time_range:
            listings = activities_in_range(api, args.time_range, args.activity_type)
        else:
            listings = recent_activities(api, args.limit, args.activity_type)
        if not listings:
            description = "activities" if args.activity_type == "all" else f"{args.activity_type} activities"
            raise RuntimeError(f"No completed {description} found")
        feedback = feedback_from_args(args)
        result = {
            "schema_version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "activities": [
                export_activity(api, item, feedback, activity_type=args.activity_type)
                for item in listings
            ],
        }
        output = Path(args.output or f"{args.activity_type}_activities.json")
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        print(f"Exported {len(result['activities'])} activity record(s) to {output}")
        return 0
    except (OSError, ValueError, RuntimeError, EOFError,
            GarminConnectAuthenticationError, GarminConnectConnectionError,
            GarminConnectTooManyRequestsError, GarminConnectNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
