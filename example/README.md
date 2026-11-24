# Paired replay example

These 12 invented observations exercise the scoring rules on three wash cycles. Each row records both estimates for the same operator-reviewed edge. The fixture contains no field measurements.

Run from the repository root with Python 3.

```sh
python3 example/score.py example/replay.csv
python3 -m unittest discover -s example
```

| Column | Meaning |
| --- | --- |
| `recording_id`, `time_ms`, `edge` | Unique observation. Time starts at zero for each recording. Each instant can have a front and a rear edge. |
| `phase` | Loading, underbody or unloading, written in lowercase. |
| `visibility` | `visible`, `absent` or `unknown`. Only visible edges have a reference position. |
| `mist` | `yes`, `no` or `unknown`. All three appear in the output. |
| `target_mm`, `plc_mm`, `model_mm` | Nominal distance from the fixture’s origin. An empty prediction means no detection. Zero is a valid position. |

The JSON reports overall counts and the same measures by recording and mist. Positions within 100 nominal mm of the reference count as correct. A missing estimate on a visible edge counts as a miss. Detected positions more than 500 nominal mm away count as large errors. A prediction on an absent edge counts as a false detection. Uncertain visibility contributes only to the unknown count.

On the nine visible edges, the PLC passes four and the candidate passes five. Three edges pass only with the candidate (`model_only`). Two pass only with the PLC (`plc_only`). Each has one false detection on the two absent edges.
