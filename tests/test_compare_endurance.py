from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import Mock, patch

from workoutplanner.garmin import compare_endurance as probe


class EnduranceComparisonTests(unittest.TestCase):
    def test_same_id_for_both_readers_and_no_raw_values(self):
        run = {"activityId": 123456789, "activityType": {"typeKey": "trail_running"}}
        personal = Mock()
        personal.get_activities.side_effect = [[dict(run, inProgress=True), run], []]
        records = [
            {"summary": {"summaryDTO": {"distance": 98765, "averageHR": 156}}, "splits": [{"distance": 100}]},
            {"summary": {"summaryDTO": {"distance": 98765, "averageHR": 150, "maxHR": 161}}},
        ]
        legacy = Mock()
        out = StringIO()
        with patch.object(probe, "export_activity", side_effect=records) as read, redirect_stdout(out):
            probe.compare(legacy, personal)
        self.assertEqual([call.args for call in read.call_args_list], [(legacy, run), (personal, run)])
        for part in ("1 matching fields", "different: averageHR", "personal only: maxHR",
                     "legacy only: first_splits", "cycling: no completed activity"):
            self.assertIn(part, out.getvalue())
        for value in ("123456789", "98765", "156"):
            self.assertNotIn(value, out.getvalue())

    def test_repeating_pages_fail_without_looping(self):
        reader = Mock()
        reader.get_activities.return_value = [{"activityId": 1, "inProgress": True}] * 20
        with self.assertRaisesRegex(RuntimeError, "repeated"):
            probe.latest(reader, "cycling")

    def test_aligns_by_zone_number_and_counts_missing_separately(self):
        out = StringIO()
        with redirect_stdout(out):
            probe.compare_rows("heart_rate_zones",
                [{"zoneNumber": 2, "secsInZone": 110, "zoneLowBoundary": 133},
                 {"zoneNumber": 1, "secsInZone": 0}],
                [{"zoneNumber": 1, "secsInZone": 0}, {"zoneNumber": 2, "secsInZone": 109.9},
                 {"zoneNumber": 3, "secsInZone": 5}])
        self.assertIn("personal-only zone numbers: 3", out.getvalue())
        self.assertIn("secsInZone: 1 / 1 / 0 / 0", out.getvalue())
        self.assertIn("zoneLowBoundary: 0 / 0 / 1 / 0", out.getvalue())
        self.assertNotIn("133", out.getvalue())
