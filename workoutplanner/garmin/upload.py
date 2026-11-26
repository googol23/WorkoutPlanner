#!/usr/bin/env python3
"""Validate, upload and optionally schedule JSON workouts."""

import argparse
import sqlite3
from contextlib import contextmanager
import sys
from datetime import date

from workoutplanner.garmin.contracts import WorkoutPublisher
from workoutplanner.garmin.encoding import build_workout
from workoutplanner.workout_schema import InputError, duration, read_plan, validate_plan


def existing_workouts(api: WorkoutPublisher):
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


def existing_schedule(api: WorkoutPublisher, dates):
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


@contextmanager
def upload_lock(directory):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    connection = sqlite3.connect(directory / "upload-lock.sqlite3", timeout=0)
    try:
        try:
            connection.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as exc:
            raise RuntimeError("Cannot acquire the local Garmin upload lock; check for another upload") from exc
        yield
    finally:
        connection.close()


def upload_plan(api: WorkoutPublisher, workouts, schedule=False, *, sport="running"):
    from garminconnect import GarminConnectConnectionError

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
            model = build_workout(source, sport=sport)
            try:
                result = api.upload_workout(model)
            except (GarminConnectConnectionError, OSError) as exc:
                raise RuntimeError("Upload outcome is uncertain. Check Garmin Connect before retrying.") from exc
            workout_id = result.get("workoutId") if isinstance(result, dict) else None
            if not workout_id:
                raise RuntimeError(f"Upload of {name!r} returned no workoutId; check Garmin before retrying")
            print(f"Uploaded: {name} (ID {workout_id})")
            library[name] = [{"workoutId": workout_id, "workoutName": name}]
        if schedule and "scheduled_date" in source:
            schedule_once(api, name, workout_id, source["scheduled_date"], calendar)


def schedule_once(api, name, workout_id, day, calendar):
    from garminconnect import GarminConnectConnectionError

    key = (str(workout_id), day)
    if key in calendar:
        print(f"Already scheduled: {name} (ID {workout_id}) on {day}")
        return
    try:
        api.schedule_workout(workout_id, day)
    except (GarminConnectConnectionError, OSError) as exc:
        raise RuntimeError("Scheduling outcome is uncertain. Check the Garmin calendar before retrying.") from exc
    calendar.add(key)
    print(f"Scheduled: {name} (ID {workout_id}) on {day}")


def schedule_existing(api, source, sport, workout_id, day):
    current = api.get_workout_by_id(workout_id)
    if not isinstance(current, dict) or str(current.get("workoutId")) != workout_id:
        raise InputError("Garmin did not return the requested workout ID.")
    kind = current.get("sportType")
    if (current.get("workoutName") != source["name"] or not isinstance(kind, dict)
            or kind.get("sportTypeKey") != sport):
        raise InputError("The selected Garmin workout name or sport differs from the plan.")
    schedule_once(api, source["name"], workout_id, day, existing_schedule(api, [day]))


def live_upload(workouts=None, *, sport="running", schedule=False, existing=None):
    from garminconnect import (
        GarminConnectAuthenticationError, GarminConnectConnectionError, GarminConnectNotFoundError,
        GarminConnectTooManyRequestsError,
    )
    from workoutplanner.garmin.auth import TOKEN_DIR, open_workout_publisher

    try:
        if workouts is None:
            open_workout_publisher()
        else:
            with upload_lock(TOKEN_DIR):
                api = open_workout_publisher()
                if existing:
                    schedule_existing(api, workouts[0], sport, *existing)
                else:
                    upload_plan(api, workouts, schedule, sport=sport)
    except (GarminConnectAuthenticationError, GarminConnectConnectionError, GarminConnectNotFoundError,
            GarminConnectTooManyRequestsError) as exc:
        raise RuntimeError(str(exc)) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", nargs="?", help="JSON plan file")
    parser.add_argument("--login", action="store_true", help="authenticate and store tokens")
    parser.add_argument("--dry-run", action="store_true", help="validate and preview without network or login")
    scheduling = parser.add_mutually_exclusive_group()
    scheduling.add_argument("--schedule-existing", nargs=2, metavar=("ID", "DATE"),
                            help="schedule one existing Garmin workout by ID and ISO date")
    scheduling.add_argument("--schedule", action="store_true", help="schedule workouts that specify dates")
    args = parser.parse_args(argv)
    if args.login and (args.plan or args.dry_run or args.schedule or args.schedule_existing):
        parser.error("--login must be used alone")
    if not args.login and not args.plan:
        parser.error("a JSON plan file or --login is required")
    try:
        if args.login:
            live_upload()
            return 0
        plan = read_plan(args.plan)
        workouts = validate_plan(plan)
        sport = plan["sport"]
        if args.schedule_existing:
            workout_id, day = args.schedule_existing
            if len(workouts) != 1 or not workout_id.isascii() or not workout_id.isdecimal() or int(workout_id) < 1:
                raise InputError("--schedule-existing requires a single workout and a positive numeric Garmin ID")
            if date.fromisoformat(day).isoformat() != day:
                raise InputError("Use YYYY-MM-DD for the calendar date")
            workouts = [{**workouts[0], "scheduled_date": day}]
        if args.schedule and not any("scheduled_date" in workout for workout in workouts):
            raise InputError("--schedule requires at least one workout with scheduled_date (YYYY-MM-DD)")
        for source in workouts:
            build_workout(source, sport=sport)  # validate conversion before any remote writes
        if args.dry_run:
            for source in workouts:
                seconds = (source["estimated_duration_seconds"] if sport == "strength_training"
                           else duration(source["steps"]))
                print(f"DRY RUN: {source['name']} ({seconds} seconds)" + (f"; schedule {source['scheduled_date']}" if (args.schedule or args.schedule_existing) and "scheduled_date" in source else ""))
            return 0
        live_upload(workouts, sport=sport, schedule=args.schedule, existing=args.schedule_existing)
        return 0
    except (InputError, ValueError, OSError, RuntimeError, EOFError, ImportError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
