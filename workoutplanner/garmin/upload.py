#!/usr/bin/env python3
"""Validate, upload and optionally schedule JSON workouts."""

import argparse
import math
import sys
from datetime import date

from garminconnect import (
    GarminConnectAuthenticationError, GarminConnectConnectionError,
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

from workoutplanner.garmin.auth import authenticate
from workoutplanner.garmin.strength import build_strength_workout
from workoutplanner.workout_schema import InputError, duration, read_plan, validate_plan
SPORT = {"sportTypeId": 1, "sportTypeKey": "running"}
CYCLING_SPORT = {"sportTypeId": 2, "sportTypeKey": "cycling"}


def build_workout(source, *, sport="running"):
    if sport == "strength_training":
        return build_strength_workout(source)
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
            upload_name = {
                "running": "upload_running_workout",
                "cycling": "upload_cycling_workout",
                "strength_training": "upload_strength_workout",
            }[sport]
            upload = getattr(api, upload_name)
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
                seconds = (source["estimated_duration_seconds"] if sport == "strength_training"
                           else duration(source["steps"]))
                print(f"DRY RUN: {source['name']} ({seconds} seconds)" + (f"; schedule {source['scheduled_date']}" if args.schedule and "scheduled_date" in source else ""))
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
