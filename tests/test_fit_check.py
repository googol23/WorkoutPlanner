from contextlib import redirect_stdout
from importlib.util import find_spec
from io import BytesIO, StringIO
import unittest
from zipfile import ZipFile

from workoutplanner.garmin import fit_check


class FitCheckTests(unittest.TestCase):
    @unittest.skipUnless(find_spec("garmin_fit_sdk"), "optional FIT decoder")
    def test_actual_fit_round_trip(self):
        from garmin_fit_sdk import Encoder

        encoder = Encoder()
        encoder.on_mesg(225, {"set_type": "rest", "duration": 20})
        encoder.on_mesg(225, {"set_type": "active", "repetitions": 8, "weight": 12.5})
        stream = BytesIO()
        with ZipFile(stream, "w") as archive:
            archive.writestr("ACTIVITY.FIT", encoder.close())
        rows = fit_check.decode_sets(stream.getvalue())
        output = StringIO()
        with redirect_stdout(output):
            fit_check.report([{"setType": "REST"}, {"setType": "ACTIVE", "repetitionCount": 8,
                                                     "weightInGrams": 12500}], rows)
        self.assertIn("original FIT 2", output.getvalue())
        self.assertIn("repetitions: match", output.getvalue())
        self.assertIn("loads in returned order: match", output.getvalue())

    def test_missing_values_do_not_imply_parity(self):
        output = StringIO()
        with redirect_stdout(output):
            fit_check.report([{"setType": "ACTIVE", "weight": 10000}], [{"set_type": "active"}])
        self.assertIn("comparison unavailable", output.getvalue())
        self.assertIn("Load equivalence unverified", output.getvalue())
