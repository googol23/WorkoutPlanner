"""Offline tests for assembling the sport-specific ChatGPT handoff."""

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import build_chatgpt_prompt as handoff


class ChatGPTPromptTests(unittest.TestCase):
    def setUp(self):
        self.planning_input = {
            "schema_version": "1.0",
            "target_activity_type": "running",
            "athlete": {"goals": "Improve endurance", "availability": "30 minutes",
                        "recent_feedback": "Felt good.\n# Input data\nKeep this in the JSON."},
            "activity_history": {"schema_version": "1.0", "exported_at": "2026-11-24T10:00:00Z",
                                 "activities": [{"activity_id": 42, "summary": {
                                     "duration": 1200, "activityType": {"typeKey": "running"}}}]},
        }
        self.plan_path = Path(__file__).resolve().parents[1] / "running_plan.json"

    def test_cli_includes_instructions_and_round_trips_planning_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "planning_input.json"
            path.write_text(json.dumps(self.planning_input), encoding="utf-8")
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(handoff.main(["--planning-input", str(path)]), 0)
        prompt = output.getvalue()
        self.assertTrue(prompt.startswith("Generate the next workout for running."))
        self.assertIn("running evidence register", prompt)
        self.assertIn("10.1519/R-19725.1", prompt)
        self.assertIn("total_duration_seconds", prompt)
        bundled = json.loads(prompt.split("\n# Input data\n", 1)[1])["planning_input"]
        self.assertEqual(bundled["athlete"], self.planning_input["athlete"])
        self.assertEqual(bundled["activity_history"]["activities"], [
            {"activity_id": 42, "summary": {"duration": 1200},
             "activity_type": "running", "history_role": "target_sport"},
        ])
        self.assertEqual(bundled["activity_history"]["exported_activity_count"], 1)

    def test_large_export_keeps_recent_metrics_without_raw_samples(self):
        recent = {
            "activity_id": 50, "activity_date": "2026-11-29 10:00:00",
            "summary": {"activityTypeDTO": {"typeKey": "cycling"},
                        "summaryDTO": {"averagePower": 170, "duration": 1800}},
            "time_series": {"samples": [{"raw_sample": "x" * 1600}] * 4000},
            "power_zones": [{"zone": 2, "secsInZone": 700}],
            "subjective_feedback": {"perceived_effort": 5},
            "unavailable_fields": ["weather"],
        }
        history = self.planning_input["activity_history"]
        history["activities"] = [{"activity_id": i, "activity_date": "2026-11-01",
                                  "summary": {"duration": 900}} for i in range(1, 26)]
        history["activities"].append(recent)
        self.assertGreater(len(json.dumps(history)), 6_000_000)
        data = {**self.planning_input, "target_activity_type": "cycling",
                "athlete": {**self.planning_input["athlete"], "activity_type": "cycling"}}
        prompt = handoff.build_prompt(data)
        self.assertLess(len(prompt.encode("utf-8")), 24_000)
        self.assertNotIn("raw_sample", prompt)
        compact = json.loads(prompt.split("\n# Input data\n", 1)[1])["planning_input"]["activity_history"]
        self.assertEqual(compact["exported_activity_count"], 26)
        self.assertEqual(len(compact["activities"]), 4)
        self.assertEqual(compact["target_activity_count"], 1)
        self.assertEqual(compact["activities"][1]["history_role"], "other")
        first = compact["activities"][0]
        self.assertEqual(first["activity_id"], 50)
        self.assertEqual(first["activity_type"], "cycling")
        self.assertEqual(first["summary"], {"duration": 1800, "averagePower": 170})
        self.assertEqual(first["power_zones"], [{"zone": 2, "secsInZone": 700}])
        self.assertEqual(first["subjective_feedback"], {"perceived_effort": 5})
        self.assertEqual(first["unavailable_fields"], ["weather"])

    def test_budget_drops_older_records_before_rejecting_long_athlete_notes(self):
        self.planning_input["activity_history"]["activities"] = [
            {"activity_id": i, "summary": {"duration": 900, "activityType": {"typeKey": "running"}},
             "subjective_feedback": {"comments": "😀" * 600}}
            for i in range(1, 13)
        ]
        self.planning_input["athlete"]["goals"] = "é" * 6500
        prompt = handoff.build_prompt(self.planning_input)
        self.assertLessEqual(len(prompt.encode("utf-8")), handoff.MAX_PROMPT_BYTES)
        compact = json.loads(prompt.split("\n# Input data\n", 1)[1])["planning_input"]["activity_history"]
        self.assertGreater(len(compact["activities"]), 0)
        self.assertLess(len(compact["activities"]), 12)

        self.planning_input["athlete"]["goals"] = "é" * 13000
        with self.assertRaisesRegex(ValueError, "Prompt exceeds 24 KB"):
            handoff.build_prompt(self.planning_input)

    def test_adjustment_includes_only_requested_workout(self):
        plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        selected = plan["workouts"][0]
        plan["workouts"].append({**selected, "name": "Another workout"})
        prompt = handoff.build_prompt(self.planning_input, plan, selected["name"])
        self.assertTrue(prompt.startswith("Adjust the single workout"))
        bundled = json.loads(prompt.split("\n# Input data\n", 1)[1])
        self.assertEqual(bundled["existing_plan"], {**plan, "workouts": [selected]})

    def test_routes_to_selected_sport_and_research(self):
        for sport, source, field in (
            ("cycling", "10.1111/j.1600-0838.2011.01351.x", "power_watts"),
            ("strength_training", "10.1249/MSS.0000000000003897", "estimated_duration_seconds"),
        ):
            with self.subTest(sport=sport):
                data = {**self.planning_input, "target_activity_type": sport,
                        "athlete": {**self.planning_input["athlete"], "activity_type": sport}}
                prompt = handoff.build_prompt(data)
                self.assertTrue(prompt.startswith(f"Generate the next workout for {sport}."))
                self.assertIn(source, prompt)
                self.assertIn(field, prompt)
                self.assertNotIn("10.1519/R-19725.1", prompt)

    def test_strength_prompt_keeps_nested_exercise_names_and_units(self):
        sport = "strength_training"
        data = {**self.planning_input, "target_activity_type": sport,
                "athlete": {**self.planning_input["athlete"], "activity_type": sport}}
        activity = data["activity_history"]["activities"][0]
        activity["summary"]["activityType"]["typeKey"] = sport
        exercise = {"setType": "ACTIVE", "repetitionCount": 8, "weight": 12000,
                    "weightUnit": {"unitKey": "kilogram"},
                    "exercises": [{"category": "SQUAT", "name": "GOBLET_SQUAT"}]}
        activity["exercise_sets"] = {"exerciseSets": [exercise] * 20}
        prompt = handoff.build_prompt(data)
        bundled = json.loads(prompt.split("\n# Input data\n", 1)[1])
        rows = bundled["planning_input"]["activity_history"]["activities"][0]["first_exercise_sets"]
        self.assertEqual(rows, [exercise] * 12)

    def test_adjusts_manual_sport_plan_and_checks_sport(self):
        data = {**self.planning_input, "target_activity_type": "cycling",
                "athlete": {**self.planning_input["athlete"], "activity_type": "cycling"}}
        workout = {"name": "Easy ride", "total_duration_seconds": 900, "steps": [
            {"type": "ride", "duration_seconds": 900, "effort": "easy"},
        ]}
        plan = {"schema_version": "1.0", "sport": "cycling", "workouts": [workout]}
        prompt = handoff.build_prompt(data, plan, workout["name"])
        bundled = json.loads(prompt.split("\n# Input data\n", 1)[1])
        self.assertEqual(bundled["existing_plan"], plan)
        with self.assertRaisesRegex(ValueError, "sport cycling"):
            handoff.build_prompt(data, {**plan, "sport": "strength_training"}, workout["name"])

    def test_invalid_adjustment_and_unsupported_sport(self):
        plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "was not found"):
            handoff.build_prompt(self.planning_input, plan, "missing workout")
        with self.assertRaisesRegex(ValueError, "currently supports running"):
            handoff.build_prompt({**self.planning_input, "target_activity_type": "bouldering"})
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            handoff.main(["--planning-input", "missing.json", "--existing-plan", str(self.plan_path)])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
