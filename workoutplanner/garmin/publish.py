"""Publish a local workout batch and retire its previous managed templates."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from garminconnect import (
    GarminConnectAuthenticationError, GarminConnectConnectionError,
    GarminConnectNotFoundError, GarminConnectTooManyRequestsError,
)

from workoutplanner.garmin.auth import TOKEN_DIR, open_workout_publisher
from workoutplanner.garmin.contracts import WorkoutPublisher, upload_for_sport
from workoutplanner.garmin.upload import build_workout, existing_workouts, upload_lock
from workoutplanner.planning_input import read_object
from workoutplanner.private_io import write_private
from workoutplanner.workout_schema import validate_plan


STATE = TOKEN_DIR / "workoutplanner-managed.json"


def write_state(path, state):
    write_private(path, json.dumps(state, indent=2) + "\n")


def prepare_batch(plans):
    if not plans:
        raise ValueError("The run contains no workout plans")
    digest = hashlib.sha256(json.dumps(
        plans, sort_keys=True, ensure_ascii=False, allow_nan=False,
    ).encode()).hexdigest()
    batch = {}
    for profile, plan in sorted(plans.items()):
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", profile):
            raise ValueError("Invalid profile name")
        workouts = validate_plan(plan)
        if len(workouts) != 1:
            raise ValueError(f"Profile {profile} must contain exactly one workout")
        source = workouts[0]
        marker = hashlib.sha256(f"{digest}:{profile}".encode()).hexdigest()[:24]
        name = f"[WP-{marker}] {source['name'][:60]}"
        sport = plan["sport"]
        batch[name] = (sport, build_workout({**source, "name": name}, sport=sport))
    return digest, batch


def publish_batch(api: WorkoutPublisher, state_path, digest, batch):
    state = read_object(state_path) if state_path.exists() else {"active": {}, "pending": None}
    active = state["active"]
    pending = state["pending"]
    if pending is None:
        if set(active) == set(batch):
            print("This workout batch was already published.")
            return
        pending = state["pending"] = {"digest": digest, "workouts": {}}
        write_state(state_path, state)
    elif pending["digest"] != digest:
        raise ValueError("A prior batch is unfinished. Publish its saved run directory again before replacing it.")

    library = existing_workouts(api)
    uploaded = pending["workouts"]
    for name, (sport, model) in batch.items():
        matches = library.get(name, [])
        if len(matches) > 1:
            raise ValueError(f"Multiple Garmin workouts match managed name {name!r}")
        if name in uploaded:
            current = api.get_workout_by_id(uploaded[name])
            if not isinstance(current, dict) or current.get("workoutName") != name:
                raise ValueError("A pending workout no longer matches Garmin. Check the Garmin library before retrying.")
            continue
        if matches:
            result = matches[0]
        else:
            result = upload_for_sport(api, sport, model)
        workout_id = result.get("workoutId") if isinstance(result, dict) else None
        if not str(workout_id).isdigit() or int(workout_id) < 1:
            raise ValueError("Garmin returned no valid workout ID. Check Garmin before retrying.")
        uploaded[name] = str(workout_id)
        write_state(state_path, state)

    # Persist every replacement before retiring any previous template.
    for name, workout_id in list(active.items()):
        if (not re.match(r"^\[WP-[0-9a-f]{24}\] ", name)
                or not str(workout_id).isdigit() or workout_id in uploaded.values()):
            raise ValueError("Managed state contains an unexpected workout reference")
        try:
            current = api.get_workout_by_id(workout_id)
        except GarminConnectNotFoundError:
            current = None
        if current is not None:
            if not isinstance(current, dict) or current.get("workoutName") != name:
                raise ValueError("An old workout no longer matches its marker. It was left in Garmin.")
            api.delete_workout(workout_id)
        del active[name]
        write_state(state_path, state)

    write_state(state_path, {"active": uploaded, "pending": None})
    print(f"Published {len(uploaded)} managed workouts and retired the previous batch.")


def publish(plans):
    digest, batch = prepare_batch(plans)
    with upload_lock(TOKEN_DIR):
        publish_batch(open_workout_publisher(), STATE, digest, batch)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="saved planner run directory to publish or retry")
    args = parser.parse_args(argv)
    try:
        profiles = read_object(args.run_dir / "batch.json")["profiles"]
        if not isinstance(profiles, list) or not all(
            isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", name) for name in profiles
        ):
            raise ValueError("Invalid batch profile list")
        publish({name: read_object(args.run_dir / f"{name}.json") for name in profiles})
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, EOFError,
            GarminConnectAuthenticationError, GarminConnectConnectionError,
            GarminConnectTooManyRequestsError, GarminConnectNotFoundError) as exc:
        print(f"Error: {exc}. Check Garmin before retrying.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
