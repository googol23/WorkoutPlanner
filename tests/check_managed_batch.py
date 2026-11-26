"""Live acceptance check for creating and retrying one isolated test template."""

import argparse
from pathlib import Path

from garminconnect import GarminConnectNotFoundError

from workoutplanner.garmin.auth import TOKEN_DIR, open_workout_publisher
from workoutplanner.garmin.publish import prepare_batch, publish_batch, write_state
from workoutplanner.garmin.upload import upload_lock
from workoutplanner.planning_input import read_object


def fixture_batch(stage):
    plan = read_object(Path(__file__).parent / "fixtures/cycling-encoder-check.json")
    plan["workouts"][0]["name"] = f"WorkoutPlanner managed acceptance {stage}"
    return prepare_batch({"acceptance_ride": plan})


def check(api, state_path):
    digest, batch = fixture_batch("A")
    name, = batch
    if state_path.exists():
        state = read_object(state_path)
        if set(state["active"]) - {name}:
            raise ValueError("The test journal contains a different batch. Stopping before publishing.")
        pending = state["pending"]
        if pending is not None and (pending["digest"] != digest or set(pending["workouts"]) - {name}):
            raise ValueError("The test journal contains a different pending batch.")

    publish_batch(api, state_path, digest, batch)
    first = read_object(state_path)["active"]
    publish_batch(api, state_path, digest, batch)
    second = read_object(state_path)["active"]
    if set(first) != {name} or second != first:
        raise RuntimeError("The saved test workout ID changed on retry.")
    workout_id = second[name]
    remote = api.get_workout_by_id(workout_id)
    if remote.get("workoutName") != name or str(remote.get("workoutId")) != workout_id:
        raise RuntimeError("The saved test ID and name could not be verified in Garmin.")
    print("Managed test A verified: stable ID and matching Garmin template.")


def replace_a(api, state_path):
    _, batch_a = fixture_batch("A")
    digest, batch_b = fixture_batch("B")
    name_a, = batch_a
    name_b, = batch_b
    state = read_object(state_path)
    active = state["active"]
    pending = state["pending"]
    if set(active) - {name_a, name_b} or len(active) > 1:
        raise ValueError("Unexpected active workout in the acceptance journal.")
    if pending is not None and (pending["digest"] != digest or set(pending["workouts"]) - {name_b}):
        raise ValueError("Unexpected pending batch in the acceptance journal.")

    # Keep A's identity after the publisher commits B so verification is retryable.
    receipt = state_path.with_suffix(".replacement.json")
    if pending is None and set(active) == {name_a}:
        old_id = active[name_a]
        remote = api.get_workout_by_id(old_id)
        if remote.get("workoutName") != name_a or str(remote.get("workoutId")) != old_id:
            raise ValueError("Garmin did not confirm the recorded test A identity.")
        write_state(receipt, {name_a: old_id})
    else:
        if pending is None and set(active) != {name_b}:
            raise ValueError("Run the initial managed test A first.")
        old_id = read_object(receipt)[name_a]
        if name_a in active and active[name_a] != old_id:
            raise ValueError("The saved test A references disagree.")

    publish_batch(api, state_path, digest, batch_b)
    new_id = read_object(state_path)["active"][name_b]
    publish_batch(api, state_path, digest, batch_b)
    remote = api.get_workout_by_id(new_id)
    if (new_id == old_id or read_object(state_path)["active"] != {name_b: new_id}
            or remote.get("workoutName") != name_b or str(remote.get("workoutId")) != new_id):
        raise RuntimeError("Could not verify the replacement template and its stable ID.")
    try:
        api.get_workout_by_id(old_id)
    except GarminConnectNotFoundError:
        print("Managed replacement verified: B retained its ID and A is absent from Garmin.")
        return
    raise RuntimeError("Garmin still returns the old template. Rerun the replacement check.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replace-a", action="store_true",
                        help="replace the isolated test A with B and verify deletion of A")
    args = parser.parse_args()
    with upload_lock(TOKEN_DIR):
        run = replace_a if args.replace_a else check
        run(open_workout_publisher(), TOKEN_DIR / "workoutplanner-acceptance.json")
