"""SLA Gym — Round 3 (Ladder L8, Sabotage S3: compounding — sensor mode + coarse poke).

SELF-PLAY: broken-and-fixed in one file via the FIXED switch. L8+ allows a
COMPOUNDING round (two causes), per SLA_GYM_PROMPT rules. Two real faults stack:

  Cause A — `mode="poke"` sensor holds a worker slot for the ENTIRE wait. With a
            small pool, the held slot starves the 3 parallel bronze loads, quietly
            re-serializing what should fan out (compounds with Round 1's lesson).
  Cause B — `poke_interval` far too coarse (60s): even once the file lands, the
            sensor sleeps up to a full interval before noticing -> avg ~30s of
            pure dead latency added to the critical path.

  FIX     — `mode="reschedule"` frees the worker slot between checks (kills the
            contention), and a tight `poke_interval` (5s) cuts the detection lag.

Runtime model (seconds, scaled): upstream file lands ~20s after start. 3 bronze
loads ~15s each, pool=2 worker slots.
  BROKEN: poke holds 1 slot for the ~20s wait -> only 1 slot left for 3 loads
          (serialize: ~3x15=45s) + ~30s avg poke lag  => critical path ~ 20 + 45 + 30
  FIXED : reschedule frees the slot during the wait -> 2 slots for 3 loads
          (~2 waves: ~30s) + ~5s poke lag             => critical path ~ 20 + 30 + 5
"""
from __future__ import annotations

import time

import pendulum
from airflow.decorators import dag, task

START = pendulum.datetime(2026, 6, 1, tz="UTC")

FIXED = True              # ROUND 3 RESULT: fixed state checked in. See SABOTAGE_LOG.md.
UPSTREAM_LANDS_AFTER = 20
POKE_INTERVAL = 5 if FIXED else 60   # detection lag ~ avg poke_interval/2
SENSOR_MODE = "reschedule" if FIXED else "poke"
LOAD_SECS = 15
SOURCES = ("alpha", "beta", "gamma")


@dag(
    dag_id="gym_l8_sensor_hang_trap",
    schedule=None,
    start_date=START,
    catchup=False,
    tags=["gym", "L8", "sla-gym", "round-3", "compounding"],
)
def gym_l8_sensor_hang_trap():
    @task
    def wait_for_source_drop():
        # Stand-in for a FileSensor on the source landing key. The DETECTION LAG
        # (poke_interval) is the modelled cost; mode is documented for the lesson.
        time.sleep(UPSTREAM_LANDS_AFTER + POKE_INTERVAL // 2)

    @task
    def bronze_load(source: str):
        time.sleep(LOAD_SECS)

    @task
    def consolidate():
        time.sleep(8)

    gate = wait_for_source_drop()
    loads = [bronze_load.override(task_id=f"bronze_{s}")(s) for s in SOURCES]
    gate >> loads >> consolidate()


gym_l8_sensor_hang_trap()
