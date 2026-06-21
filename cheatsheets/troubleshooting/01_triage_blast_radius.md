# Phase 01 — Triage & Blast Radius — Incident Cards  [DRILL-READY]

> Checklist step 1 of 8 (see `00_INDEX.md`). First move on any page: scope severity and
> blast radius BEFORE touching code (ADR-006-A1 §5 — observability-first is the mandatory
> first drill step). Scope: `docs/DQD.md` Action-on-Failure tiers, `docs/OPS_RUNBOOK.md`
> Alert SLA table, `scripts/seed_landing_to_s3.py`, the DAG's task-group topology.
> **DRILL-READY (C3, ADR-006-A1) — cleared 2026-06-20.** Exercised against a real `gym-lake`
> MinIO loop: T-TRI-02's silent-stale-fallback was reproduced live (not just cited), and the
> rep surfaced that T-TRI-05's premise needs a correction — see ★ T-TRI-07.
> Owned by @incident-responder · Governed by ADR-006 / ADR-006-A1.

---

### T-TRI-01 — Severity is tiered by MECHANISM, not by which dashboard looks scary  [✅ HARDENED]
- Symptom         : an alert fires; the instinct is to triage by how alarming the symptom looks (e.g. "0 rows" feels scarier than "warn: 3 rows").
- Diagnosis       : classify by the documented Action-on-Failure tier, not gut feel — CRITICAL/HIGH/MEDIUM map to a specific *mechanism*, not a specific *symptom shape*.
- Root cause      : N/A — documents the triage policy.
- Fix / Recovery  : look up which dbt test `severity` (error/warn) or GE expectation actually tripped before deciding response time; don't eyeball it.
- Evidence        : `docs/DQD.md:106-109` (Action on Failure: CRITICAL=block+alert via `severity: error`; HIGH=quarantine-in-place via `dq_flag`/`dq_reason`, no dedicated quarantine table yet; MEDIUM=flag+log via `severity: warn`) + `docs/OPS_RUNBOOK.md:16-26` (Alert SLA: CRITICAL=15min PagerDuty-sim, HIGH=1hr Slack, MEDIUM=business-day email, mapped to specific failure types per row). ✅ HARDENED — this is the code-enforced dbt severity tag, not just prose.
- ⚠️ Junior mistake : pages the on-call at CRITICAL urgency for a `severity: warn` test trip (e.g. the known `stg_beta__ndc.generic_name` warn) because the word "FAIL" appeared in the log, without checking which tier actually fired.
- 🎤 Soundbite      : "I triage by the severity tier the test is tagged with, not by how scary the log text reads — a `severity: warn` and a `severity: error` can print similar-looking lines but carry completely different response clocks."

---

### T-TRI-02 — Stale local-dir fallback can present as "no incident" when ingestion silently re-used yesterday  ★  [✅ HARDENED — reproduced live 2026-06-20]
- Symptom         : a fresh ingestion run for today's `LAND_DATE` is broken (today's local landing dir is missing/empty), but the pipeline reports success with a plausible-looking row count.
- Diagnosis       : check which exact `landing/<source>/<date>/` prefix actually got written to S3 for *today's* `ds` — don't trust "bronze row count looks normal" as proof today's data landed.
- Root cause      : `latest_dir()` falls back to the most recently-dated **local** landing dir if today's doesn't exist, then uploads THAT to S3 under what looks like a normal key — masking a fresh land failure as stale-but-present data.
- Fix / Recovery  : assert the uploaded `date_part` (`src_dir.name`) equals the expected `LAND_DATE` before treating the run as healthy; alert instead of silently falling back.
- Evidence        : `scripts/seed_landing_to_s3.py:44-53` (`latest_dir()`: `if LAND_DATE` and the dir exists, use it; **else** `candidates[-1]` — most recent dir, sorted, no caller-visible signal that this branch fired). Correction to `docs/OPS_RUNBOOK.md:37`, which attributes this exact fallback behavior to `load_bronze.py` — that script (current code) has no such fallback; it reads `LAND_DATE` directly with no directory search (`scripts/load_bronze.py:23,28-29`). The runbook line predates the ADR-005 S3 migration and is stale on this point. Placement: a `date_part == expected_date` assert in `seed_landing_to_s3.py:main()`. Tradeoff: breaks the "always succeeds, never blocks a demo" convenience the fallback currently provides. **Live rep (2026-06-20, gym-lake):** ran `LAND_DATE=2026-06-20 python scripts/seed_landing_to_s3.py` (only a `2026-06-18` local dir exists) — exit code 0, `"uploaded 7 files"`, but every single printed key reads `s3://gym-lake/landing/{alpha,beta,gamma}/2026-06-18/...` — the stale date, silently, with zero indication today's requested partition didn't exist. ✅ HARDENED.
- ⚠️ Junior mistake : closing the ticket because `[bronze] <table>: <n> rows` printed a believable number — the row count being "normal" is exactly what a silent same-data-as-yesterday replay looks like.
- 🎤 Soundbite      : "A plausible row count isn't proof of a fresh load — I check that the partition key uploaded actually matches today's `ds`, because this pipeline's seed step silently falls back to the last dir it finds if today's is missing. I've reproduced this live: ask for a date that doesn't exist locally and it exits 0 holding yesterday's data."

