# 7AM SLA Analysis — Before / After Log

> The headline portfolio artifact for the SLA Troubleshooting track. For every round: symptom,
> diagnosis (critical path + evidence), the fix, and before/after runtime. Run starts 03:00;
> deadline = **07:00** (240-min budget).
>
> **Rounds 1–3 below: Senior Data Engineer SELF-PLAY** (see `SABOTAGE_LOG.md`). Numbers are
> **by-construction from each gym DAG's deterministic `time.sleep` duration model** (seconds, scaled
> from the real pipeline's minutes) — not a live Gantt capture. The lesson is the **pattern and the
> ratio**, which transfer directly to the minute-scale real DAG; the literal seconds do not. Round 3's
> pool-contention component is reasoned, not measured.

## Method (how to diagnose every time)
1. Airflow **Grid + Gantt** → longest bar / longest chain = **critical path**.
2. Compare task durations → spot the outlier (skew, full-reload, sequential block, sensor lag).
3. Read task **logs** → confirm root cause (don't guess).
4. Apply ONE fix → re-run → measure.
5. Record below.

---

### Round 1 — DAG: `gym_l3_sequential_trap` — Level L3
- **Symptom:** 3 independent bronze loads run serially; DAG wall-time = sum of all loads. Gantt is a staircase.
- **Critical path (broken):** `load_alpha(25) → load_beta(40) → load_gamma(15) → consolidate(10)` = **90s**.
- **Diagnosis:** the loads share no data dependency, but `a >> b >> c` forces a chain. Critical path is `sum(loads)+consolidate` when it should be `max(loads)+consolidate`.
- **Fix applied:** `[load_alpha, load_beta, load_gamma] >> consolidate` (fan-out).
- **Before:** 90s → **After:** 50s (`max(25,40,15)+10`) — **saved 40s / 44%**.
- **SLA met?** ✅ (pattern: serial fan-in scaled to prod minutes is the #1 7AM-breach cause).
- **Concept:** critical path = the *longest dependency chain*; independent work belongs in parallel, not a chain.

### Round 2 — DAG: `gym_l5_full_reload_trap` — Level L5
- **Symptom:** runtime creeps up daily — invisible at launch, breaches by ~month 3. Each load's duration tracks how long the pipeline's been live.
- **Critical path (broken, 9 prior partitions):** each `bronze_<src>` scans all 10 partitions = `10×6=60s`; 3 run parallel = 60s; `+consolidate(8)` = **68s** — and **rising every day**.
- **Diagnosis:** `bronze_load` re-reads every historical `landing/<src>/<date>/` instead of pruning to today's `ds`. Cost is O(history). The smoking gun is duration *growth over calendar time*, not a one-run outlier.
- **Fix applied:** partition-prune to the current `ds` only (`PRUNE_TO_CURRENT`).
- **Before:** 68s (and O(history)) → **After:** 14s (`1×6 + 8`) and **flat regardless of history** — saved 54s / 79% today, unbounded over time.
- **SLA met?** ✅ — and stays met, which the broken version would not as history grows.
- **Concept:** idempotent partition pruning; the dangerous bug is the one that *passes today* and degrades linearly.

### Round 3 — DAG: `gym_l8_sensor_hang_trap` — Level L8 (compounding, two causes)
- **Symptom:** ~a minute of dead idle before any load starts, AND the "parallel" loads don't parallelize under a constrained pool.
- **Critical path (broken):** `wait_for_source_drop(20 + 60/2 = 50s)` → loads → `consolidate(8)` = **~73s modeled** (+ extra serialization in a real pool=2 because the poke sensor holds a slot).
- **Diagnosis — two stacked causes:** **(A)** `mode="poke"` holds a worker slot for the entire wait, starving the pool and re-serializing the fan-out (Round 1's lesson, re-broken indirectly); **(B)** `poke_interval=60s` adds ~30s average dead detection latency after the file actually lands.
- **Fix applied:** `mode="reschedule"` (frees the slot between checks) + `poke_interval=5s` (tighter detection).
- **Before:** ~73s modeled → **After:** ~45s (`22 + 15 + 8`) — saved ~28s from poke-lag alone; **more under a constrained pool** once the slot is freed (reasoned, not measured).
- **SLA met?** ✅ — and the pool is no longer starved, so the upstream fan-out actually fans out.
- **Concept:** sensors aren't free — `poke` holds a worker, `reschedule` doesn't; poke_interval is pure latency; and one bad sensor can silently undo a parallelism win elsewhere.

---

## Results table
| Round | DAG | Root cause | Before | After | Saved | SLA met |
|-------|-----|-----------|--------|-------|-------|---------|
| 1 | `gym_l3_sequential_trap` | serial chain of independent tasks | 90s | 50s | 40s / 44% | ✅ |
| 2 | `gym_l5_full_reload_trap` | full-history reload, no partition prune | 68s (O(history)) | 14s (flat) | 54s / 79% + unbounded | ✅ |
| 3 | `gym_l8_sensor_hang_trap` | poke-sensor slot starvation + coarse poke_interval | ~73s | ~45s | ~28s+ | ✅ |

> Levels demonstrated as self-play worked examples: **L3, L5, L8**. Remaining ladder rungs (L1–L2,
> L4, L6–L7, L9–L10) are left **open for the owner to re-derive with self-review** — the method above is
> the same every time; only the bottleneck shape changes.
