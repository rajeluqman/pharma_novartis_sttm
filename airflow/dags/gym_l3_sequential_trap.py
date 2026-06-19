"""SLA Gym — Round 1 (Ladder L3, Sabotage S1: sequential-when-parallelizable).

SELF-PLAY: built broken-by-design, then fixed in the same file (see
`USE_PARALLEL` switch below) so the before/after is reproducible from one
source file. Mirrors the real pipeline's source fan-out (alpha/beta/gamma)
at L3 scale: 3 independent bronze loads + 1 downstream consolidation.

Topology mirrors `pharma_sttm_pipeline.py`'s bronze stage (3 sources) but at
toy scale: each "load" task just sleeps to stand in for an I/O-bound land+
bronze step. Independent sources have ZERO data dependency on each other —
textbook fan-out candidate.

BROKEN (USE_PARALLEL=False): a >> b >> c >> consolidate
  Critical path = a + b + c + consolidate = sum of every task.
FIXED   (USE_PARALLEL=True):  [a, b, c] >> consolidate
  Critical path = max(a, b, c) + consolidate.

Runtime model per task (stand-in for real land+bronze IO wait, not CPU work):
  load_alpha ~ 25s, load_beta ~ 40s, load_gamma ~ 15s, consolidate ~ 10s.
These are SECONDS (not the real pipeline's minutes) — gym DAGs run small on
purpose so self-play rounds finish without burning the 240-min SLA for real;
the SLA comparison in docs/sla/SLA_ANALYSIS.md scales the ratio, not the
literal seconds, against the 240-min contract.
"""
from __future__ import annotations

import time

import pendulum
from airflow.decorators import dag, task

START = pendulum.datetime(2026, 6, 1, tz="UTC")

# Self-play switch: flip to True for the "fixed" run. Both states live in one
# file so the round is auditable end-to-end (no hidden diff between bug and fix).
USE_PARALLEL = True  # ROUND 1 RESULT: fixed state checked in. See SABOTAGE_LOG.md.

# Stand-in I/O wait per source — proportionally matches the real DAG's
# alpha/beta/gamma split (beta = openFDA API call = slowest, gamma = local
# file = fastest), scaled to seconds for a fast gym loop.
DURATIONS = {"alpha": 25, "beta": 40, "gamma": 15, "consolidate": 10}


@dag(
    dag_id="gym_l3_sequential_trap",
    schedule=None,  # gym DAG: triggered manually for self-play, not on a clock
    start_date=START,
    catchup=False,
    tags=["gym", "L3", "sla-gym", "round-1"],
)
def gym_l3_sequential_trap():
    @task
    def load_alpha():
        time.sleep(DURATIONS["alpha"])

    @task
    def load_beta():
        time.sleep(DURATIONS["beta"])

    @task
    def load_gamma():
        time.sleep(DURATIONS["gamma"])

    @task
    def consolidate():
        time.sleep(DURATIONS["consolidate"])

    a, b, c = load_alpha(), load_beta(), load_gamma()

    if USE_PARALLEL:
        [a, b, c] >> consolidate()
    else:
        a >> b >> c >> consolidate()


gym_l3_sequential_trap()
