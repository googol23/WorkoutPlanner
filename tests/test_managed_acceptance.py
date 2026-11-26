import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from garminconnect import GarminConnectNotFoundError

from check_managed_batch import check, fixture_batch, replace_a
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

    def test_replacement_and_repeat_only_delete_test_a(self):
        api = Mock()
        _, a = fixture_batch("A")
        original = next(iter(a))
        library = {"101": {"workoutId": 101, "workoutName": original}}
        def lookup(key):
            if key not in library:
                raise GarminConnectNotFoundError("missing")
            return library[key]
        def upload(payload):
            library["102"] = {"workoutId": 102, "workoutName": payload["workoutName"]}
            return library["102"]
        api.get_workout_by_id.side_effect = lookup
        api.get_workouts.side_effect = lambda **kw: list(library.values())
        api.upload_workout.side_effect = upload
        api.delete_workout.side_effect = library.pop
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "acceptance.json"
            write_state(path, {"active": {original: "101"}, "pending": None})
            replace_a(api, path)
            replace_a(api, path)
        api.upload_workout.assert_called_once()
        api.delete_workout.assert_called_once_with("101")

    def test_renamed_a_aborts_before_upload(self):
        api = Mock()
        _, a = fixture_batch("A")
        api.get_workout_by_id.return_value = {"workoutId": 101, "workoutName": "renamed"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "acceptance.json"
            write_state(path, {"active": {next(iter(a)): "101"}, "pending": None})
            with self.assertRaisesRegex(ValueError, "identity"):
                replace_a(api, path)
        api.upload_workout.assert_not_called()
        api.delete_workout.assert_not_called()
