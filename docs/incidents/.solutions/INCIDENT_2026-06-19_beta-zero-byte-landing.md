# SEALED RUBRIC — INC-2026-06-19-01 (Beta NDC zero-byte landing)

> 🔒 GITIGNORED. Do NOT read this before you have solved the drill — it defeats the gym.
> This is a RUBRIC (ADR-006-A1 §4): acceptable diagnosis paths + must-not-do list, NOT a single
> canonical answer. @incident-responder grades the user's path against this; @cikgu never reads it aloud.

## Sealed root cause
A **0-byte / truncated `ndc_directory.json`** landed at `landing/beta/<date>/` (partial/hung
upload). Bronze `read_json_auto` then produces 0 rows for Beta → the conformed `dim_drug`
crosswalk (ADR-003) loses its product master → the **drug match-rate KPI craters** (the symptom
the user is shown). Code anchor of the gap: `scripts/seed_landing_to_s3.py:62-69` accepts any
file, prints size but never asserts `> 0`.

## Acceptable diagnosis paths (any ONE reaching the cause cleanly = pass)
- **Path A (counts-backward):** KPI drop → reconcile gold→silver→bronze counts
  (`scripts/load_bronze.py:80-83`) → spot bronze `ndc_directory`=0 → check landing object size
  (`seed_landing_to_s3.py:67-68` print) → 0 bytes. ← the cleanest path.
- **Path B (lineage-first):** KPI is crosswalk-derived → which source feeds dim_drug? Beta →
  inspect Beta landing object → 0 bytes.
- **Path C (logs-first):** CloudWatch/DuckDB traceback on the Beta bronze step → `read_json_auto`
  empty/parse → trace to landing size.

## Must-NOT-do (any of these caps the score, even if cause is found)
- ❌ Re-run / backfill **before** reducing blast radius (pausing crosswalk→Gold) — risks
  publishing a corrupt Gold to the veneer.
- ❌ "Re-seed with a timestamped filename to be safe" — breaks idempotency (card I-ING-06),
  spawns duplicate landing objects the bronze glob double-counts.
- ❌ Declare it fixed on "the job didn't error" — must **reconcile counts** post-recovery
  (expect ~136k NDC rows) before re-enabling downstream.
- ❌ Touch the live lake/veneer — drills are incubator-only (`gym.env` + `gym_guard.py`).

## Correct recovery (graded)
1. Pause downstream (crosswalk → Gold).
2. Re-land Beta (`ingest_beta_ndc.py`, verify ~136k printed) → re-seed (idempotent) → rerun bronze.
3. **Reconcile**: `load_bronze.py:80-83` shows ~136k for `ndc_directory`.
4. Re-enable downstream; catchup rerun.

## Prevention the user should propose
- Size assert `> 0` at `seed_landing_to_s3.py:64`.
- GE `row_count > 0` (≈136k) landing/bronze gate in `scripts/run_ge_validation.py`.

## Difficulty
Far-from-root symptom (business KPI) = **L5**. Same failure shown as "bronze=0 rows" would be L1.
