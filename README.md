# Vehicle-edge tracking in mist

**I recommended keeping the existing controller.** In a vehicle wash, two laser scanners track the front and rear of each vehicle. When a scanner picks up mist, the reported edge can jump. I built a replay benchmark to test when a model should override the programmable logic controller (PLC).

| Method | Where it ran | Within 100 nominal mm |
|---|---|---:|
| Existing controller | Recorded PLC output | 83 / 106 |
| Shallow decision tree | Azure Databricks CPU job | 53 / 106 |
| Selective correction | Local training and evaluation, tracked in Azure-hosted MLflow | 85 / 106 |

In confirmed mist, the PLC and the correction passed on the same five of six marks. The operator saw no mist at any of the seven positions the correction changed. [Historical results](evidence/historical-benchmark.json) · [Databricks run extract](evidence/databricks-pilot.json)

![Paired comparison of 106 marked edges. Both methods passed on 81, only the correction passed on four, only the PLC passed on two, and both missed on 19.](evidence/paired-outcomes.png)

## How I tested it

An equipment operator marked visible vehicle edges in the replay. I matched the marks to individual scanner frames and kept complete wash cycles together when splitting the data. Eight cycles supplied 332 development marks. The evaluation used 106 marks from four other cycles, including two from a site outside the development set. A mark counts as a pass within 100 nominal mm on the replay scale. Physical position accuracy would require an independent measurement in the bay.

The correction could change the rear edge during underbody scanning and the front edge during unloading. Both methods still produced 13 errors over 500 nominal mm. The four evaluation cycles had already been examined during the first pilot. My evaluation ended at offline replay. A deployment decision would need fresh mist-affected cycles, closely spaced marks around jumps and a timing check on the PLC.

## What ran on Azure Databricks

I wrote 1,232 observations and 21,457 candidate beam groups to two Unity Catalog managed Delta tables. The training job read version 0 of both tables and compared the rows with the staged inputs in both directions. It logged the input hashes, model and evaluation metrics in MLflow.

The first job failed while reading package metadata after it had logged scores. The corrected run finished with the same 99 metric values. Both single-node clusters terminated. The published extract includes the CPU job settings, Delta versions and held-out MLflow metrics.

## Run the paired comparison

The public example uses 12 invented observations. It shows how the scoring handles a missing estimate, an absent vehicle edge and an uncertain label. Run from the repository root with Python 3.10 or later.

```sh
python3 example/score.py example/replay.csv
python3 -m unittest discover -s example
python3 -m unittest discover -s evidence
```

The first command reports four PLC passes and five model passes on nine visible edges in the example. The notebook scores the fixture in Spark SQL and logs the input version and results in MLflow. [Fixture and scoring rules](example/README.md) · [Databricks notebook](databricks/replay.py)

In a local test I changed the PLC values in Delta version 1. The notebook still read version 0. Both MLflow runs returned the original scores, and their saved results matched the Python scorer for every group. [Version-pinning test results](evidence/synthetic-delta-check.json)
