"""Live acceptance check for creating and retrying one isolated test template."""

from pathlib import Path

from workoutplanner.garmin.auth import TOKEN_DIR, open_workout_publisher
from workoutplanner.garmin.publish import prepare_batch, publish_batch
from workoutplanner.garmin.upload import upload_lock
from workoutplanner.planning_input import read_object


def check(api, state_path):
    plan = read_object(Path(__file__).parent / "fixtures/cycling-encoder-check.json")
    plan["workouts"][0]["name"] = "WorkoutPlanner managed acceptance A"
    digest, batch = prepare_batch({"acceptance_ride": plan})
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


if __name__ == "__main__":
    with upload_lock(TOKEN_DIR):
        check(open_workout_publisher(), TOKEN_DIR / "workoutplanner-acceptance.json")
