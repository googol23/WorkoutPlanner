"""Offline tests for the read-only running activity exporter."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from workoutplanner.garmin import download as exporter


def run(activity_id, kind="running", **extra):
    return {"activityId": activity_id, "activityType": {"typeKey": kind},
            "activityName": "Morning Run", "startTimeLocal": "2026-11-23 08:00:00",
            "distance": 5000, "duration": 1500, **extra}


class DownloadTests(unittest.TestCase):
    def api(self):
        api = Mock()
        api.get_activity.side_effect = lambda activity_id: run(int(activity_id),
            userId=19, latitude=1.5, nested={"heartRate": 130, "longitude": 3})
        api.get_activity_details.return_value = {
            "metricDescriptors": [
                {"metricsIndex": 0, "key": "directTimestamp", "unit": "milliseconds"},
                {"metricsIndex": 1, "key": "directHeartRate", "unit": "bpm"},
                {"metricsIndex": 2, "key": "directLatitude", "unit": "degrees"},
                {"metricsIndex": 3, "key": "directSpeed", "unit": "m/s"},
                {"metricsIndex": 4, "key": "directLon", "unit": "degrees"},
            ],
            "activityDetailMetrics": [{"metrics": [1700000000000, 130, 52.0, 3.5, 13.0]}],
            "geoPolyline": {"points": [1, 2]},
        }
        api.get_activity_splits.return_value = {"lapDTOs": [{"distance": 1000, "startTimeGMT": "2026-11-23 07:00:00", "ownerId": 11, "startPoint": {"lat": 52, "lon": 13}}]}
        api.get_activity_step_details.return_value = {"steps": [{"power": 200, "positionLat": 52}]}
        api.get_activity_hr_in_timezones.return_value = [{"zone": 2, "secsInZone": 120}]
        api.get_activity_power_in_timezones.return_value = [{"zone": 3, "secsInZone": 60}]
        api.get_activity_weather.return_value = {"temperature": 12, "location": "Home"}
        return api

    def test_recent_runs_paged_and_filtered(self):
        api = self.api()
        page = [run(100 - i, "cycling" if i == 0 else "running") for i in range(20)]
        page[2]["inProgress"] = True
        api.get_activities.side_effect = [page, [run(42, "running"), run(41, "walking")]]
        found = exporter.recent_runs(api, 19)
        self.assertEqual(len(found), 19)
        self.assertEqual(found[-1]["activityId"], 42)
        self.assertEqual(api.get_activities.call_args_list[1].kwargs,
                         {"start": 20, "limit": 20, "activitytype": "running"})

    def test_export_privacy_and_metrics(self):
        api = self.api()
        result = exporter.export_activity(api, run(42), {"perceived_effort": 7})
        self.assertEqual(result["time_series"]["samples"],
                         [{"metrics": {"directTimestamp": 1700000000000,
                                       "directHeartRate": 130, "directSpeed": 3.5}}])
        self.assertEqual(result["time_series"]["metric_descriptors"][1]["unit"], "bpm")
        self.assertEqual(result["summary"]["nested"], {"heartRate": 130})
        text = json.dumps(result).lower()
        for private in ("latitude", "longitude", "userid", "ownerid", "positionlat", "geopolyline", "location", "startpoint", "\"lat\"", "\"lon\"", "directlon"):
            self.assertNotIn(private, text)
        self.assertEqual(result["splits"]["lapDTOs"][0]["distance"], 1000)
        self.assertEqual(result["subjective_feedback"], {"perceived_effort": 7})
        self.assertEqual(result["unavailable_fields"], [])
        api.get_activity.assert_called_once_with("42")
        api.get_activity_details.assert_called_once_with("42", maxpoly=0)
        api.get_activity_step_details.assert_called_once_with("42")

    def test_strength_export_keeps_exercise_sets_and_marks_empty_data(self):
        api = self.api()
        activity = run(42, "strength_training")
        api.get_activity.side_effect = None
        api.get_activity.return_value = activity
        sets = {"exerciseSets": [{"exercises": [{"category": "SQUAT", "name": "GOBLET_SQUAT"}],
                                  "repetitionCount": 10, "weight": 12000,
                                  "weightUnit": {"unitKey": "kilogram"}, "ownerId": 7}]}
        api.get_activity_exercise_sets.return_value = sets
        result = exporter.export_activity(api, activity, activity_type="strength_training")
        api.get_activity_exercise_sets.assert_called_once_with("42")
        self.assertNotIn("ownerId", result["exercise_sets"]["exerciseSets"][0])
        self.assertEqual(result["exercise_sets"]["exerciseSets"][0]["repetitionCount"], 10)

        api.get_activity_exercise_sets.return_value = {"exerciseSets": []}
        result = exporter.export_activity(api, activity, activity_type="strength_training")
        self.assertIsNone(result["exercise_sets"])
        self.assertIn("get_activity_exercise_sets", result["unavailable_fields"])

    def test_missing_optional_data(self):
        api = self.api()
        api.get_activity_splits.side_effect = exporter.GarminConnectNotFoundError("missing")
        api.get_activity_weather.return_value = None
        api.get_activity_details.return_value = {}
        result = exporter.export_activity(api, run(42))
        self.assertIsNone(result["splits"])
        self.assertIsNone(result["time_series"])
        self.assertEqual(set(result["unavailable_fields"]),
                         {"get_activity_splits", "get_activity_details", "time_series", "get_activity_weather"})

    def test_specific_id_cli_and_validation(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as tmp, patch.object(exporter, "authenticate", return_value=api):
            output = Path(tmp) / "runs.json"
            self.assertEqual(exporter.main(["--activity-id", "42", "--output", str(output),
                                            "--perceived-effort", "8", "--fatigue", "tired"]), 0)
            content = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(content["schema_version"], "1.0")
            self.assertEqual(content["activities"][0]["activity_id"], 42)
            self.assertEqual(content["activities"][0]["subjective_feedback"],
                             {"perceived_effort": 8, "fatigue": "tired"})
            api.get_activities.assert_not_called()


    def test_default_and_multiple_cli(self):
        api = self.api()
        api.get_activities.return_value = [run(42), run(41), run(40, "cycling")]
        with tempfile.TemporaryDirectory() as tmp, patch.object(exporter, "authenticate", return_value=api):
            output = Path(tmp) / "runs.json"
            self.assertEqual(exporter.main(["--output", str(output)]), 0)
            self.assertEqual(len(json.loads(output.read_text())["activities"]), 1)
            self.assertEqual(exporter.main(["--limit", "5", "--output", str(output)]), 0)
            self.assertEqual([a["activity_id"] for a in json.loads(output.read_text())["activities"]], [42, 41])
            api.get_activities.assert_any_call(start=0, limit=20, activitytype="running")

    def test_range_exports_inclusive_local_dates_for_exact_type(self):
        api = self.api()
        first = run(42, "cycling", startTimeLocal="2026-11-20 00:00:00",
                    startTimeGMT="2026-11-19 23:00:00")
        last = run(43, "cycling", startTimeLocal="2026-11-23 23:59:59")
        api.get_activities_by_date.return_value = [
            run(50, "cycling", startTimeLocal="2026-11-24 00:00:00"),
            last, first, {**first, "activityId": "42"},
            run(44, "cycling", startTimeLocal="2026-11-19 23:59:59"),
            run(45, "cycling", inProgress=True), run(46, "indoor_cycling"),
        ]
        api.get_activity.side_effect = {"42": first, "43": last}.__getitem__
        with tempfile.TemporaryDirectory() as tmp, patch.object(exporter, "authenticate", return_value=api):
            output = Path(tmp) / "rides.json"
            args = ["--time-range", "2026-11-20..2026-11-23",
                    "--activity-type", "cycling", "--output", str(output)]
            self.assertEqual(exporter.main(args), 0)
            self.assertEqual([a["activity_id"] for a in json.loads(output.read_text())["activities"]], [43, 42])
        api.get_activities_by_date.assert_called_once_with("2026-11-20", "2026-11-23")
        api.get_activities.assert_not_called()

    def test_all_types_with_limit_deduplicates_across_pages(self):
        api = self.api()
        api.get_activities.side_effect = [
            [run(42, "cycling")] + [run(42, "cycling")] * 19,
            [run("42", "cycling"), run(41, "indoor_climbing")],
        ]
        activities = exporter.recent_activities(api, 2, "all")
        self.assertEqual([item["activityId"] for item in activities], [42, 41])
        api.get_activities.assert_called_with(start=20, limit=20, activitytype=None)

    def test_invalid_selection_is_rejected_before_login(self):
        with patch.object(exporter, "authenticate") as authenticate:
            for args in (
                ["--time-range", "2026-11-23..2026-11-20"],
                ["--time-range", "2026-02-30..2026-03-01"],
                ["--time-range", "2026-11-20"],
                ["--time-range", "2026-11-20..2026-11-23", "--limit", "2"],
                ["--activity-type", "../cycling"],
            ):
                with self.subTest(args=args), self.assertRaises(SystemExit) as error:
                    exporter.main(args)
                self.assertEqual(error.exception.code, 2)
            authenticate.assert_not_called()

    def test_empty_range_leaves_existing_output_intact(self):
        api = self.api()
        api.get_activities_by_date.return_value = [run(42, "walking")]
        with tempfile.TemporaryDirectory() as tmp, patch.object(exporter, "authenticate", return_value=api):
            output = Path(tmp) / "existing.json"
            output.write_text("existing", encoding="utf-8")
            self.assertEqual(exporter.main(["--time-range", "2026-11-23..2026-11-23",
                                            "--output", str(output)]), 1)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing")
        api.get_activity.assert_not_called()

    def test_export_accepts_garmin_detail_type_dto(self):
        api = self.api()
        api.get_activity.side_effect = None
        api.get_activity.return_value = {
            "activityTypeDTO": {"typeKey": "cycling"},
            "summaryDTO": {"startTimeLocal": "2026-11-23 07:00:00"},
        }
        result = exporter.export_activity(api, run(42, "cycling"), activity_type="all")
        self.assertEqual(result["activity_date"], "2026-11-23 07:00:00")
        self.assertEqual(result["activity_name"], "Morning Run")
        result = exporter.export_activity(api, {"activityId": 42}, activity_type="cycling")
        self.assertEqual(result["summary"]["activityTypeDTO"]["typeKey"], "cycling")

    def test_export_uses_list_type_only_when_detail_type_is_missing(self):
        api = self.api()
        api.get_activity.side_effect = None
        api.get_activity.return_value = {}
        result = exporter.export_activity(api, run(42, "cycling"), activity_type="cycling")
        self.assertEqual(result["activity_date"], "2026-11-23 08:00:00")
        api.get_activity.return_value = {"activityTypeDTO": {"typeKey": "running"}}
        with self.assertRaisesRegex(RuntimeError, "not a completed cycling activity"):
            exporter.export_activity(api, run(42, "cycling"), activity_type="cycling")
        api.get_activity.return_value = {"inProgress": True}
        with self.assertRaisesRegex(RuntimeError, "not a completed cycling activity"):
            exporter.export_activity(api, run(42, "cycling"), activity_type="cycling")

    def test_specific_id_rejects_other_sports_and_no_output(self):
        api = self.api()
        api.get_activity.return_value = run(42, "cycling")
        api.get_activity.side_effect = None
        with tempfile.TemporaryDirectory() as tmp, patch.object(exporter, "authenticate", return_value=api):
            output = Path(tmp) / "runs.json"
            self.assertEqual(exporter.main(["--activity-id", "42", "--output", str(output)]), 1)
            self.assertFalse(output.exists())
            api.get_activity_details.assert_not_called()


if __name__ == "__main__":
    unittest.main()
