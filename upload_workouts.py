#!/usr/bin/env python3
"""Validate, upload and optionally schedule JSON running workouts."""

import argparse
import json
import math
import re
import sys
from datetime import date
from getpass import getpass
from pathlib import Path

from garminconnect import (
    Garmin, GarminConnectAuthenticationError, GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)
from garminconnect.workout import (
    CustomHeartRateTarget,
    CustomPowerTarget,
    CyclingWorkout,
    PaceTarget,
    RunningWorkout,
    WorkoutSegment,
    create_cooldown_step,
    create_interval_step,
    create_recovery_step,
    create_repeat_group,
    create_targeted_interval_step,
    create_warmup_step,
)

TOKEN_DIR = Path.home() / ".garminconnect"
SPORT = {"sportTypeId": 1, "sportTypeKey": "running"}
CYCLING_SPORT = {"sportTypeId": 2, "sportTypeKey": "cycling"}
STEP_TYPES = {"warmup", "run", "interval", "recovery", "cooldown"}


class InputError(ValueError):
    """Invalid interchange-format workout."""


def fields(obj, required, optional, where):
    if not isinstance(obj, dict):
        raise InputError(f"{where} must be an object")
    missing = required - obj.keys()
    extra = obj.keys() - required - optional
    if missing or extra:
        raise InputError(f"{where}: missing {sorted(missing)}; unsupported {sorted(extra)}")


