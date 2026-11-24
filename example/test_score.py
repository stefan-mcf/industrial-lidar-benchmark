import csv
import tempfile
import unittest
from pathlib import Path

from score import FIELDS, read_rows, score


FIXTURE = Path(__file__).with_name("replay.csv")


class PairedReplayTest(unittest.TestCase):
    def test_fixture_accounting(self):
        result = score(read_rows(FIXTURE))
        total = {
            "visible": 9, "absent": 2, "unknown": 1,
            "both_within": 2, "plc_only": 2, "model_only": 3, "neither_within": 2,
            "plc_within": 4, "model_within": 5, "plc_missing": 2, "model_missing": 2,
            "plc_over_500": 2, "model_over_500": 2,
            "plc_false_detection": 1, "model_false_detection": 1,
        }
        self.assertEqual(result["all"], total)
        for dimension in ("by_recording", "by_mist"):
            groups = result[dimension].values()
            self.assertEqual({key: sum(g[key] for g in groups) for key in total}, total)
        self.assertEqual(result["by_mist"]["yes"]["visible"], 3)
        self.assertEqual(result["by_recording"]["run-02"]["plc_only"], 1)

    def parse(self, *rows, fields=FIELDS):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(fields)
                writer.writerows(rows)
            return read_rows(path)

    def test_thresholds_and_no_detection(self):
        def front(t, target, plc, model):
            return ["toy", str(t), "loading", "front", "visible", "yes", target, plc, model]

        rows = self.parse(front(0, "100.1", "200.1", "600.1"),
                          front(1, "0", "", "500.1"))
        counts = score(iter(rows))["all"]
        self.assertEqual((counts["plc_within"], counts["model_within"]), (1, 0))
        self.assertEqual((counts["plc_missing"], counts["model_missing"]), (1, 0))
        self.assertEqual((counts["plc_over_500"], counts["model_over_500"]), (0, 1))

    def test_rejects_ambiguous_or_invalid_observations(self):
        base = ["toy", "0", "loading", "rear", "visible", "unknown", "100", "50", ""]
        for field, value in [
            ("recording_id", " "), ("time_ms", "-1"), ("time_ms", "0.5"),
            ("edge", "roof"), ("phase", "idle"), ("mist", "maybe"),
            ("visibility", "absent"), ("visibility", "unknown"), ("target_mm", ""),
            ("plc_mm", "NaN"), ("model_mm", "Infinity"), ("target_mm", "-1"),
        ]:
            row = base.copy()
            row[FIELDS.index(field)] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.parse(row)
        for invalid in ([base, base], [base[:-1]], [base + ["extra"]], []):
            with self.subTest(rows=invalid), self.assertRaises(ValueError):
                self.parse(*invalid)
        with self.assertRaisesRegex(ValueError, "header"):
            self.parse(base, fields=FIELDS[:-1] + ("plc_mm",))


if __name__ == "__main__":
    unittest.main()
