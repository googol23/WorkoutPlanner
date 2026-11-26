"""Offline workout encoding, publishing and dry-run checks."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from workoutplanner.garmin import upload as module
from workoutplanner.garmin.contracts import WorkoutPublisher
from workoutplanner.garmin.strength import resolve_exercise
from workoutplanner.workout_schema import load_plan


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.plan = [{"name": "Intervals", "scheduled_date": "2027-04-02", "week": 1, "total_duration_seconds": 1080, "steps": [
            {"type": "warmup", "duration_seconds": 300},
            {"type": "repeat", "count": 3, "steps": [
                {"type": "interval", "duration_seconds": 120, "target": {"type": "pace", "slow_seconds_per_km": 360, "fast_seconds_per_km": 300}},
                {"type": "recovery", "duration_seconds": 60, "target": {"type": "heart_rate", "min_bpm": 110, "max_bpm": 130}},
            ]},
            {"type": "cooldown", "duration_seconds": 240},
        ]}]

    def test_supplied_plan(self):
        path = Path(__file__).resolve().parents[1] / "running_plan.json"
        workouts = load_plan(path)
        self.assertEqual(len(workouts), 1)
        self.assertEqual(module.build_workout(workouts[0])["estimatedDurationInSecs"], 1200)
        with patch.object(module, "live_upload") as live:
            self.assertEqual(module.main([str(path), "--dry-run", "--schedule"]), 0)
            live.assert_not_called()

    def test_conversion_and_duration(self):
        result = module.build_workout(self.plan[0])
        self.assertEqual(result["estimatedDurationInSecs"], 1080)
        steps = result["workoutSegments"][0]["workoutSteps"]
        self.assertEqual([s["stepOrder"] for s in steps], [1, 2, 5])
        self.assertEqual([s["stepOrder"] for s in steps[1]["workoutSteps"]], [3, 4])
        pace = steps[1]["workoutSteps"][0]
        self.assertAlmostEqual(pace["targetValueOne"], 1000 / 360)
        self.assertAlmostEqual(pace["targetValueTwo"], 1000 / 300)
        self.assertEqual(steps[1]["workoutSteps"][1]["targetValueOne"], 110)

    def test_bad_input_rejected(self):
        for bad_step in (
            {"type": "repeat", "count": 0, "steps": [{"type": "interval", "duration_seconds": 30}]},
            {"type": "interval", "duration_seconds": -1},
            {"type": "interval", "duration_seconds": 60, "target": {"type": "pace", "slow_seconds_per_km": 290, "fast_seconds_per_km": 330}},
            {"type": "interval", "duration_seconds": 60, "unknown": 1},
        ):
            with self.subTest(bad_step=bad_step), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "plan.json"
                path.write_text(json.dumps({"schema_version": "1.0", "sport": "running", "timezone": "Europe/Berlin", "units": {"duration": "seconds", "pace": "seconds_per_km", "heart_rate": "bpm"}, "workouts": [{"name": "X", "week": 1, "total_duration_seconds": 60, "steps": [bad_step]}]}))
                with self.assertRaises(module.InputError):
                    load_plan(path)

    def test_dry_run_never_authenticates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps({"schema_version": "1.0", "sport": "running", "timezone": "Europe/Berlin", "units": {"duration": "seconds", "pace": "seconds_per_km", "heart_rate": "bpm"}, "workouts": self.plan}))
            with patch.object(module, "live_upload") as live:
                self.assertEqual(module.main([str(path), "--dry-run", "--schedule"]), 0)
                live.assert_not_called()

    def test_upload_then_schedule_and_skip_duplicates(self):
        api = Mock(spec_set=WorkoutPublisher)
        api.get_workouts.return_value = []
        api.get_scheduled_workouts.return_value = {"calendarItems": []}
        api.upload_workout.return_value = {"workoutId": 42}
        module.upload_plan(api, self.plan, schedule=True)
        api.schedule_workout.assert_called_once_with(42, "2027-04-02")
        api.get_workouts.return_value = [{"workoutName": "Intervals", "workoutId": 42}]
        api.get_scheduled_workouts.return_value = {"calendarItems": [{"itemType": "workout", "date": "2027-04-02", "workoutId": 42}]}
        module.upload_plan(api, self.plan, schedule=True)
        api.upload_workout.assert_called_once()
        api.schedule_workout.assert_called_once()

    def test_cycling_upload_and_duplicate_skip(self):
        plan = {"schema_version": "1.0", "sport": "cycling", "workouts": [{
            "name": "Easy ride", "total_duration_seconds": 900,
            "steps": [{"type": "ride", "duration_seconds": 900, "effort": "easy",
                       "power_watts": {"min": 110, "max": 140}}],
        }]}
        workouts = module.validate_plan(plan)
        api = Mock(spec_set=WorkoutPublisher)
        api.get_workouts.return_value = []
        api.upload_workout.return_value = {"workoutId": 5}
        module.upload_plan(api, workouts, sport="cycling")
        sent = api.upload_workout.call_args.args[0]
        segment = sent["workoutSegments"][0]
        self.assertEqual(segment["sportType"]["sportTypeId"], 2)
        step = segment["workoutSteps"][0]
        self.assertEqual((step["targetValueOne"], step["targetValueTwo"]), (110, 140))
        self.assertEqual(step["description"], "easy")
        api.get_workouts.return_value = [{"workoutName": "Easy ride", "workoutId": 5}]
        module.upload_plan(api, workouts, sport="cycling")
        api.upload_workout.assert_called_once()
        plan["workouts"][0]["steps"][0]["power_watts"]["min"] = 150
        with self.assertRaisesRegex(module.InputError, "Maximum watts"):
            module.validate_plan(plan)

    def test_strength_resolves_glute_bridge_and_suggests_catalog_names(self):
        self.assertEqual(resolve_exercise("Glute Bridge"), resolve_exercise("Hip Raise"))
        with self.assertRaisesRegex(module.InputError, "Catalog matches:.*Goblet Squat"):
            resolve_exercise("Goblet Squats")

    def test_strength_conversion_and_upload(self):
        plan = {"schema_version": "1.0", "sport": "strength_training", "workouts": [{
            "name": "Gym test", "estimated_duration_seconds": 900, "warmup": "Warm up",
            "exercises": [{"name": "Goblet Squat", "sets": 2, "reps": {"min": 8, "max": 10},
                           "rest_seconds": 60, "effort": "Easy", "load": {"value": 20, "unit": "lb"}}],
        }]}
        workouts = module.validate_plan(plan)
        converted = module.build_workout(workouts[0], sport="strength_training")
        steps = converted["workoutSegments"][0]["workoutSteps"]
        self.assertEqual(converted["sportType"]["sportTypeKey"], "strength_training")
        self.assertEqual([step["endConditionValue"] for step in steps], [8, 60, 8])
        self.assertEqual(steps[0]["exerciseName"], "GOBLET_SQUAT")
        self.assertAlmostEqual(steps[0]["weightValue"], 9071.8474)
        api = Mock(spec_set=WorkoutPublisher)
        api.get_workouts.return_value = []
        api.upload_workout.return_value = {"workoutId": 5}
        module.upload_plan(api, workouts, sport="strength_training")
        api.upload_workout.assert_called_once()
        api.get_workouts.return_value = [{"workoutName": "Gym test", "workoutId": 5}]
        module.upload_plan(api, workouts, sport="strength_training")
        api.upload_workout.assert_called_once()
        plan["workouts"][0]["exercises"][0]["name"] = "Unknown exercise"
        with tempfile.TemporaryDirectory() as folder, patch.object(module, "live_upload") as auth:
            path = Path(folder) / "strength.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            self.assertEqual(module.main([str(path), "--dry-run"]), 1)
            auth.assert_not_called()

    def test_schedule_requires_a_date_before_authentication(self):
        plan = {"schema_version": "1.0", "sport": "strength_training", "workouts": [{
            "name": "Gym test", "estimated_duration_seconds": 900, "warmup": "Warm up",
            "exercises": [{"name": "Goblet Squat", "sets": 2, "reps": {"min": 8, "max": 10},
                           "rest_seconds": 60, "effort": "Easy"}],
        }]}
        with tempfile.TemporaryDirectory() as folder, patch.object(module, "live_upload") as auth:
            path = Path(folder) / "strength.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            self.assertEqual(module.main([str(path), "--schedule", "--dry-run"]), 1)
            self.assertEqual(module.main([str(path), "--schedule"]), 1)
            auth.assert_not_called()

    def test_live_upload_lock_rejects_concurrent_call_and_releases(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            with module.upload_lock(directory):
                with self.assertRaisesRegex(RuntimeError, "local Garmin upload lock"):
                    with module.upload_lock(directory):
                        self.fail("second lock unexpectedly acquired")
            with module.upload_lock(directory):
                pass

    def test_unknown_calendar_refuses_write(self):
        api = Mock(spec_set=WorkoutPublisher)
        api.get_workouts.return_value = []
        api.get_scheduled_workouts.return_value = None
        with self.assertRaises(RuntimeError):
            module.upload_plan(api, self.plan, schedule=True)
        api.upload_workout.assert_not_called()


if __name__ == "__main__":
    unittest.main()
