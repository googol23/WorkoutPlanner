import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from workoutplanner.garmin.contracts import WorkoutPublisher
from workoutplanner.garmin import publish
from workoutplanner.planning_input import read_object


class PublishTests(unittest.TestCase):
    def test_resumes_partial_batch_before_deleting_old_workout(self):
        with tempfile.TemporaryDirectory() as folder:
            state_path = Path(folder) / "state.json"
            old = "[WP-" + "a" * 24 + "] Old workout"
            publish.write_state(state_path, {"active": {old: "10"}, "pending": None})
            batch = {"new-run": ("running", object()), "new-ride": ("cycling", object())}
            api = Mock(spec_set=WorkoutPublisher)
            api.get_workouts.return_value = []
            api.upload_running_workout.return_value = {"workoutId": 20}
            api.upload_cycling_workout.side_effect = [OSError("network"), {"workoutId": 21}]
            api.get_workout_by_id.side_effect = lambda key: {
                "workoutName": old if key == "10" else "new-run",
            }
            with self.assertRaises(OSError):
                publish.publish_batch(api, state_path, "batch", batch)
            api.delete_workout.assert_not_called()
            self.assertEqual(read_object(state_path)["pending"]["workouts"], {"new-run": "20"})

            publish.publish_batch(api, state_path, "batch", batch)
            api.upload_running_workout.assert_called_once()
            api.delete_workout.assert_called_once_with("10")
            self.assertEqual(read_object(state_path), {
                "active": {"new-run": "20", "new-ride": "21"}, "pending": None,
            })

    def test_renamed_workout_is_left_in_garmin(self):
        with tempfile.TemporaryDirectory() as folder:
            state_path = Path(folder) / "state.json"
            old = "[WP-" + "b" * 24 + "] Old workout"
            publish.write_state(state_path, {"active": {old: "10"}, "pending": None})
            api = Mock(spec_set=WorkoutPublisher)
            api.get_workouts.return_value = []
            api.upload_running_workout.return_value = {"workoutId": 20}
            api.get_workout_by_id.return_value = {"workoutName": "Renamed workout"}
            with self.assertRaisesRegex(ValueError, "no longer matches"):
                publish.publish_batch(api, state_path, "batch", {"new": ("running", object())})
            api.delete_workout.assert_not_called()
