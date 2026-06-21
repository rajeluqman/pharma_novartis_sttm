# INCIDENT 2026-06-19 — drug coverage KPI dropped ~12%

> 8-step diagnostic walkthrough (ADR-006 + ADR-006-A1). Owned by @incident-responder.
> **WORKED EXAMPLE** (filled, to show the format). In a REAL drill the symptom below is all you
> get — the root cause + rubric stay sealed in `docs/incidents/.solutions/` until you solve it.
> Pairs with card [I-ING-01](../../cheatsheets/troubleshooting/03_ingestion_s3.md).

| Field | Value |
|-------|-------|
| Incident id | INC-2026-06-19-01 |
| Track / Source | I (failure) — Sabotage Log round, see `docs/sla/SABOTAGE_LOG.md` |
| Difficulty | **L5** (symptom presented FAR from root — a business KPI, not a row count) |
| Severity | SEV2 (KPI wrong, no data lost downstream yet) — *theatre shown for L7+ only* |
| **Symptom (all you're given)** | **"Drug coverage KPI (dim_drug match-rate) dropped ~12% overnight. Dashboard looks wrong."** |
| MTTR | (captured + displayed for the post-mortem story — **NOT graded**, ADR-006-A1 §3) |
| Root cause | 🔒 `[SEALED → docs/incidents/.solutions/]` until solved |
| Status | RESOLVED |

## Hypothesis-trail (USER-written; evidence-gated — no claim without command+output)
| # | Hypothesis | Test (command/query) | Predicted | Actual | Verdict |
|---|-----------|----------------------|-----------|--------|---------|
| H1 | KPI is crosswalk-derived; a source feeding dim_drug shrank | reconcile gold→silver→bronze counts (`load_bronze.py:80-83`) | one source count dropped | bronze `ndc_directory` = 0, others normal | ✅ localized to Beta |
| H2 | Beta bronze=0 because transform broke | rerun bronze on a known-good sample | sample → ~136k rows | sample fine → not the code | ❌ ruled out (it's the input) |
| H3 | Beta landing file is bad | check landing object size (`seed_landing_to_s3.py:67-68` print) | non-zero ~MBs | **0 bytes** | ✅ root found |

> Observability-first: H1 starts from the *signal* (reconcile counts), not from reading code.

## 1. Triage & blast radius
Validate KPI drop is real (not a dashboard cache). **Pause downstream** (crosswalk → Gold) so a
corrupt Beta can't poison the veneer. Do NOT let the run pointer-swap `gold/<run_id>/` on bad Beta.

## 2. Run logs / stack trace
CloudWatch task log + DuckDB Python traceback (NO Spark UI). Beta bronze read
`scripts/load_bronze.py:55-59` → 0 rows / empty read. Points upstream of the transform.

## 3. Ingestion (S3)  ← root cause
Landing object size at `landing/beta/<date>/ndc_directory.json` → **0 bytes** (seed prints size,
`scripts/seed_landing_to_s3.py:67-68`). Expected ~136k products (`ingest_beta_ndc.py:39`).

## 4. Transformation (DuckDB/dbt)
Ruled out via clean-sample rerun (H2) — code path healthy, the input is the fault.

## 5. Load (Snowflake external table)
Not reached. Confirm veneer still points at the previous good `gold/<run_id>/`, not swapped onto
corrupt Beta. (No COPY history — external tables over Gold parquet.)

## 6. Data validation (Great Expectations)
Should have caught this at the gate: a landing/bronze `row_count > 0` (≈136k) expectation on
`ndc_directory` fails fast. Action → add to `scripts/run_ge_validation.py`.

## 7. CI/CD audit
No recent merge to ingestion scripts; DAG parse gate clean → operational/data incident, not a deploy.

## 8. Post-mortem & recovery (recovery is GRADED)
- **Impact:** Beta bronze empty → crosswalk match-rate craters → KPI -12%. No bad data reached
  the veneer (caught at step-1 blast-radius pause).
- **Recovery (idempotent, reconcile, verify-before-re-enable):**
  1. Re-land Beta (`ingest_beta_ndc.py`, verify ~136k) → re-seed (idempotent, card I-ING-06) → rerun bronze.
  2. **Reconcile**: `load_bronze.py:80-83` shows ~136k for `ndc_directory`.
  3. Re-enable downstream (crosswalk → Gold); catchup rerun.
  - ❌ must-not-do: re-seed with timestamped filename (breaks idempotency); re-enable before reconciling.
- **Prevention:** size assert `>0` at `seed_landing_to_s3.py:64` + GE `row_count>0` gate.

---

## @cikgu handoff
Teach from the **symptom only** (KPI -12%). Make the user re-derive the backward trace
(KPI → reconcile counts → bronze=0 → landing size). After 2 failed hypotheses, hint the
*method* ("what feeds that KPI? where would you measure it?"), never the cause. Grade the method
+ recovery (not MTTR). Then log `LEARNING_LOG.md`.
