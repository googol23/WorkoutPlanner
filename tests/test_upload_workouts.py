"""Offline tests: stub the library boundary when pip is unavailable."""
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


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


from workoutplanner.garmin.strength import build_strength_workout, resolve_exercise
from workoutplanner.workout_schema import load_plan


library = types.ModuleType("garminconnect")
library.Garmin = Mock()
library.GarminConnectAuthenticationError = type("GarminConnectAuthenticationError", (Exception,), {})
library.GarminConnectConnectionError = type("GarminConnectConnectionError", (Exception,), {})
library.GarminConnectTooManyRequestsError = type("GarminConnectTooManyRequestsError", (Exception,), {})
workout = types.ModuleType("garminconnect.workout")
workout.RunningWorkout = Model
workout.CyclingWorkout = Model
workout.CustomPowerTarget = type("CustomPowerTarget", (Model,), {"target_type": 2, "target_type_key": "power.zone"})
workout.WorkoutSegment = Model
workout.PaceTarget = type("PaceTarget", (Model,), {"target_type": 6, "target_type_key": "pace.zone"})
workout.CustomHeartRateTarget = type("CustomHeartRateTarget", (Model,), {"target_type": 3, "target_type_key": "heart.rate.zone"})
for kind in ("warmup", "cooldown", "recovery", "interval"):
    setattr(workout, "create_" + kind + "_step", step(kind))
workout.create_targeted_interval_step = lambda seconds, order, target: Model(stepOrder=order, target=target)
workout.create_repeat_group = lambda count, children, order: Model(stepOrder=order, numberOfIterations=count, workoutSteps=children)
spec = importlib.util.spec_from_file_location("upload_workouts", Path(__file__).resolve().parents[1] / "workoutplanner" / "garmin" / "upload.py")
module = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"garminconnect": library, "garminconnect.workout": workout}):
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
        workouts = load_plan(path)
        self.assertEqual(len(workouts), 1)
        self.assertEqual(module.build_workout(workouts[0]).estimatedDurationInSecs, 1200)
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
                    load_plan(path)

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

    def test_cycling_upload_and_duplicate_skip(self):
        plan = {"schema_version": "1.0", "sport": "cycling", "workouts": [{
            "name": "Easy ride", "total_duration_seconds": 900,
            "steps": [{"type": "ride", "duration_seconds": 900, "effort": "easy",
                       "power_watts": {"min": 110, "max": 140}}],
        }]}
        workouts = module.validate_plan(plan)
        api = Mock()
        api.get_workouts.return_value = []
        api.upload_cycling_workout.return_value = {"workoutId": 5}
        module.upload_plan(api, workouts, sport="cycling")
        sent = api.upload_cycling_workout.call_args.args[0]
        segment = sent.workoutSegments[0]
        self.assertEqual(segment.sportType["sportTypeId"], 2)
        step = segment.workoutSteps[0]
        self.assertEqual((step.target.lower_limit, step.target.upper_limit), (110, 140))
        self.assertEqual(step.description, "easy")
        api.get_workouts.return_value = [{"workoutName": "Easy ride", "workoutId": 5}]
        module.upload_plan(api, workouts, sport="cycling")
        api.upload_cycling_workout.assert_called_once()
        api.upload_running_workout.assert_not_called()
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
        converted = build_strength_workout(workouts[0]).to_dict()
        steps = converted["workoutSegments"][0]["workoutSteps"]
        self.assertEqual(converted["sportType"]["sportTypeKey"], "strength_training")
        self.assertEqual([step["endConditionValue"] for step in steps], [8, 60, 8])
        self.assertEqual(steps[0]["exerciseName"], "GOBLET_SQUAT")
        self.assertAlmostEqual(steps[0]["weightValue"], 9071.8474)
        api = Mock()
        api.get_workouts.return_value = []
        api.upload_strength_workout.return_value = {"workoutId": 5}
        module.upload_plan(api, workouts, sport="strength_training")
        api.upload_strength_workout.assert_called_once()
        api.get_workouts.return_value = [{"workoutName": "Gym test", "workoutId": 5}]
        module.upload_plan(api, workouts, sport="strength_training")
        api.upload_strength_workout.assert_called_once()
        plan["workouts"][0]["exercises"][0]["name"] = "Unknown exercise"
        with tempfile.TemporaryDirectory() as folder, patch.object(module, "authenticate") as auth:
            path = Path(folder) / "strength.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            self.assertEqual(module.main([str(path), "--dry-run"]), 1)
            auth.assert_not_called()

    def test_unknown_calendar_refuses_write(self):
        api = Mock()
        api.get_workouts.return_value = []
        api.get_scheduled_workouts.return_value = None
        with self.assertRaises(RuntimeError):
            module.upload_plan(api, self.plan, schedule=True)
        api.upload_running_workout.assert_not_called()


if __name__ == "__main__":
    unittest.main()
