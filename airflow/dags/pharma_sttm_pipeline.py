"""Consolidated daily pipeline — Helvetia Pharma enVision.

Topology (ADR-002): Landing -> Bronze -> Enrich -> Gold (star + OBT).
Three divergent sources (alpha/beta/gamma) converge into one governed mart.
SLA: complete by 07:00 (03:00 start, 240-min budget) — the JD #1 drill.

Wired to the real ingestion scripts / dbt commands (Phase 4 build). Runs on
aws-mwaa-local-runner locally, AWS MWAA in the cloud — task bodies shell out
via subprocess so no extra orchestration package (e.g. Cosmos) is required.
"""
from __future__ import annotations

import os
import pathlib
import subprocess

import pendulum
from airflow.decorators import dag, task, task_group

from slack_notify import sla_miss_callback, task_failure_callback

START = pendulum.datetime(2026, 6, 1, tz="UTC")
SLA = pendulum.duration(minutes=240)  # 03:00 -> 07:00

# DAG file lives at <repo_root>/airflow/dags/pharma_sttm_pipeline.py
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DBT_PROJECT_DIR = REPO_ROOT / "dbt"


def run(cmd: list[str], *, cwd: pathlib.Path = REPO_ROOT, extra_env: dict | None = None) -> None:
    """Shell out to a real script/dbt command; stream output into the task log."""
    env = {**os.environ, **(extra_env or {})}
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True)


def dbt(*args: str, run_id: str | None = None) -> None:
    cmd = ["dbt", *args, "--project-dir", str(DBT_PROJECT_DIR), "--profiles-dir", str(DBT_PROJECT_DIR)]
    if run_id is not None:
        cmd += ["--vars", f'{{"run_id": "{run_id}"}}']
    run(cmd)


def gold_run_id(ts_nodash: str) -> str:
    # O-AIR-01: one run_id per DAG run (shared by every dbt(...) call below), so marts/serving
    # write to the SAME gold/<run_id>/ prefix and publish_gold() publishes exactly that prefix.
    # ts_nodash is the DAG run's logical timestamp (identical across every task in this run, not
    # wall-clock task time), so each task can derive it independently without passing it via XCom.
    return f"run-{ts_nodash}"


@dag(
    dag_id="pharma_sttm_pipeline_v1",   # T080 — version in id; mirrors STTM v2 / AH v2 convention
    schedule="0 3 * * *",          # 03:00 daily
    start_date=START,
    catchup=False,
    default_args={
        "sla": SLA,                                          # T055 — 7AM SLA breach alerting
        "execution_timeout": pendulum.duration(minutes=30),  # T051 — no task hangs past its slice of the 240-min budget
        "retries": 2,                                        # T052 — absorb transient blips (safe: tasks idempotent, T010)
        "retry_delay": pendulum.duration(minutes=5),         # T053 — give external systems time to recover
        "on_failure_callback": task_failure_callback,        # ADR-007 B7 — Slack on task failure
    },
    sla_miss_callback=sla_miss_callback,  # ADR-007 B7 — makes T055's `sla=SLA` budget actually alert
    tags=["enVision", "pharma", "sttm", "medallion"],
)
def pharma_sttm_pipeline():
    @task_group(group_id="alpha")
    def alpha():
        @task
        def land(ds=None):  # scripts/ingest_alpha_sales.sh -> landing/alpha
            run(["bash", "scripts/ingest_alpha_sales.sh"], extra_env={"LAND_DIR": f"data/landing/alpha/{ds}"})

        @task
        def bronze(ds=None):  # land -> bronze.alpha (+load meta)
            run(["python3", "scripts/load_bronze.py"], extra_env={"LAND_DATE": ds})

        land() >> bronze()

    @task_group(group_id="beta")
    def beta():
        @task(retry_exponential_backoff=True)  # T054 — don't hammer a struggling openFDA API on retry
        def land(ds=None):  # scripts/ingest_beta_ndc.py -> landing/beta
            run(["python3", "scripts/ingest_beta_ndc.py"], extra_env={"LAND_DIR": f"data/landing/beta/{ds}"})

        @task
        def bronze(ds=None):
            run(["python3", "scripts/load_bronze.py"], extra_env={"LAND_DATE": ds})

        land() >> bronze()

    @task_group(group_id="gamma")
    def gamma():
        @task
        def land(ds=None):  # scripts/ingest_gamma_reviews.sh -> landing/gamma
            run(["bash", "scripts/ingest_gamma_reviews.sh"], extra_env={"LAND_DIR": f"data/landing/gamma/{ds}"})

        @task
        def bronze(ds=None):
            run(["python3", "scripts/load_bronze.py"], extra_env={"LAND_DATE": ds})

        land() >> bronze()

    @task
    def dbt_seed(ts_nodash=None):  # static ATC crosswalk reference data -> persisted to S3 via seed roundtrip
        # O-AIR-07: the orchestrated DAG previously never seeded; the seed table is :memory: only,
        # so marts.core (a separate subprocess) couldn't read atc_pharmclass_crosswalk. `dbt seed`
        # builds it and the on-run-end hook exports it to s3://.../silver/seeds/ for cross-task reads.
        dbt("seed", run_id=gold_run_id(ts_nodash))

    @task
    def dbt_enrich(ts_nodash=None):  # dbt run -s staging  (per-source Silver, divergent)
        dbt("run", "-s", "staging", run_id=gold_run_id(ts_nodash))

    @task
    def dbt_marts(ts_nodash=None):  # dbt snapshot (dim_drug SCD2 source) then dbt run -s marts.core (STAR)
        run_id = gold_run_id(ts_nodash)
        dbt("snapshot", run_id=run_id)          # snap_beta_ndc must exist before dim_drug builds from it
        dbt("run", "-s", "marts.core", run_id=run_id)

    @task
    def dbt_serving(ts_nodash=None):  # dbt run -s marts.serving  (OBT from star)
        dbt("run", "-s", "marts.serving", run_id=gold_run_id(ts_nodash))

    @task
    def dbt_test(ts_nodash=None):  # dbt schema/data tests against THIS run's unpublished gold/<run_id>/
        dbt("test", run_id=gold_run_id(ts_nodash))

    @task
    def publish_gold(ts_nodash=None):
        # O-AIR-01: verify-then-copy this run's gold/<run_id>/ into the fixed gold/_current/
        # pointer (scripts/publish_gold.py) so Snowflake + GE validation see THIS run, not a
        # permanently-stale gold/dev/ that nothing downstream ever reads.
        run(["python3", "scripts/publish_gold.py", "--run-id", gold_run_id(ts_nodash)])

    @task
    def dq_validate():  # great_expectations + crosswalk coverage KPI (ADR-003)
        # Runs AFTER publish_gold, not before: run_ge_validation.py reads ONLY gold/_current/
        # (scripts/run_ge_validation.py's gold_current() helper), so running it pre-publish would
        # just re-validate the PREVIOUS run's already-validated data, never this run's output.
        # Mirrors the proven order in scripts/run_pipeline_aws.sh (build -> publish -> GE).
        run(["python3", "scripts/run_ge_validation.py"])

    # bronze for all 3 (+ seed reference data) -> enrich -> consolidate marts -> OBT ->
    # test (gates on THIS run's unpublished gold/<run_id>/) -> publish -> GE smoke test on _current
    (
        [alpha(), beta(), gamma(), dbt_seed()]
        >> dbt_enrich()
        >> dbt_marts()
        >> dbt_serving()
        >> dbt_test()
        >> publish_gold()
        >> dq_validate()
    )


pharma_sttm_pipeline()
