"""Spark + Delta DEMONSTRATION track (ADR-007) — separate, non-production DAG.

Fence principle #1 (additive, never substitutive): this DAG is independent of
pharma_sttm_pipeline_v1 and carries no schedule of its own (manual/demo trigger only —
schedule=None). It never feeds Snowflake/serving and never publishes to gold/_current/
(ADR-007 B8(a)) — DuckDB+S3 remains the sole system of record.

DAG subprocess shape (ADR-007 B5, mirrors pharma_sttm_pipeline_v1's `run()` pattern): task
bodies shell out to spark/jobs/*.py rather than importing pyspark at DAG-parse time, so this
file parses clean under parse_test_mwaa.sh even though the MWAA runner has no pyspark
installed. Each task is its own subprocess/JVM; state crosses the task boundary via the
Spark staging bucket's Delta tables (S3-staging-backed handoff), NOT shared in-process
memory — the multi-subprocess-shared-state trap O-AIR-07 hit on the ephemeral DuckDB
catalog must not be repeated here.

Requires SPARK_*/SPARK_JAVA_HOME (gym.env) and scripts/spark_gym_guard.py green in the
invoking environment — see spark/spark_session_factory.py. Both tasks abort before
touching the JVM if the guard fails.
"""
from __future__ import annotations

import os
import pathlib
import subprocess

import pendulum
from airflow.decorators import dag, task

from slack_notify import task_failure_callback

START = pendulum.datetime(2026, 6, 1, tz="UTC")
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def run(cmd: list[str]) -> None:
    """Shell out to a spark/jobs/*.py script; stream output into the task log.

    Overrides JAVA_HOME (and prepends its bin/ to PATH) to the Java 21 candidate pinned by
    ADR-007 B2 — the Codespace/MWAA default Java is NOT compatible with Spark 3.5.x.
    """
    java_home = os.environ.get("SPARK_JAVA_HOME", "")
    env = {**os.environ}
    if java_home:
        env["JAVA_HOME"] = java_home
        env["PATH"] = f"{java_home}/bin:{env.get('PATH', '')}"
    subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, check=True)


@dag(
    dag_id="spark_delta_demo_v1",
    schedule=None,  # manual/demo trigger only — never on the production 03:00 schedule
    start_date=START,
    catchup=False,
    default_args={
        "retries": 0,  # demonstration track — a failed drill is investigated, not auto-retried
        "execution_timeout": pendulum.duration(minutes=30),
        "on_failure_callback": task_failure_callback,  # ADR-007 B7 — Slack on task failure
    },
    tags=["demonstration", "spark", "delta", "non-production"],
)
def spark_delta_demo():
    @task
    def build_delta_slice():
        # Reads gold/_current/ (read-only) from SPARK_READ_S3_BUCKET, writes Delta tables +
        # OPTIMIZE ZORDER into SPARK_S3_BUCKET (the separate Spark staging bucket).
        run(["python3", "spark/jobs/build_delta_slice.py"])

    @task
    def reconcile():
        # ADR-007 B8: Spark+Delta slice must row-count + key-set match the DuckDB mart for
        # the same gold/_current/ snapshot. Exits non-zero on any divergence.
        run(["python3", "spark/jobs/reconcile.py"])

    build_delta_slice() >> reconcile()


spark_delta_demo()