def positive(value, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise InputError(f"{where} must be a positive number")
    return value


def validate_step(step, where, depth=0):
    fields(step, {"type"}, {"duration_seconds", "target", "count", "steps", "description"}, where)
    kind = step["type"]
    if kind == "repeat":
        if depth >= 5:
            raise InputError(f"{where}: repeat nesting too deep")
        fields(step, {"type", "count", "steps"}, set(), where)
        if type(step["count"]) is not int or not 2 <= step["count"] <= 100:
            raise InputError(f"{where}.count must be an integer from 2 to 100")
        validate_steps(step["steps"], where + ".steps", depth + 1)
        return
    if kind not in STEP_TYPES:
        raise InputError(f"{where}.type must be warmup, run, interval, recovery, cooldown or repeat")
    fields(step, {"type", "duration_seconds"}, {"target", "description"}, where)
    positive(step["duration_seconds"], where + ".duration_seconds")
    if "description" in step and (not isinstance(step["description"], str) or not step["description"].strip()):
        raise InputError(f"{where}.description must be nonempty text")
    target = step.get("target")
    if target is None:
        return
    fields(target, {"type"}, {"slow_seconds_per_km", "fast_seconds_per_km", "min_bpm", "max_bpm"}, where + ".target")
    if target["type"] == "none":
        fields(target, {"type"}, set(), where + ".target")
    elif target["type"] == "pace":
        fields(target, {"type", "slow_seconds_per_km", "fast_seconds_per_km"}, set(), where + ".target")
        slow = positive(target["slow_seconds_per_km"], where + ".target.slow_seconds_per_km")
        fast = positive(target["fast_seconds_per_km"], where + ".target.fast_seconds_per_km")
        if slow < fast:
            raise InputError(f"{where}: slow pace must be >= fast pace")
    elif target["type"] == "heart_rate":
        fields(target, {"type", "min_bpm", "max_bpm"}, set(), where + ".target")
        low, high = target["min_bpm"], target["max_bpm"]
        if type(low) is not int or type(high) is not int or not 1 <= low <= high <= 250:
            raise InputError(f"{where}: heart rate must be whole bpm in ascending order (1–250)")
    else:
        raise InputError(f"{where}.target.type must be none, pace or heart_rate")


def validate_steps(steps, where, depth=0):
    if not isinstance(steps, list) or not steps:
        raise InputError(f"{where} must be a nonempty list")
    for index, step in enumerate(steps):
        validate_step(step, f"{where}[{index}]", depth)


def read_plan(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputError(f"Cannot read JSON plan: {exc}") from exc
    return data


def load_plan(path):
    return validate_plan(read_plan(path))


def validate_plan(data):
    if isinstance(data, dict) and data.get("sport") == "cycling":
        return validate_cycling_plan(data)
    fields(data, {"schema_version", "sport", "timezone", "units", "workouts"}, set(), "plan")
    if data["schema_version"] != "1.0" or data["sport"] != "running":
        raise InputError("Only schema_version 1.0 and sport running are supported")
    if not isinstance(data["timezone"], str) or not data["timezone"].strip():
        raise InputError("timezone must be a nonempty IANA timezone name")
    fields(data["units"], {"duration", "pace", "heart_rate"}, set(), "units")
    if data["units"] != {"duration": "seconds", "pace": "seconds_per_km", "heart_rate": "bpm"}:
        raise InputError("units must be seconds, seconds_per_km and bpm")
    workouts = data["workouts"]
    if not isinstance(workouts, list) or not workouts:
        raise InputError("workouts must be a nonempty list")
    names = set()
    for index, workout in enumerate(workouts):
        where = f"workouts[{index}]"
        fields(workout, {"name", "steps", "week", "total_duration_seconds"}, {"scheduled_date", "description"}, where)
        if type(workout["week"]) is not int or workout["week"] < 1:
            raise InputError(f"{where}.week must be a positive integer")
        name = workout["name"]
        if not isinstance(name, str) or not name.strip():
            raise InputError(f"{where}.name must be nonempty text")
        if name in names:
            raise InputError(f"duplicate workout name in file: {name}")
        names.add(name)
        if "description" in workout and not isinstance(workout["description"], str):
            raise InputError(f"{where}.description must be text")
        if "scheduled_date" in workout:
            value = workout["scheduled_date"]
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise InputError(f"{where}.scheduled_date must be YYYY-MM-DD")
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise InputError(f"{where}.scheduled_date is not a valid date") from exc
        validate_steps(workout["steps"], where + ".steps")
        if positive(workout["total_duration_seconds"], where + ".total_duration_seconds") != duration(workout["steps"]):
            raise InputError(f"{where}.total_duration_seconds does not match the steps")
    return workouts


def validate_cycling_plan(data):
    fields(data, {"schema_version", "sport", "workouts"}, set(), "cycling plan")
    if data["schema_version"] != "1.0":
        raise InputError("Cycling plan schema_version must be 1.0")
    workouts = data["workouts"]
    if not isinstance(workouts, list) or not workouts:
        raise InputError("workouts must be a nonempty list")
    names = set()
    for workout in workouts:
        fields(workout, {"name", "total_duration_seconds", "steps"}, {"scheduled_date"}, "cycling workout")
        name = workout["name"]
        if not isinstance(name, str) or not name.strip() or name in names:
            raise InputError("Cycling workout names must be nonempty and unique")
        names.add(name)
        if "scheduled_date" in workout:
            day = workout["scheduled_date"]
            if not isinstance(day, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day):
                raise InputError("scheduled_date must be YYYY-MM-DD")
            date.fromisoformat(day)
        steps = workout["steps"]
        if not isinstance(steps, list) or not steps:
            raise InputError("Cycling steps must be a nonempty list")
        for step in steps:
            fields(step, {"type", "duration_seconds", "effort"}, {"power_watts"}, "cycling step")
            if step["type"] not in ("warmup", "ride", "recovery", "cooldown"):
                raise InputError("Cycling step type must be warmup, ride, recovery or cooldown")
            positive(step["duration_seconds"], "cycling step duration_seconds")
            if not isinstance(step["effort"], str) or not step["effort"].strip():
                raise InputError("Cycling step effort must be nonempty text")
            if "power_watts" in step:
                watts = step["power_watts"]
                fields(watts, {"min", "max"}, set(), "power_watts")
                if positive(watts["min"], "minimum watts") > positive(watts["max"], "maximum watts"):
                    raise InputError("Maximum watts must be at least minimum watts")
        if positive(workout["total_duration_seconds"], "total_duration_seconds") != duration(steps):
            raise InputError("Cycling total_duration_seconds does not match the steps")
    return workouts


def duration(steps):
    return sum(step["count"] * duration(step["steps"]) if step["type"] == "repeat" else step["duration_seconds"] for step in steps)


def build_workout(source, *, sport="running"):
    order = 0

    def convert(steps):
        nonlocal order
        result = []
        for step in steps:
            order += 1
            current_order = order
            kind = step["type"]
            if kind == "repeat":
                children = convert(step["steps"])
                result.append(create_repeat_group(step["count"], children, current_order))
                continue
            seconds = step["duration_seconds"]
            target = step.get("target")
            intensity = None
            if target is not None and target["type"] == "pace":
                intensity = PaceTarget(
                    lower_limit=1000 / target["slow_seconds_per_km"],
                    upper_limit=1000 / target["fast_seconds_per_km"],
                )
            elif target is not None and target["type"] == "heart_rate":
                intensity = CustomHeartRateTarget(lower_limit=target["min_bpm"], upper_limit=target["max_bpm"])
            if "power_watts" in step:
                watts = step["power_watts"]
                intensity = CustomPowerTarget(lower_limit=watts["min"], upper_limit=watts["max"])
            if kind in {"run", "interval", "ride"}:
                item = create_targeted_interval_step(seconds, current_order, target=intensity) if intensity else create_interval_step(seconds, current_order)
            else:
                helper = {"warmup": create_warmup_step, "recovery": create_recovery_step, "cooldown": create_cooldown_step}[kind]
                item = helper(seconds, current_order)
                if intensity:
                    item.targetType = {"workoutTargetTypeId": intensity.target_type, "workoutTargetTypeKey": intensity.target_type_key, "displayOrder": 1}
                    item.targetValueOne = intensity.lower_limit
                    item.targetValueTwo = intensity.upper_limit
            description = step.get("effort", step.get("description"))
            if description:
                item.description = description
            result.append(item)
        return result

    model, segment_sport = (CyclingWorkout, CYCLING_SPORT) if sport == "cycling" else (RunningWorkout, SPORT)
    return model(
        workoutName=source["name"],
        description=source.get("description"),
        estimatedDurationInSecs=math.ceil(duration(source["steps"])),
        workoutSegments=[WorkoutSegment(segmentOrder=1, sportType=segment_sport, workoutSteps=convert(source["steps"]))],
    )


def authenticate():
    try:
        api = Garmin()
        api.login(str(TOKEN_DIR))
        print("Authenticated using saved tokens.")
        return api
    except Exception as exc:
        # Authentication errors can indicate missing/expired tokens; other failures must not prompt for credentials.
        from garminconnect import GarminConnectAuthenticationError
        if not isinstance(exc, (GarminConnectAuthenticationError, FileNotFoundError)):
            raise
    email = input("Garmin email: ").strip()
    if not email:
        raise InputError("email is required")
    password = getpass("Garmin password: ")
    api = Garmin(email=email, password=password, prompt_mfa=lambda: input("Garmin MFA code: ").strip())
    password = None
    api.login(str(TOKEN_DIR))
    print("Authenticated; reusable tokens stored outside this project.")
    return api


def existing_workouts(api):
    found = {}
    start = 0
    while True:
        page = api.get_workouts(start=start, limit=100, my_workouts_only=True)
        if not isinstance(page, list):
            raise RuntimeError("Unexpected Garmin workout list response")
        for entry in page:
            if isinstance(entry, dict) and entry.get("workoutName"):
                found.setdefault(entry["workoutName"], []).append(entry)
        if len(page) < 100:
            break
        start += len(page)
    return found


def existing_schedule(api, dates):
    found = set()
    for year, month in sorted({(date.fromisoformat(day).year, date.fromisoformat(day).month) for day in dates}):
        response = api.get_scheduled_workouts(year, month)
        if not isinstance(response, dict) or not isinstance(response.get("calendarItems"), list):
            raise RuntimeError("Unexpected Garmin calendar response; refusing to schedule")
        for item in response["calendarItems"]:
            if not isinstance(item, dict) or item.get("itemType") != "workout":
                continue
            workout = item.get("workout") or {}
            workout_id = item.get("workoutId") or workout.get("workoutId")
            day = item.get("date") or item.get("calendarDate")
            if workout_id is not None and isinstance(day, str):
                found.add((str(workout_id), day[:10]))
    return found


def upload_plan(api, workouts, schedule=False, *, sport="running"):
    library = existing_workouts(api)
    dates = [workout["scheduled_date"] for workout in workouts if "scheduled_date" in workout] if schedule else []
    calendar = existing_schedule(api, dates) if dates else set()
    for source in workouts:
        name = source["name"]
        matches = library.get(name, [])
        if len(matches) > 1:
            raise RuntimeError(f"Multiple existing workouts named {name!r}; resolve ambiguity manually")
        if matches:
            workout_id = matches[0].get("workoutId")
            if not workout_id:
                raise RuntimeError(f"Existing workout {name!r} has no ID")
            print(f"Already uploaded: {name} (ID {workout_id}); skipping upload")
        else:
            upload = api.upload_cycling_workout if sport == "cycling" else api.upload_running_workout
            result = upload(build_workout(source, sport=sport))
            workout_id = result.get("workoutId") if isinstance(result, dict) else None
            if not workout_id:
                raise RuntimeError(f"Upload of {name!r} returned no workoutId; check Garmin before retrying")
            print(f"Uploaded: {name} (ID {workout_id})")
            library[name] = [{"workoutId": workout_id, "workoutName": name}]
        if schedule and "scheduled_date" in source:
            key = (str(workout_id), source["scheduled_date"])
            if key in calendar:
                print(f"Already scheduled: {name} on {source['scheduled_date']}")
            else:
                api.schedule_workout(workout_id, source["scheduled_date"])
                calendar.add(key)
                print(f"Scheduled: {name} on {source['scheduled_date']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", nargs="?", help="JSON plan file")
    parser.add_argument("--login", action="store_true", help="authenticate and store tokens")
    parser.add_argument("--dry-run", action="store_true", help="validate and preview without network or login")
    parser.add_argument("--schedule", action="store_true", help="schedule workouts that specify dates")
    args = parser.parse_args(argv)
    if args.login and (args.plan or args.dry_run or args.schedule):
        parser.error("--login must be used alone")
    if not args.login and not args.plan:
        parser.error("a JSON plan file or --login is required")
    try:
        if args.login:
            authenticate()
            return 0
        plan = read_plan(args.plan)
        workouts = validate_plan(plan)
        sport = plan["sport"]
        for source in workouts:
            build_workout(source, sport=sport)  # validate conversion before any remote writes
        if args.dry_run:
            for source in workouts:
                print(f"DRY RUN: {source['name']} ({duration(source['steps'])} seconds)" + (f"; schedule {source['scheduled_date']}" if args.schedule and "scheduled_date" in source else ""))
            return 0
        upload_plan(authenticate(), workouts, args.schedule, sport=sport)
        return 0
    except (InputError, ValueError, OSError, RuntimeError, EOFError,
            GarminConnectAuthenticationError, GarminConnectConnectionError,
            GarminConnectTooManyRequestsError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
