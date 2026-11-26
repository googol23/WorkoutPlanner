import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from check_managed_batch import check
from workoutplanner.garmin.publish import write_state


class ManagedAcceptanceTests(unittest.TestCase):
    def test_retry_reuses_uploaded_id_and_reads_it_back(self):
        api = Mock()
        api.get_workouts.return_value = []
        api.upload_workout.return_value = {"workoutId": 123}
        api.get_workout_by_id.side_effect = lambda key: {
            "workoutId": int(key), "workoutName": api.upload_workout.call_args.args[0]["workoutName"]}
        with tempfile.TemporaryDirectory() as folder:
            check(api, Path(folder) / "acceptance.json")
        api.upload_workout.assert_called_once()
        api.get_workout_by_id.assert_called_once_with("123")
        api.delete_workout.assert_not_called()

    def test_different_active_batch_stops_before_garmin_calls(self):
        api = Mock()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "acceptance.json"
            write_state(path, {"active": {"other": "123"}, "pending": None})
            with self.assertRaisesRegex(ValueError, "different batch"):
                check(api, path)
        self.assertEqual(api.mock_calls, [])
