"""Offline tests for the planning input contract."""

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import build_planning_input as planner


class PlanningInputTests(unittest.TestCase):
    def setUp(self):
        self.athlete = {"goals": "Build endurance", "availability": "30 minutes",
                        "recent_feedback": "Legs felt fresh"}
        self.history = {
            "schema_version": "1.0",
            "exported_at": "2026-11-24T10:00:00+00:00",
            "activities": [
                {"activity_id": 1, "summary": {"activityType": {"typeKey": "running"},
                                               "distance": 5000, "duration": 1800},
                 "time_series": {"metric_descriptors": [{"key": "directHeartRate", "unit": "bpm"}],
                                 "samples": [{"metrics": {"directHeartRate": 140}}]},
                 "subjective_feedback": {"perceived_effort": 5}},
                {"activity_id": 2, "summary": {"activityType": {"typeKey": "cycling"},
                                               "averagePower": 175},
                 "power_zones": [{"zone": 2, "secsInZone": 600}]},
                {"activity_id": 3, "summary": {"activityType": {"typeKey": "indoor_climbing"},
                                               "duration": 900},
                 "time_series": None, "unavailable_fields": ["time_series"]},
            ],
        }

    def test_cli_preserves_sport_metrics_and_missing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            activities = Path(tmp) / "activities.json"
            athlete = Path(tmp) / "athlete.json"
            activities.write_text(json.dumps(self.history), encoding="utf-8")
            athlete.write_text(json.dumps(self.athlete), encoding="utf-8")
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(planner.main(["--activities", str(activities),
                                               "--athlete", str(athlete),
                                               "--activity-type", "bouldering"]), 0)
        self.assertEqual(json.loads(output.getvalue()), {
            "schema_version": "1.0", "target_activity_type": "bouldering",
            "athlete": self.athlete, "activity_history": self.history,
        })

    def test_rejects_unrecognized_export_and_missing_goals(self):
        with self.assertRaisesRegex(ValueError, "schema_version"):
            planner.build_input({**self.history, "schema_version": "2.0"}, self.athlete, "running")
        with self.assertRaisesRegex(ValueError, "goals"):
            planner.build_input(self.history, {"availability": "30 minutes"}, "running")
        with self.assertRaisesRegex(ValueError, "summary"):
            planner.build_input({**self.history, "activities": [{}]}, self.athlete, "running")

    def test_invalid_target_exits_before_reading_files(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            planner.main(["--activities", "missing.json", "--athlete", "missing.json",
                          "--activity-type", "all"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
