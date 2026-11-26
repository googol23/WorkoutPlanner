import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from workoutplanner.chatgpt import week


class WeekPlanningTests(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 11, 26)
        self.profiles = {
            name: {"activity_type": sport, "goals": "Build endurance or strength", "availability": "30 minutes"}
            for name, sport in (("run", "running"), ("ride", "cycling"), ("gym", "strength_training"))
        }
        self.export = {"schema_version": "1.0", "exported_at": "2026-11-26T10:00:00Z", "activities": [
            {"activity_id": i, "activity_date": day,
             "summary": {"activityTypeDTO": {"typeKey": sport}, "summaryDTO": {"duration": 1800}}}
            for i, (day, sport) in enumerate([
                ("2026-11-26T09:00:00", "running"), ("2026-11-24T09:00:00", "cycling"),
                ("2026-11-23T09:00:00", "strength_training"), ("2026-11-13T09:00:00", "bouldering"),
                ("2026-11-12T09:00:00", "hiking"), ("2026-11-27T09:00:00", "swimming"),
            ], start=1)
        ]}
        self.plans = {
            "run": json.loads(Path("running_plan.json").read_text(encoding="utf-8")),
            "ride": {"schema_version": "1.0", "sport": "cycling", "workouts": [
                {"name": "Ride", "total_duration_seconds": 1200,
                 "steps": [{"type": "ride", "duration_seconds": 1200, "effort": "easy"}]},
            ]},
            "gym": {"schema_version": "1.0", "sport": "strength_training", "workouts": [
                {"name": "Gym", "estimated_duration_seconds": 1200, "warmup": "Easy warmup",
                 "exercises": [{"name": "Goblet Squat", "sets": 2, "reps": {"min": 8, "max": 10},
                                "rest_seconds": 60, "effort": "easy"}]},
            ]},
        }

    def test_one_prompt_contains_all_recent_types_and_profiles(self):
        prompt = week.build_week_prompt(self.export, self.profiles, self.day, 14)
        data = json.loads(prompt.split("# Input data\n", 1)[1])
        self.assertEqual(data["profiles"], self.profiles)
        self.assertEqual(data["planning_window"]["end_date"], "2026-12-02")
        history = data["shared_activity_history"]
        self.assertEqual(history["start_date"], "2026-11-13")
        self.assertEqual([row["activity_type"] for row in history["sessions"]],
                         ["running", "cycling", "strength_training", "bouldering"])
        self.assertNotIn("activity_id", prompt)
        self.assertLessEqual(len(prompt.encode("utf-8")), week.MAX_PROMPT_BYTES)
        self.assertIn("gym", data["garmin_exercise_catalog_by_profile"])

    def test_cli_saves_one_plan_per_profile_after_one_model_call(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, obj in (("export.json", self.export), ("profiles.json", self.profiles)):
                (root / name).write_text(json.dumps(obj), encoding="utf-8")
            payload = {"priority": ["ride", "run", "gym"], "plans": self.plans}
            response = {"rationale": "Synthetic weekly priorities", "workout_json": json.dumps(payload)}
            with patch.object(week, "run_codex", return_value=response) as model:
                result = week.main(["--activities", str(root / "export.json"), "--profiles", str(root / "profiles.json"),
                                    "--output-dir", str(root / "out"), "--as-of", self.day.isoformat()])
            self.assertEqual(result, 0)
            model.assert_called_once()
            run_dir, = (root / "out").iterdir()
            for name, plan in self.plans.items():
                self.assertEqual(json.loads((run_dir / f"{name}.json").read_text()), plan)

    def test_unknown_exercise_is_rejected_before_saving_batch(self):
        self.plans["gym"]["workouts"][0]["exercises"][0]["name"] = "Made Up Exercise"
        payload = {"priority": list(self.plans), "plans": self.plans}
        response = {"rationale": "Synthetic", "workout_json": json.dumps(payload)}
        with self.assertRaisesRegex(ValueError, "Profile gym: Unknown Garmin exercise"):
            week.validate_week_response(response, self.profiles)

    def test_rejects_wrong_sport_and_allows_explicit_deferral(self):
        plans = {**self.plans, "gym": None}
        response = {"rationale": "Defer gym", "workout_json": json.dumps(
            {"priority": ["run", "ride"], "plans": plans},
        )}
        _, priority, usable = week.validate_week_response(response, self.profiles)
        self.assertEqual(priority, ["run", "ride"])
        self.assertNotIn("gym", usable)
        plans["gym"] = self.plans["run"]
        response["workout_json"] = json.dumps({"priority": ["run", "ride", "gym"], "plans": plans})
        with self.assertRaisesRegex(ValueError, "sport strength_training"):
            week.validate_week_response(response, self.profiles)
