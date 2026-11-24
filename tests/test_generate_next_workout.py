"""Offline tests for the authenticated generation wrapper."""

import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from workoutplanner.chatgpt import generate as generator


class GenerationTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.output = Path(folder) / "next_workout.json"
        self.input = Path(folder) / "input.json"
        self.input.write_text(json.dumps({
            "schema_version": "1.0", "target_activity_type": "running",
            "athlete": {"goals": "Endurance", "availability": "30 minutes"},
            "activity_history": {"schema_version": "1.0", "exported_at": "2026-11-24T10:00:00Z",
                                 "activities": []},
        }), encoding="utf-8")
        self.plan = json.loads((Path(__file__).resolve().parents[1] / "running_plan.json").read_text())
        self.args = ["--planning-input", str(self.input), "--output", str(self.output)]
        self.enterContext(redirect_stdout(StringIO()))
        self.enterContext(redirect_stderr(StringIO()))

    def test_authenticated_handoff_writes_valid_workout_without_proxies(self):
        def codex(command, **options):
            self.assertFalse(any(key.lower().endswith("_proxy") for key in options["env"]))
            self.assertNotIn("OPENAI_API_KEY", options["env"])
            if command[1:3] == ["login", "status"]:
                return subprocess.CompletedProcess(command, 0, "", "Logged in using ChatGPT")
            self.assertIn("Generate the next workout for running", options["input"])
            self.assertEqual(command[-1], "-")
            path = Path(command[command.index("--output-last-message") + 1])
            path.write_text(json.dumps({"rationale": "Example", "workout_json": json.dumps(self.plan)}))
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch.dict(generator.os.environ, {"HTTPS_PROXY": "http://proxy.invalid",
                                              "OPENAI_API_KEY": "unused"}):
            with patch.object(generator.subprocess, "run", side_effect=codex):
                self.assertEqual(generator.main(self.args), 0)
        self.assertEqual(json.loads(self.output.read_text()), self.plan)

    def test_no_workout_and_invalid_workout_leave_existing_output_intact(self):
        self.output.write_text("existing", encoding="utf-8")
        for workout, exit_code in ((None, 2), ("{}", 1), ("invalid JSON", 1)):
            with self.subTest(workout=workout):
                result = {"rationale": "Example", "workout_json": workout}
                with patch.object(generator, "run_codex", return_value=result):
                    self.assertEqual(generator.main(self.args), exit_code)
                self.assertEqual(self.output.read_text(), "existing")

    def test_debug_reports_cli_error_and_preserves_file(self):
        self.output.write_text("existing", encoding="utf-8")
        status = subprocess.CompletedProcess([], 0, "", "Logged in using ChatGPT")
        failed = subprocess.CompletedProcess([], 1, "", "Error: example CLI failure")
        with patch.object(generator.subprocess, "run", side_effect=[status, failed]):
            with redirect_stderr(StringIO()) as error:
                self.assertEqual(generator.main([*self.args, "--debug"]), 1)
        self.assertIn("Error: example CLI failure", error.getvalue())
        self.assertEqual(self.output.read_text(), "existing")

    def test_api_key_login_is_rejected_before_sending_prompt(self):
        result = subprocess.CompletedProcess([], 0, "", "Logged in using an API key")
        with patch.object(generator.subprocess, "run", return_value=result) as run:
            self.assertEqual(generator.main(self.args), 1)
        run.assert_called_once()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
