# DAG Ladder — Curriculum Map (USER builds these)

> Localized for this project from the domain-agnostic gym template (dataset = pharma). The USER
> builds each DAG; @cikgu teaches the concept first (WHY before HOW); @bottleneck-saboteur injects
> a flaw once the DAG works.
>
> Mark a level DONE only after: (a) you built it, (b) you solved its sabotage, (c) you
> logged before/after runtime in `docs/sla/SLA_ANALYSIS.md`.

## Current Position
- **Building level:** L1 (owner starts here — hands on keyboard)
- **Last solved sabotage:** none by owner yet
- **Score (cikgu):** 100/100
- **Worked examples already on disk (answer keys to RE-DERIVE, not skip):** @senior-data-engineer
  self-play solved **L3 / L5 / L8** — see `airflow/dags/gym_l{3,5,8}_*.py` + `docs/sla/SABOTAGE_LOG.md`
  + `docs/sla/SLA_ANALYSIS.md`. @cikgu will make you re-derive these (the rep is the re-derivation,
  not the answer). **Build the ladder from L1 anyway** — don't read the gym_l8 fix before you've earned it.

---

## The Ladder (Beginner → Advanced)

| Lvl | DAG you build | New concept | Sabotage you'll face | Skill sharpened |
|-----|---------------|-------------|----------------------|-----------------|
| **L1** | `hello_pharma` — 1 task, print row count of raw file | DAG = graph; task; schedule; `start_date`; `catchup` | — (free; learn basics) | Python, Airflow |
| **L2** | `ingest_raw` — raw file → Bronze (1 task) | Operators; idempotent load | S6 schedule mismatch | Python, idempotency |
| **L3** | `ingest_then_count` — 2 tasks, `a >> b` | Task dependency; upstream/downstream | S1 sequential trap | Airflow, critical path |
| **L4** | `enrich` — Bronze → Silver (clean+conform) | Layer boundary; branching; XCom | S2 full-refresh vs incremental | SQL/Python, layering |
| **L5** | `build_mart` — Silver → star schema (fact+dims) | Fan-out (parallel dims); **grain** | S1 + parallelism missed | Kimball modeling |
| **L6** | `mart_with_tests` — add dbt/GE quality gate | Fail-fast gating; trust boundary | S4 retry storm in tail | dbt tests, DQ |
| **L7** | `serving_layer` — Mart → reporting views | Serving layer; aggregation | S8 small-file explosion | SQL, warehouse |
| **L8** | `daily_master` — orchestrate L2–L7 end-to-end | Critical path; SLA target; `sla=` | S3 no-pool contention | Airflow at scale |
| **L9** | `daily_master_v2` — sensors + pools + priority | Sensors; pools; `priority_weight` | S9 unbounded sensor hang | Orchestration depth |
| **L10**| `daily_master_hardened` — full SLA-safe DAG | Skew; broadcast; partition tuning | S10 compound (isolate causes) | PySpark perf, capstone |

---

## Rules of the Gym
1. **You type the code.** Cabinet specs + cikgu hints, but your hands on keyboard.
2. **One sabotage per level** (until L8+ compound). Diagnose ONE root cause at a time.
3. **Measure everything.** Every level ends with a runtime number. No "feels faster."
4. **Critical path is king.** For every DAG, be able to draw its critical path.
5. **The deadline is real.** Pretend the run starts 03:00; the DAG must finish < 07:00.

## How a round runs
```
@cikgu     → teaches concept for level N (Socratic, minimal hints, DIY Build Mode)
YOU        → build airflow/dags/<dag_for_level_N>.py
@senior-de → reviews your DAG (risk + perf)
@saboteur  → injects flaw, logs SYMPTOM only in docs/sla/SABOTAGE_LOG.md
YOU + cikgu→ diagnose (Gantt, logs, critical path) → you fix
@saboteur  → verifies, reveals root cause, marks SOLVED
YOU        → record before/after in docs/sla/SLA_ANALYSIS.md
```
