"""Offline tests: stub the library boundary when pip is unavailable."""
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock


class Model:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def to_dict(self):
        return self.__dict__


def step(kind):
    def build(seconds, order=1, **kwargs):
        item = Model(stepOrder=order, stepType=kind, endConditionValue=seconds, **kwargs)
        return item
    return build


library = types.ModuleType("garminconnect")
library.Garmin = Mock()
library.GarminConnectAuthenticationError = type("GarminConnectAuthenticationError", (Exception,), {})
library.GarminConnectConnectionError = type("GarminConnectConnectionError", (Exception,), {})
library.GarminConnectTooManyRequestsError = type("GarminConnectTooManyRequestsError", (Exception,), {})
workout = types.ModuleType("garminconnect.workout")
workout.RunningWorkout = Model
workout.WorkoutSegment = Model
workout.PaceTarget = type("PaceTarget", (Model,), {"target_type": 6, "target_type_key": "pace.zone"})
workout.CustomHeartRateTarget = type("CustomHeartRateTarget", (Model,), {"target_type": 3, "target_type_key": "heart.rate.zone"})
for kind in ("warmup", "cooldown", "recovery", "interval"):
    setattr(workout, "create_" + kind + "_step", step(kind))
workout.create_targeted_interval_step = lambda seconds, order, target: Model(stepOrder=order, target=target)
workout.create_repeat_group = lambda count, children, order: Model(stepOrder=order, numberOfIterations=count, workoutSteps=children)
sys.modules["garminconnect"] = library
sys.modules["garminconnect.workout"] = workout
spec = importlib.util.spec_from_file_location("upload_workouts", Path(__file__).resolve().parents[1] / "upload_workouts.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


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
        workouts = module.load_plan(path)
        self.assertEqual(len(workouts), 12)
        self.assertEqual(module.build_workout(workouts[1]).estimatedDurationInSecs, 1980)
        library.Garmin.reset_mock()
        self.assertEqual(module.main([str(path), "--dry-run", "--schedule"]), 0)
        library.Garmin.assert_not_called()

    def test_conversion_and_duration(self):
        result = module.build_workout(self.plan[0])
        self.assertEqual(result.estimatedDurationInSecs, 1080)
        steps = result.workoutSegments[0].workoutSteps
        self.assertEqual([s.stepOrder for s in steps], [1, 2, 5])
        self.assertEqual([s.stepOrder for s in steps[1].workoutSteps], [3, 4])
        pace = steps[1].workoutSteps[0].target
        self.assertAlmostEqual(pace.lower_limit, 1000 / 360)
        self.assertAlmostEqual(pace.upper_limit, 1000 / 300)
        self.assertEqual(steps[1].workoutSteps[1].targetValueOne, 110)

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
                    module.load_plan(path)

    def test_dry_run_never_authenticates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps({"schema_version": "1.0", "sport": "running", "timezone": "Europe/Berlin", "units": {"duration": "seconds", "pace": "seconds_per_km", "heart_rate": "bpm"}, "workouts": self.plan}))
            library.Garmin.reset_mock()
            self.assertEqual(module.main([str(path), "--dry-run", "--schedule"]), 0)
            library.Garmin.assert_not_called()

    def test_upload_then_schedule_and_skip_duplicates(self):
        api = Mock()
        api.get_workouts.return_value = []
        api.get_scheduled_workouts.return_value = {"calendarItems": []}
        api.upload_running_workout.return_value = {"workoutId": 42}
        module.upload_plan(api, self.plan, schedule=True)
        api.schedule_workout.assert_called_once_with(42, "2027-04-02")
        api.get_workouts.return_value = [{"workoutName": "Intervals", "workoutId": 42}]
        api.get_scheduled_workouts.return_value = {"calendarItems": [{"itemType": "workout", "date": "2027-04-02", "workoutId": 42}]}
        module.upload_plan(api, self.plan, schedule=True)
        api.upload_running_workout.assert_called_once()
        api.schedule_workout.assert_called_once()

    def test_unknown_calendar_refuses_write(self):
        api = Mock()
        api.get_workouts.return_value = []
        api.get_scheduled_workouts.return_value = None
        with self.assertRaises(RuntimeError):
            module.upload_plan(api, self.plan, schedule=True)
        api.upload_running_workout.assert_not_called()


if __name__ == "__main__":
    unittest.main()
