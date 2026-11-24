# Databricks notebook source
# MAGIC %md
# MAGIC # Paired scanner replay
# MAGIC
# MAGIC Reproduce the public CSV score on Delta Lake and record the result in MLflow. Both estimates and all operator marks in this file are invented.
# MAGIC
# MAGIC Open this notebook from the cloned project in a Databricks Git folder on a Unity Catalog cluster with Databricks Runtime ML 15.4 LTS or later. Run the widget cell, enter a catalog and scratch schema where you can create and read managed tables, then run the remaining cells. Each distinct fixture creates one small table. Repeated runs reuse its first version and create a new MLflow run.

# COMMAND ----------

dbutils.widgets.text("catalog", "", "Catalog")
dbutils.widgets.text("schema", "", "Scratch schema")

# COMMAND ----------

import hashlib
import re
import sys
from pathlib import Path

import mlflow

repo = Path.cwd().parent
sys.path.insert(0, str(repo))
from example.score import read_rows, score

fixture_path = repo / "example" / "replay.csv"
reviews = read_rows(fixture_path)
fixture_hash = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
catalog, schema = (dbutils.widgets.get(k).strip() for k in ("catalog", "schema"))
if not all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", s) for s in (catalog, schema)):
    raise ValueError("Enter a catalog and scratch schema using letters, numbers and underscores.")
table = f"`{catalog}`.`{schema}`.`lidar_replay_{fixture_hash[:16]}`"

fixture = spark.createDataFrame(reviews, schema="""
    recording_id STRING, time_ms BIGINT, phase STRING, edge STRING, visibility STRING,
    mist STRING, target_mm DECIMAL(30,12), plc_mm DECIMAL(30,12), model_mm DECIMAL(30,12)
""")
fixture.write.format("delta").mode("ignore").saveAsTable(table)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Pin the input
# MAGIC
# MAGIC Version 0 must match the fixture in both directions, including duplicate counts. This also checks an existing table before reuse.

# COMMAND ----------

pinned = spark.sql(f"SELECT * FROM {table} VERSION AS OF 0")
if fixture.exceptAll(pinned).take(1) or pinned.exceptAll(fixture).take(1):
    raise ValueError("Version 0 differs from the public fixture.")
pinned.createOrReplaceTempView("lidar_replay_pinned")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Score both methods against the same marked end
# MAGIC
# MAGIC A missing prediction on a visible end is a miss. Absent and uncertain ends have separate counts in the reference report.

# COMMAND ----------

paired = spark.sql("""
    WITH decisions AS (
        SELECT recording_id, mist,
               coalesce(abs(plc_mm - target_mm) <= 100, false) AS plc_pass,
               coalesce(abs(model_mm - target_mm) <= 100, false) AS model_pass
        FROM lidar_replay_pinned
        WHERE visibility = 'visible'
    )
    SELECT recording_id, mist, count(*) AS visible,
           count_if(plc_pass AND model_pass) AS both_within,
           count_if(plc_pass AND NOT model_pass) AS plc_only,
           count_if(model_pass AND NOT plc_pass) AS model_only,
           count_if(NOT plc_pass AND NOT model_pass) AS neither_within
    FROM decisions
    GROUP BY GROUPING SETS ((), (recording_id), (mist))
""")

reference = score(reviews)
for record in paired.collect():
    counters = record.asDict()
    recording, mist = counters.pop("recording_id"), counters.pop("mist")
    if recording is not None:
        expected = reference["by_recording"][recording]
    elif mist is not None:
        expected = reference["by_mist"][mist]
    else:
        expected = reference["all"]
    if any(value != expected[key] for key, value in counters.items()):
        raise ValueError(f"Spark and the reference scorer disagree for {recording=}, {mist=}.")

# COMMAND ----------

with mlflow.start_run(run_name="synthetic-paired-replay") as run:
    mlflow.set_tag("data_origin", "synthetic")
    mlflow.log_params({
        "fixture_sha256": fixture_hash, "delta_table": table, "delta_version": 0,
        "tolerance_mm": 100, "scorer_sha256": hashlib.sha256((repo / "example/score.py").read_bytes()).hexdigest(),
    })
    mlflow.log_metrics(reference["all"])
    mlflow.log_dict(reference, "paired_counts.json")
    print(f"MLflow run {run.info.run_id}")

paired.orderBy("recording_id", "mist").show()
