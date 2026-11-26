from contextlib import redirect_stdout
from io import StringIO
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
            batch = {"new-run": {"sportType": "running"}, "new-ride": {"sportType": "cycling"}}
            api = Mock(spec_set=WorkoutPublisher)
            api.get_workouts.return_value = []
            api.upload_workout.side_effect = [{"workoutId": 20}, OSError("network"), {"workoutId": 21}]
            api.get_workout_by_id.side_effect = lambda key: {
                "workoutName": old if key == "10" else "new-run",
            }
            with self.assertRaises(OSError):
                publish.publish_batch(api, state_path, "batch", batch)
            api.delete_workout.assert_not_called()
            self.assertEqual(read_object(state_path)["pending"]["workouts"], {"new-run": "20"})

            publish.publish_batch(api, state_path, "batch", batch)
            self.assertEqual(api.upload_workout.call_count, 3)
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
            api.upload_workout.return_value = {"workoutId": 20}
            api.get_workout_by_id.return_value = {"workoutName": "Renamed workout"}
            with self.assertRaisesRegex(ValueError, "no longer matches"):
                publish.publish_batch(api, state_path, "batch", {"new": {"sportType": "running"}})
            api.delete_workout.assert_not_called()

    def test_preview_reports_actions_without_modifying_garmin_or_journal(self):
        api = Mock(spec_set=WorkoutPublisher)
        old = "[WP-" + "a" * 24 + "] Old"
        api.get_workouts.return_value = [{"workoutName": "reuse", "workoutId": 11}]
        api.get_workout_by_id.return_value = {"workoutName": old}
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(StringIO()) as output:
            path = Path(folder) / "state.json"
            publish.write_state(path, {"active": {old: "10"}, "pending": None})
            original = path.read_bytes()
            publish.publish_batch(api, path, "batch", {"reuse": {}, "new": {}}, preview=True)
            self.assertEqual(path.read_bytes(), original)
            self.assertIn("1 to create, 1 to reuse, 1 to retire", output.getvalue())
        api.upload_workout.assert_not_called()
        api.delete_workout.assert_not_called()

    def test_first_preview_leaves_no_journal(self):
        api = Mock(spec_set=WorkoutPublisher)
        api.get_workouts.return_value = []
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            publish.publish_batch(api, path, "batch", {"new": {}}, preview=True)
            self.assertFalse(path.exists())
        api.upload_workout.assert_not_called()
