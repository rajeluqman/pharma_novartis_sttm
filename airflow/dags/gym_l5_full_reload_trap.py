"""SLA Gym — Round 2 (Ladder L5, Sabotage S2: redundant full-reload / no partition pruning).

SELF-PLAY: broken-and-fixed in one file via the PRUNE_TO_CURRENT switch.
Mirrors the real pipeline's bronze stage, where each daily run should touch ONLY
today's `landing/<src>/<date>/` partition — not re-scan the whole history.

The trap: a bronze-load that re-reads EVERY historical date partition each run.
Cost grows linearly with how long the pipeline has been in production — invisible
on day 1, an SLA breach by month 3. Classic "works on my machine / dies in prod".

Runtime model (seconds, scaled — see Round 1 note): scanning one date partition of
one source ~ 6s. There are N_HISTORY past partitions already in landing.
  BROKEN (PRUNE_TO_CURRENT=False): scan all (N_HISTORY+1) partitions  -> 3 sources x (N+1) x 6s
  FIXED  (PRUNE_TO_CURRENT=True):  scan only today's partition        -> 3 sources x 1     x 6s
"""
from __future__ import annotations

import time

import pendulum
from airflow.decorators import dag, task

START = pendulum.datetime(2026, 6, 1, tz="UTC")

PRUNE_TO_CURRENT = True   # ROUND 2 RESULT: fixed state checked in. See SABOTAGE_LOG.md.
N_HISTORY = 9             # 9 prior daily partitions already landed (10th run today)
SCAN_PER_PARTITION = 6    # seconds to scan one date partition of one source
SOURCES = ("alpha", "beta", "gamma")


@dag(
    dag_id="gym_l5_full_reload_trap",
    schedule=None,
    start_date=START,
    catchup=False,
    tags=["gym", "L5", "sla-gym", "round-2"],
)
def gym_l5_full_reload_trap():
    @task
    def bronze_load(source: str):
        # The bug is the partition selection, not the per-partition cost.
        partitions = 1 if PRUNE_TO_CURRENT else (N_HISTORY + 1)
        time.sleep(partitions * SCAN_PER_PARTITION)

    @task
    def consolidate():
        time.sleep(8)

    loads = [bronze_load.override(task_id=f"bronze_{s}")(s) for s in SOURCES]
    loads >> consolidate()


gym_l5_full_reload_trap()
