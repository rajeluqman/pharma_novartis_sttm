# Spark + Delta — DEMONSTRATION track (ADR-007)

Non-production. Read `docs/ADR/ADR-007-spark-delta-demonstration-track.md` first — this file
documents what the track honestly does and does not prove (ADR-007 B9), so neither this repo's
docs nor any resume narrative built from it over-claim.

## What this demonstrates (real, locally verified)

- The Spark DataFrame/SQL API against a real `SparkSession` (`local[*]`).
- Catalyst/AQE query plans on real data (the ADR-001 star, read from `gold/_current/`).
- The Delta Lake transaction log: real `write.format("delta")`, `OPTIMIZE ... ZORDER BY (...)`,
  and time-travel-capable history — against real Delta tables on S3-compatible storage (MinIO
  locally; B4's real-AWS staging bucket once provisioned).
- Hadoop's S3A connector (`spark.hadoop.fs.s3a.*`) as a structurally separate client from
  DuckDB's httpfs — a second, independently-guarded path to S3 (`scripts/spark_gym_guard.py`).
- A two-engine reconciliation: the Delta slice's row count and key set are proven to exactly
  match the DuckDB mart for the same `gold/_current/` snapshot (`spark/jobs/reconcile.py`,
  ADR-007 B8) — not asserted, run and printed.

## What `local[*]` is capable of, not yet exercised by current code

ADR-007 B9 names broadcast-vs-sort-merge join selection as something `local[*]`'s own planner
is capable of demonstrating. **Be precise about this one**: neither `build_delta_slice.py` nor
`reconcile.py` runs an actual Spark join today (the reconciliation in `reconcile.py` diffs
driver-collected key sets in Python, not a Spark-side join) — so this has NOT yet been run and
observed in this repo, unlike every bullet above. Don't cite it as verified until a job here
actually runs `df.explain()` on a real join over these tables and the plan is captured.

## What this does NOT demonstrate (permanent fidelity ceiling, by design)

- **No real shuffle across executors.** `local[*]` runs every task as a thread in one JVM on
  one machine — there is no network shuffle, no executor-to-executor data movement, and
  nothing here exercises shuffle tuning (partition counts, skew handling, spill behavior)
  the way a real multi-node cluster would.
- **No executor loss/recovery.** There is exactly one process; Spark's executor-failure
  recovery path (re-running lost tasks, lineage-based recomputation across a cluster) is
  never exercised.
- **No dynamic allocation.** `local[*]` has a fixed thread count for the life of the
  `SparkSession`; nothing here shows executors scaling up/down with load.
- **Never a managed cluster.** This never submits to Glue, EMR, Databricks, or any paid
  compute (ADR-007 fence principle #2) — `master("local[*]")` is hardcoded in
  `spark_session_factory.py`, not configurable.
- **Never the system of record.** DuckDB+S3 remains the sole system of record (ADR-007 B8(a)).
  The Delta slice lives only in the staging bucket; nothing here is read by Snowflake/serving
  or published to `gold/_current/`.

This is analogous to ADR-006-A1's MinIO substrate limit for the Incident-Response gym
(`L-SNO-03`, Snowflake `REFRESH` staleness): an accepted, disclosed ceiling, not a gap to
silently close later.

## Scope boundary

Glue-ready code stays code — this track does not balloon into unused Glue IaC. Step Functions
are explicitly OUT of ADR-007 scope. AWS Lambda/Glue remain rejected as production compute per
ADR-005; nothing in this track revisits that.

## Layout

| Path | Purpose |
|---|---|
| `spark/spark_session_factory.py` | The ONLY allowed way to construct a `SparkSession` here — calls `scripts/spark_gym_guard.py`'s `assert_spark_gym_safe()` first (abort-before-JVM); CI greps for any other `SparkSession.builder` use under `spark/`. |
| `spark/jobs/build_delta_slice.py` | Reads the ADR-001 star read-only from `gold/_current/`, writes Delta + `OPTIMIZE ZORDER` to the Spark staging bucket. |
| `spark/jobs/reconcile.py` | ADR-007 B8 — Spark+Delta slice vs the DuckDB mart, row count + key set, same snapshot. |

Run via the new `spark_delta_demo_v1` Airflow DAG (`airflow/dags/spark_delta_demo_dag.py`,
manual/demo trigger, `schedule=None` — never on the production 03:00 schedule), or directly:

```bash
set -a; source gym.env; set +a
export JAVA_HOME="$SPARK_JAVA_HOME"; export PATH="$JAVA_HOME/bin:$PATH"
python3 spark/jobs/build_delta_slice.py && python3 spark/jobs/reconcile.py
```
