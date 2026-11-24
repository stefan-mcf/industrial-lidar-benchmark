"""Compare two edge estimates against one independently marked replay position."""

import argparse
import csv
import json
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path


FIELDS = (
    "recording_id", "time_ms", "phase", "edge", "visibility", "mist",
    "target_mm", "plc_mm", "model_mm",
)
CHOICES = {
    "phase": ("loading", "underbody", "unloading"),
    "edge": ("front", "rear"),
    "visibility": ("visible", "absent", "unknown"),
    "mist": ("yes", "no", "unknown"),
}
PAIRED_OUTCOME = {(True, True): "both_within", (True, False): "plc_only",
                  (False, True): "model_only", (False, False): "neither_within"}


def distance(value, field):
    if value == "":
        return None
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"{field} must be a number or empty") from None
    if not result.is_finite() or result < 0:
        raise ValueError(f"{field} must be finite and nonnegative")
    return result


def read_rows(path):
    rows, seen = [], set()
    with Path(path).open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, strict=True)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("unexpected CSV header: expected " + ",".join(FIELDS))
        for row in reader:
            try:
                if None in row or None in row.values():
                    raise ValueError("incorrect field count")
                identifier = row["recording_id"]
                if not identifier or identifier != identifier.strip():
                    raise ValueError("recording_id must be nonblank and trimmed")
                if not row["time_ms"].isascii() or not row["time_ms"].isdecimal():
                    raise ValueError("time_ms must be a nonnegative integer")
                row["time_ms"] = int(row["time_ms"])
                for field, options in CHOICES.items():
                    if row[field] not in options:
                        raise ValueError(f"{field} must be one of {', '.join(options)}")
                for field in ("target_mm", "plc_mm", "model_mm"):
                    row[field] = distance(row[field], field)
                if (row["visibility"] == "visible") != (row["target_mm"] is not None):
                    raise ValueError("target_mm is required only for a visible edge")
                key = (row["recording_id"], row["time_ms"], row["edge"])
                if key in seen:
                    raise ValueError(f"duplicate recording/time/edge: {key}")
                seen.add(key)
            except ValueError as error:
                raise ValueError(f"line {reader.line_num}: {error}") from None
            rows.append(row)
    if not rows:
        raise ValueError("CSV contains no observations")
    return rows


def counts(rows):
    result = dict.fromkeys(("visible", "absent", "unknown", "both_within",
                            "plc_only", "model_only", "neither_within"), 0)
    for method in ("plc", "model"):
        for metric in ("within", "missing", "over_500", "false_detection"):
            result[f"{method}_{metric}"] = 0
    for row in rows:
        visibility = row["visibility"]
        result[visibility] += 1
        if visibility == "absent":
            for method in ("plc", "model"):
                result[f"{method}_false_detection"] += int(row[f"{method}_mm"] is not None)
        if visibility != "visible":
            continue
        passed = []
        for method in ("plc", "model"):
            value = row[f"{method}_mm"]
            error = abs(value - row["target_mm"]) if value is not None else None
            within = error is not None and error <= 100
            passed.append(within)
            result[f"{method}_within"] += int(within)
            result[f"{method}_missing"] += int(value is None)
            result[f"{method}_over_500"] += int(error is not None and error > 500)
        result[PAIRED_OUTCOME[tuple(passed)]] += 1
    return result


def score(rows):
    rows = list(rows)
    by_wash, by_mist = defaultdict(list), defaultdict(list)
    for row in rows:
        by_wash[row["recording_id"]].append(row)
        by_mist[row["mist"]].append(row)
    return {
        "all": counts(rows),
        "by_mist": {key: counts(by_mist[key]) for key in CHOICES["mist"]},
        "by_recording": {key: counts(by_wash[key]) for key in sorted(by_wash)},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(score(read_rows(args.csv)), indent=2))
    except (OSError, ValueError, csv.Error) as error:
        parser.exit(2, f"{error}\n")
