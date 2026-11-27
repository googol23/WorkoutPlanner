import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from workoutplanner.garmin import personal


class PersonalApiTests(unittest.TestCase):
    def test_login_checks_key_before_storing(self):
        with patch.object(personal, "getpass", return_value="new-key"), patch.object(
            personal, "request", return_value=b"abc.def.xyz\n"
        ) as request, tempfile.TemporaryDirectory() as folder, patch.object(
            personal, "KEY_FILE", Path(folder) / "private" / "garmin_personal_api_key"
        ):
            personal.login()
            request.assert_called_once_with("POST", personal.TOKEN_PATH, "ApiKey new-key")
            self.assertEqual(personal.load_key(), "new-key")
            self.assertEqual(stat.S_IMODE(personal.KEY_FILE.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(personal.KEY_FILE.parent.stat().st_mode), 0o700)
            request.reset_mock()
            request.return_value = b"unexpected"
            with self.assertRaises(RuntimeError):
                personal.login()
            request.assert_called_once()

    def test_load_key_rejects_permissions_visible_to_other_users(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(personal, "KEY_FILE", Path(folder) / "key"):
            personal.KEY_FILE.write_text("private-value\n")
            os.chmod(personal.KEY_FILE, 0o644)
            with self.assertRaisesRegex(RuntimeError, "chmod 600"):
                personal.load_key()

    def test_read_and_compare(self):
        sets = [{"repetitionCount": 8, "weight": 12000}]
        with tempfile.TemporaryDirectory() as folder, patch.object(personal, "load_key", return_value="key"), patch.object(
            personal, "request", side_effect=[b"a.b.c", json.dumps({"activityId": 17, "exerciseSets": sets}).encode()]
        ) as request, patch("sys.stdout", new_callable=io.StringIO) as output:
            path = Path(folder) / "export.json"
            path.write_text(json.dumps({"activities": [{"activity_id": 17, "exercise_sets": {"exerciseSets": sets}}]}))
            self.assertEqual(personal.main(["check", "17", "--compare-export", str(path)]), 0)
            self.assertIn("match", output.getvalue())
            self.assertNotIn("12000", output.getvalue())
            self.assertEqual(request.call_args.args, ("GET", "/activity-service/activity/17", "Bearer a.b.c"))

    def test_missing_detail_checks_associated_workouts_without_exposing_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "export.json"
            path.write_text(json.dumps({"activities": [{"activity_id": 17, "exercise_sets": {
                "exerciseSets": [{"repetitionCount": 12}]}}]}))
            for payload, expected in (
                (b"", "field unavailable"),
                (b'[{"exerciseSets":[]}]', "0 exercise-set records"),
                (b'[{"exerciseSets":[{"repetitionCount":12}]}]', "match"),
            ):
                with self.subTest(payload=payload), patch.object(personal, "load_key", return_value="key"), patch.object(
                    personal, "request", side_effect=[b"a.b.c", b'{"activityId":17}', payload]
                ) as request, patch("sys.stdout", new_callable=io.StringIO) as output:
                    self.assertEqual(personal.main(["check", "17", "--compare-export", str(path)]), 0)
                    self.assertIn("Existing export: 1 exercise-set record", output.getvalue())
                    self.assertIn("Personal API activity detail: exerciseSets field unavailable", output.getvalue())
                    self.assertIn(expected, output.getvalue().split("Personal API associated workouts:")[1])
                    self.assertNotIn("repetitionCount", output.getvalue())
                    request.assert_called_with("GET", "/activity-service/activity/17/workouts",
                                               "Bearer a.b.c", optional=True)

    def test_http_failure_omits_response_and_closes_connection(self):
        for status in (302, 401, 403, 429):
            with self.subTest(status=status), patch.object(personal, "HTTPSConnection") as connect:
                conn = connect.return_value
                response = conn.getresponse.return_value
                response.status = status
                with self.assertRaises(RuntimeError):
                    personal.request("POST", personal.TOKEN_PATH, "ApiKey private-value")
                conn.request.assert_called_once()
                response.read.assert_not_called()
                conn.close.assert_called_once()
