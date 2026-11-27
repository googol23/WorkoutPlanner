from importlib.util import find_spec
from io import BytesIO
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from workoutplanner.garmin import download, endurance, personal
from workoutplanner.garmin.personal_reader import PersonalReader


class EnduranceFitTests(unittest.TestCase):
    @unittest.skipUnless(find_spec("garmin_fit_sdk"), "optional FIT decoder")
    def test_export_original_laps_and_session_zones_once(self):
        from garmin_fit_sdk import Encoder
        encoder = Encoder()
        encoder.on_mesg(19, {"total_distance": 1000, "avg_heart_rate": 140, "total_timer_time": 300})
        encoder.on_mesg(18, {"time_in_power_zone": [0, 0, 300]})
        encoder.on_mesg(216, {"reference_mesg": "lap", "time_in_hr_zone": [0, 70, 20]})
        encoder.on_mesg(216, {"reference_mesg": "session", "time_in_hr_zone": [10, 90, 200]})
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("activity.fit", encoder.close())
        with patch.object(personal, "exchange", return_value="token"), patch.object(personal, "load_key"), patch.object(
                personal, "request", side_effect=[b'{"activityId":42}', buffer.getvalue()]) as request:
            row = download.export_activity(PersonalReader(), {"activityId": 42,
                "activityType": {"typeKey": "cycling"}}, activity_type="all")
        self.assertEqual(request.call_count, 2)
        self.assertEqual(row["splits"]["lapDTOs"], [{"duration": 300, "distance": 1000, "averageHR": 140}])
        self.assertEqual(row["heart_rate_zones"], [{"zoneNumber": 1, "secsInZone": 90},
                                                 {"zoneNumber": 2, "secsInZone": 200}])
        self.assertEqual(row["power_zones"][0], {"zoneNumber": 1, "secsInZone": 0})
        self.assertNotIn("get_activity_splits", row["unavailable_fields"])

    def test_no_session_totals_from_lap_or_multisport_zones(self):
        messages = {"time_in_zone_mesgs": [{"reference_mesg": "lap", "time_in_hr_zone": [0, 42]}]}
        self.assertFalse(endurance.planner_sections(messages)["heart_rate_zones"])
        self.assertFalse(endurance.planner_sections({**messages, "session_mesgs": [{}, {}]}))

    def test_running_lap_cadence_includes_both_steps_and_fraction(self):
        messages = {"session_mesgs": [{"sport": "running"}], "lap_mesgs": [
            {"avg_running_cadence": 81, "avg_fractional_cadence": 0.5},
            {"avg_cadence": 0}, {"sport": "cycling", "avg_cadence": 92, "total_distance": 100}]}
        laps = endurance.planner_sections(messages)["splits"]["lapDTOs"]
        self.assertEqual(laps, [{"averageRunCadence": 163}, {"averageRunCadence": 0}, {"distance": 100}])