---

### T-TRI-03 — Task-group independence bounds blast radius to one source  [✅ HARDENED]
- Symptom         : one of `alpha`/`beta`/`gamma` fails to land/load.
- Diagnosis       : check whether the OTHER two sources still completed — if so, blast radius is contained to one source, not the whole pipeline.
- Root cause      : N/A — documents the containment guard.
- Fix / Recovery  : confirm via Airflow Grid view which task group(s) actually failed before assuming a full-pipeline incident; this is a single-source rerun, not a from-scratch backfill.
- Evidence        : `airflow/dags/pharma_sttm_pipeline.py:107` (`[alpha(), beta(), gamma()] >> dbt_enrich() ...` — a list, not a chain: the three groups have zero data dependency on each other before the fan-in) + `:52-86` (each group's only internal dependency is its own `land() >> bronze()`). ✅ HARDENED — this is DAG topology, not a hope.
- ⚠️ Junior mistake : treating a single `beta.land` failure as "the whole pipeline is down" and escalating CRITICAL before checking that `alpha`/`gamma` are fine and only one source needs a rerun.
- 🎤 Soundbite      : "The three sources are independent task groups, not a chain — a Beta openFDA outage doesn't touch Alpha or Gamma, so my first triage question is 'which group,' not 'is the pipeline down.'"

---

### T-TRI-04 — Bad data can already be live in `_current` before anyone is paged  ★  [✅ HARDENED]
- Symptom         : a Great Expectations FAIL is reported, but the question that actually matters for blast radius is whether the bad run already reached serving.
- Diagnosis       : check the manual pipeline runner's step ORDER — `publish_gold.py` runs BEFORE `run_ge_validation.py`, not after. A GE FAIL is a detection, not a prevention, on this path.
- Root cause      : GE validates `gold/_current/` as a separate, later step from the pointer-swap that wrote it — there is no built-in "GE passes, then publish" gate on the manual runner.
- Fix / Recovery  : first triage action on any GE FAIL is "what's already in `_current`," not "why did the suite fail" — assume serving may already be stale/wrong and check `gold/_current/` object timestamps before users do.
- Evidence        : `scripts/run_pipeline_aws.sh:34-38` (`[4/5] publish gold/${RUN_ID} -> gold/_current` runs, THEN `[5/5]` GE validation) + `scripts/run_ge_validation.py:35` (`gold/_current/` is the only thing GE reads). Same underlying fact as `V-DQ-04` in `06_data_validation.md` (validation theater), viewed here from the triage angle: scope blast radius BEFORE diagnosing the suite failure. ✅ HARDENED — this is the literal documented script order, not a hypothetical.
- ⚠️ Junior mistake : spending the first 20 minutes reading GE expectation diffs instead of first checking whether the bad run is already being served — the order of operations means it usually already is.
- 🎤 Soundbite      : "On this pipeline, publish happens before validation, not after — so the first thing I check on any GE failure is what's already live in `gold/_current/`, because the suite failing doesn't mean the bad data was stopped."

---

### T-TRI-05 — The orchestrated DAG never touches `gold/_current/` at all  [🟡 APPLICABLE — premise superseded, see ★ T-TRI-07]
- ⚠️ **2026-06-20 update**: written assuming the DAG *reaches* a fully-green state. The live rep proved it doesn't — `dbt_marts()` fails before any Gold model builds at all (★ T-TRI-07 / `02_orchestration_airflow.md` `O-AIR-07`). Keep this card for the day O-AIR-07 is fixed; until then, T-TRI-07 is what actually fires first.
- Symptom         : (becomes live once O-AIR-07 is fixed) a `pharma_sttm_pipeline_v1` DAG run goes fully green, but the question "did this reach the dashboard" is NOT answered by that green state.
- Diagnosis       : check whether `gold/_current/`'s last-modified timestamp changed at all around this DAG run — if not, the run never reached serving, no matter how green the Grid view looks.
- Root cause      : the DAG has no task that calls `scripts/publish_gold.py`; full detail and fix in `02_orchestration_airflow.md` (`O-AIR-01`) — this card is the triage-side framing of the same gap.
- Fix / Recovery  : until `O-AIR-01` is closed, treat "DAG green" and "serving updated" as two SEPARATE facts to verify independently during any blast-radius assessment — never infer the second from the first.
- Evidence        : see `02_orchestration_airflow.md` → `O-AIR-01` for the full file:line chain (`airflow/dags/pharma_sttm_pipeline.py`, `dbt/dbt_project.yml:18`, `dbt/macros/s3_paths.sql:25-26`, `scripts/run_pipeline_aws.sh:34-35`). Placement: a `publish_gold` task at the end of the DAG. Tradeoff: none real — this closes a correctness gap, not a deliberate design choice.
- ⚠️ Junior mistake : closing an incident as "resolved, DAG is green now" without separately confirming Gold was actually published — on THIS pipeline as currently wired, that confirmation step is not optional.
- 🎤 Soundbite      : "Green DAG and updated serving layer are two different claims here — I verify both, because as this DAG is wired today, a successful run doesn't by itself mean Gold got published."

---

### T-TRI-07 — First triage question on this pipeline: did the DAG even survive past `dbt_enrich()`  ★  [✅ HARDENED]
- Symptom         : on-call sees `pharma_sttm_pipeline_v1` red, and the temptation is to jump straight to whichever model name appears in the last error line (e.g. `dim_drug`, `dim_condition`).
- Diagnosis       : before reading any model-level error text, check which TASK failed — if it's `dbt_marts()`, this is (today, as the DAG is wired) the **expected, deterministic** failure point, not a new incident needing root-cause analysis from scratch. Full mechanism: `02_orchestration_airflow.md` `O-AIR-07`.
- Root cause      : the DuckDB dev target is `:memory:` and every `dbt(...)` call is its own `subprocess` (`airflow/dags/pharma_sttm_pipeline.py:28-35`) — Silver (`view`) and the SCD2 snapshot (default DuckDB table) never survive a task boundary, only Gold (`external`) does. This reproduces 100% of the time, live-verified this session on `gym-lake` (see `O-AIR-07` for the exact commands/output).
- Fix / Recovery  : triage time should be near-zero here — confirm the failing task is `dbt_marts()` with a `Catalog Error: ... does not exist` on a `main_enrich.*` or `snapshots.*` relation, log it as the known O-AIR-07 gap (not a new incident), and escalate to "needs the structural fix" rather than spending triage budget hypothesis-testing data issues. Blast radius is total — no Gold model has ever been produced by an orchestrated run.
- Evidence        : same citations as `02_orchestration_airflow.md` `O-AIR-07`, viewed from the triage angle — this card exists so a responder's FIRST move is "which task" not "which model."
- ⚠️ Junior mistake : spending the first 30 minutes of an incident debugging `dim_drug.sql` or the crosswalk logic because that's the model name in the error, when the task that actually failed first was `dbt_marts()`'s `dbt snapshot` sub-step, for a reason that has nothing to do with any model's SQL.
- 🎤 Soundbite      : "My first triage move on this DAG isn't 'which model broke,' it's 'which task' — if it's `dbt_marts()`, I already know this is the known catalog-ephemerality gap, not a new data bug, and I don't burn triage time re-diagnosing something I've already proven is deterministic."

---

### T-TRI-06 — HIGH-severity blast radius is "how many rows have `dq_flag=true`," not "did row count drop"  [✅ HARDENED]
- Symptom         : a HIGH-severity coverage threshold trips (e.g. `condition_sk` FK resolution dips).
- Diagnosis       : query the `dq_flag`/`dq_reason` audit columns for a count and a reason breakdown — the affected rows are still IN the table, nulled in place, not removed.
- Root cause      : N/A — documents the quarantine-in-place policy.
- Fix / Recovery  : scope blast radius as "N rows with a nulled FK, flagged and traceable" rather than assuming a row-count drop; cross-check against `ADR-003`'s null-not-drop policy before assuming data loss.
- Evidence        : `docs/DQD.md:108` (HIGH → "quarantine + continue (no dedicated quarantine *table* exists yet — current practice is null-in-place with `dq_flag`/`dq_reason`")) + `docs/OPS_RUNBOOK.md:74` ("unmatched FKs are nulled, not dropped, per ADR-003"). ✅ HARDENED — current, code-enforced behavior.
- ⚠️ Junior mistake : seeing a coverage-rate drop and assuming rows were silently dropped (the I12 reconciliation-mismatch failure class) when on THIS pipeline's HIGH path the rows are still present — confusing "FK nulled" with "row missing" leads to chasing the wrong reconciliation query.
- 🎤 Soundbite      : "A HIGH-severity coverage dip here means rows got an FK nulled and flagged, not rows disappearing — my blast-radius query counts `dq_flag=true`, not a row-count delta, because that's what this pipeline's quarantine policy actually does."

---

## Phase tally
✅ HARDENED: 6 · 🟡 APPLICABLE: 1 · ⚪ N/A: 0 — **7 cards** (drill-ready, C3, cleared 2026-06-20).
