# Sabotage Log — SLA Gym (Track B)

> PUBLIC record. Normally the fault-injection drill logs the SYMPTOM only and the root cause stays
> `[SEALED]` until the learner solves it. **These rounds were run as Senior Data Engineer SELF-PLAY
> (create + solve in one pass)** — a worked-example answer key. Root causes are revealed here on
> purpose; self-review will still make the owner *re-derive* them (the answer key existing doesn't defeat
> the gym — re-derivation is the rep). Each gym DAG carries both the broken and fixed state behind a
> single switch so the before/after is auditable from one source file.
>
> **Number honesty:** gym tasks are deterministic `time.sleep` stand-ins (seconds, scaled down from
> the real pipeline's minutes). Before/after below are **by-construction from the duration model**,
> not a live Airflow Gantt capture. Round 3's worker-pool-contention portion is *reasoned*, not
> measured (would need a real pool + scheduler to observe). All three DAGs parse clean on the local
> Airflow (`DagBag`, zero import errors).

| Round | DAG | Level | Symptom (visible) | Status | Root cause (revealed) |
|-------|-----|-------|-------------------|--------|------------------------|
| 1 | `gym_l3_sequential_trap` | L3 | 3 independent source loads run one-after-another; Gantt is a staircase, not a fan; wall-time = sum of every load | SOLVED | `a >> b >> c >> consolidate` serializes tasks that have **zero data dependency**. Critical path = `sum(loads)` instead of `max(loads)`. |
| 2 | `gym_l5_full_reload_trap` | L5 | Runtime creeps up a little **every day** — fine at launch, breaches the budget by ~month 3; each load's duration tracks calendar age | SOLVED | `bronze_load` re-scans **all** historical `landing/<src>/<date>/` partitions every run instead of pruning to today's `ds`. Cost = O(history), not O(1). |
| 3 | `gym_l8_sensor_hang_trap` | L8 (compounding) | Pipeline idles ~a minute before any load starts, AND the parallel loads don't actually parallelize under load — two smells at once | SOLVED | **A:** sensor `mode="poke"` holds a worker slot for the whole wait → starves the pool → re-serializes the fan-out (Round 1's lesson, re-broken indirectly). **B:** `poke_interval=60s` adds ~30s avg dead detection latency. |

## Status legend
- `OPEN` — sabotage active, diagnosing.
- `SOLVED` — fixed; root cause revealed above.

## Fix switches (one source file per round, both states auditable)
- Round 1: `USE_PARALLEL` (`gym_l3_sequential_trap.py`) — `False`=broken serial, `True`=fixed fan-out.
- Round 2: `PRUNE_TO_CURRENT` (`gym_l5_full_reload_trap.py`) — `False`=full reload, `True`=partition prune.
- Round 3: `FIXED` (`gym_l8_sensor_hang_trap.py`) — flips `mode` poke→reschedule and `poke_interval` 60s→5s.
