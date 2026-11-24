"""Offline tests for assembling the running ChatGPT handoff."""

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
                                 "activities": [{"activity_id": 42, "summary": {"duration": 1200}}]},
        }
        self.plan_path = Path(__file__).resolve().parents[1] / "running_plan.json"

    def test_cli_includes_instructions_and_round_trips_planning_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "planning_input.json"
            path.write_text(json.dumps(self.planning_input), encoding="utf-8")
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(handoff.main(["--planning-input", str(path)]), 0)
        prompt = output.getvalue()
        self.assertTrue(prompt.startswith("Generate the next running workout."))
        self.assertIn("running evidence register", prompt)
        self.assertIn("10.1519/R-19725.1", prompt)
        self.assertIn("total_duration_seconds", prompt)
        self.assertEqual(json.loads(prompt.split("\n# Input data\n", 1)[1]),
                         {"planning_input": self.planning_input})

    def test_adjustment_includes_only_requested_workout(self):
        plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        selected = plan["workouts"][0]
        plan["workouts"].append({**selected, "name": "Another workout"})
        prompt = handoff.build_prompt(self.planning_input, plan, selected["name"])
        self.assertTrue(prompt.startswith("Adjust the single workout"))
        bundled = json.loads(prompt.split("\n# Input data\n", 1)[1])
        self.assertEqual(bundled["existing_plan"], {**plan, "workouts": [selected]})

    def test_invalid_adjustment_and_unsupported_sport(self):
        plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "was not found"):
            handoff.build_prompt(self.planning_input, plan, "missing workout")
        with self.assertRaisesRegex(ValueError, "currently supports running"):
            handoff.build_prompt({**self.planning_input, "target_activity_type": "cycling"})
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            handoff.main(["--planning-input", "missing.json", "--existing-plan", str(self.plan_path)])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
