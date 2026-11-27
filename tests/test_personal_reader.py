import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workoutplanner.chatgpt.history import summarize_activity
from workoutplanner.garmin import download, personal
from workoutplanner.garmin.personal_reader import PersonalReader


class PersonalReaderTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(personal, "load_key", return_value="key"))
        self.enterContext(patch.object(personal, "exchange", return_value="token"))

    def test_date_range_pages_and_deduplicates(self):
        rows = [{"activityId": n} for n in range(1, 22)]
        with patch.object(personal, "request", side_effect=[json.dumps(rows[:20]), json.dumps(rows[19:])]) as get:
            result = PersonalReader().get_activities_by_date("2026-01-01", "2026-01-14")
        self.assertEqual(result, rows)
        self.assertIn("start=20&limit=20&startDate=2026-01-01&endDate=2026-01-14", get.call_args.args[1])

    def test_export_and_planner_keep_zero_load_and_missing_identity(self):
        listing = {"activityId": 42, "activityType": {"typeKey": "strength_training"},
                   "startTimeLocal": "2026-01-10 12:00:00"}
        reference = [{"set_type": "rest"}, {"set_type": "active", "repetitions": 12, "weight": 0}]
        with tempfile.TemporaryDirectory() as folder, patch.object(personal, "request", side_effect=[
                json.dumps([listing]), json.dumps({"activityId": 42})]), patch.object(
                personal, "read_fit_sets", return_value=reference):
            output = Path(folder) / "history.json"
            self.assertEqual(download.main(["--source", "personal", "--activity-type", "all",
                "--time-range", "2026-01-01..2026-01-14", "--output", str(output)]), 0)
            row = summarize_activity(json.loads(output.read_text())["activities"][0])
        self.assertEqual(row["activity_type"], "strength_training")
        self.assertEqual(row["first_exercise_sets"][1], {
            "setType": "ACTIVE", "repetitionCount": 12, "load": 0, "loadUnit": "kg"})
        self.assertIn("exercise subtype missing on some or all active FIT sets", row["unavailable_fields"])
        self.assertIn("time_series", row["unavailable_fields"])
