"""Check agreement between the published result tables and the cloud metric extract."""
import hashlib
import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
BENCHMARK = json.loads((HERE / "historical-benchmark.json").read_text())
PILOT = json.loads((HERE / "databricks-pilot.json").read_text())


class PublishedResults(unittest.TestCase):
    def test_version_pin_receipt_matches_public_inputs(self):
        receipt = json.loads((HERE / "synthetic-delta-check.json").read_text())
        for name, expected in receipt["sha256"].items():
            self.assertEqual(hashlib.sha256((HERE.parent / name).read_bytes()).hexdigest(), expected)
        self.assertEqual([run["latest_table_version"] for run in receipt["runs"]], [0, 1])
        for run in receipt["runs"]:
            self.assertEqual((run["input_version"], run["mlflow_status"]), (0, "FINISHED"))
            self.assertEqual((run["plc_within"], run["model_within"], run["visible"]), (4, 5, 9))

    def test_cloud_metrics_match_benchmark(self):
        benchmark = BENCHMARK["historical_evaluation"]
        metrics = {item["key"]: item["value"] for item in PILOT["mlflow_metrics"]}
        totals = {"plc": 0, "tree": 0}
        for split in ("held_out_wash", "held_out_site"):
            for method in totals:
                prefix = f"{split}.{method}."
                self.assertEqual(metrics[prefix + "marked"], BENCHMARK["split"][split]["marked_edges"])
                totals[method] += metrics[prefix + "within_nominal_100mm"]
        self.assertEqual(totals, {"plc": benchmark["plc_within"], "tree": benchmark["azure_tree_within"]})

    def test_paired_counts_and_conditions_account_for_all_marks(self):
        data = BENCHMARK["historical_evaluation"]
        pairs = data["paired_plc_and_correction"]
        self.assertEqual(sum(pairs.values()), data["marked_edges"])
        self.assertEqual(pairs["both_within"] + pairs["only_plc_within"], data["plc_within"])
        self.assertEqual(pairs["both_within"] + pairs["only_correction_within"], data["local_correction_within"])
        conditions = list(data["condition"].values())
        for field, total in [("marks", "marked_edges"), ("plc_within", "plc_within"),
                             ("correction_within", "local_correction_within")]:
            self.assertEqual(sum(row[field] for row in conditions), data[total])


if __name__ == "__main__":
    unittest.main()
