"""Slack alerting (ADR-007 B7) — env-only webhook, shared by both DAGs.

Stdlib-only (no extra dependency, no pyspark/JVM) so it parses clean under the
MWAA parse gate (scripts/parse_test_mwaa.sh mounts ONLY airflow/dags/ read-only
-- importing anything from scripts/ here would fail that gate). Lives flat in
airflow/dags/ so pharma_sttm_pipeline.py and spark_delta_demo_dag.py can both
`from slack_notify import ...` the way Airflow's DAG processor expects shared
code to be colocated with the DAG files, not packaged.

SLACK_WEBHOOK_URL unset/empty => every function below is a silent no-op, never
an error -- a missing webhook must not fail a task or block a DAG run.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def notify_slack(text: str) -> None:
    """POST `text` to SLACK_WEBHOOK_URL. No-op if unset/empty OR if Slack/network is unreachable --
    a callback firing from inside Airflow's own failure-handling path must never itself raise."""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except (urllib.error.URLError, OSError):
        pass


def task_failure_callback(context: dict) -> None:
    """Airflow on_failure_callback -- wire via default_args on both DAGs."""
    dag_id = context["dag"].dag_id
    task_id = context["task_instance"].task_id
    run_id = context["run_id"]
    log_url = context["task_instance"].log_url
    notify_slack(f":rotating_light: *{dag_id}* task `{task_id}` FAILED (run `{run_id}`)\n{log_url}")


def sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis) -> None:
    """Airflow sla_miss_callback -- wire via @dag(sla_miss_callback=...).

    Only meaningful on pharma_sttm_pipeline_v1, the one DAG with an `sla=` budget
    (T055); spark_delta_demo_v1 carries no sla= field so this hook never fires there.
    """
    notify_slack(f":hourglass_flowing_sand: *{dag.dag_id}* missed SLA: `{task_list}`")
