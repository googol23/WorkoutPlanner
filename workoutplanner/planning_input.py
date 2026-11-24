#!/usr/bin/env python3
"""Combine a Garmin activity export and athlete context into planning input JSON."""

import argparse
import json
import re
import sys
from pathlib import Path


STRENGTH_PREFERENCES = ("preferred_machines", "preferred_exercises")


def read_object(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def build_input(export, athlete, activity_type):
    if export.get("schema_version") != "1.0":
        raise ValueError("Garmin export schema_version must be 1.0")
    exported_at = export.get("exported_at")
    if not isinstance(exported_at, str) or not exported_at.strip():
        raise ValueError("Garmin export must include exported_at")
    activities = export.get("activities")
    if not isinstance(activities, list):
        raise ValueError("Garmin export activities must be a list")
    for index, activity in enumerate(activities, start=1):
        if not isinstance(activity, dict) or not isinstance(activity.get("summary"), dict):
            raise ValueError(f"Activity {index} must contain a summary object")
        activity_id = activity.get("activity_id")
        if type(activity_id) not in (str, int) or not activity_id:
            raise ValueError(f"Activity {index} must include activity_id")

    profile_type = athlete.get("activity_type")
    if (profile_type is not None or activity_type in ("cycling", "strength_training")) and profile_type != activity_type:
        raise ValueError(
            f'Athlete context must have "activity_type": "{activity_type}" and goals for that activity'
        )

    allowed_fields = {
        "activity_type", "goals", "availability", "constraints", "preferences",
        "recent_feedback", "training_background", "benchmarks", "equipment",
    }
    if activity_type == "strength_training":
        allowed_fields.update(STRENGTH_PREFERENCES)
    if athlete.keys() - allowed_fields:
        raise ValueError("Athlete context contains unknown fields")
    for field in ("goals", "availability"):
        value = athlete.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Athlete context {field} must be nonempty text")
    for field, value in athlete.items():
        if field in STRENGTH_PREFERENCES:
            if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
                raise ValueError(f"Athlete context {field} must be a list of nonempty strings")
        elif not isinstance(value, str) or not value.strip():
            raise ValueError("Athlete context values must be nonempty text")

    return {
        "schema_version": "1.0",
        "target_activity_type": activity_type,
        "athlete": athlete,
        "activity_history": export,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--activities", required=True, type=Path, help="Garmin activity export JSON")
    parser.add_argument("--athlete", required=True, type=Path, help="athlete context JSON")
    parser.add_argument("--activity-type", required=True, metavar="KEY", help="target activity type")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-z][a-z0-9_]*", args.activity_type) or args.activity_type == "all":
        parser.error("--activity-type must name a single target activity type")

    try:
        planning_input = build_input(read_object(args.activities), read_object(args.athlete), args.activity_type)
        print(json.dumps(planning_input, indent=2, ensure_ascii=False, allow_nan=False))
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
