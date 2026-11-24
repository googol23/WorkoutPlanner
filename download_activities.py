#!/usr/bin/env python3
"""Export completed Garmin runs as privacy-filtered JSON for offline analysis."""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
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


def is_run(activity):
    kind = activity.get("activityType") or {}
    return isinstance(kind, dict) and kind.get("typeKey") == "running"


def recent_runs(api, limit):
    runs = []
    start = 0
    page_size = 20
    while len(runs) < limit:
        page = api.get_activities(start=start, limit=page_size, activitytype="running")
        if not isinstance(page, list):
            raise RuntimeError("Unexpected Garmin activities list response")
        for item in page:
            if not isinstance(item, dict):
                raise RuntimeError("Unexpected Garmin activity entry")
            if is_run(item) and item.get("activityId") and not item.get("inProgress"):
                runs.append(item)
                if len(runs) == limit:
                    break
        if len(page) < page_size:
            break
        start += len(page)
    return runs


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


def export_activity(api, listing, feedback=None):
    activity_id = listing["activityId"]
    unavailable = []
    summary = api.get_activity(str(activity_id))
    if not isinstance(summary, dict):
        raise RuntimeError(f"Unexpected activity summary for {activity_id}")
    if not is_run(summary) or summary.get("inProgress"):
        raise RuntimeError(f"Activity {activity_id} is not a completed running activity")
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
    return {
        "activity_id": activity_id,
        "activity_name": summary.get("activityName"),
        "activity_date": summary.get("startTimeLocal") or summary.get("startTimeGMT"),
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
    selection.add_argument("--limit", type=int, default=1, help="number of recent completed runs")
    selection.add_argument("--activity-id", type=int, help="export one completed running activity")
    parser.add_argument("--output", default="running_activities.json", help="output JSON path")
    parser.add_argument("--perceived-effort", type=int, help="perceived effort from 1 to 10")
    parser.add_argument("--fatigue", help="optional fatigue notes")
    parser.add_argument("--pain", help="optional pain notes")
    parser.add_argument("--comments", help="optional comments")
    args = parser.parse_args(argv)
    if args.limit < 1 or args.activity_id is not None and args.activity_id < 1:
        parser.error("--limit and --activity-id must be positive")
    if args.perceived_effort is not None and not 1 <= args.perceived_effort <= 10:
        parser.error("--perceived-effort must be from 1 to 10")
    try:
        api = authenticate()
        listings = ([{"activityId": args.activity_id}] if args.activity_id is not None
                    else recent_runs(api, args.limit))
        if not listings:
            raise RuntimeError("No completed running activities found")
        feedback = feedback_from_args(args)
        result = {
            "schema_version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "activities": [export_activity(api, item, feedback) for item in listings],
        }
        output = Path(args.output)
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        print(f"Exported {len(result['activities'])} run(s) to {output}")
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
