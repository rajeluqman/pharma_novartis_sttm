# Phase 05 — Load (Snowflake external table) — Incident Cards  [DRILL-READY — WITH CAVEAT]

> Checklist step 5 of 8 (see `00_INDEX.md`). Stack-honest: serving = Snowflake EXTERNAL TABLES
> over Gold parquet — **no `COPY INTO`, no copy history** (see translation table in `00_INDEX.md`).
> Scope: `scripts/publish_gold.py` (verify→copy pointer-swap + rollback), `scripts/provision_snowflake_veneer.py/.sql`.
> **C3 partially cleared 2026-06-19** — `publish_gold.py` ran for real against local MinIO `gym-lake`
> (verify all 7 objects → pointer-swap to `gold/_current/`), confirmed by @senior-data-engineer.
> **L-SNO-01/02/04/05 are drill-ready up to L10.** **L-SNO-03 stays 🟡 APPLICABLE permanently** —
> `ALTER EXTERNAL TABLE ... REFRESH` stale-metadata caching is real Snowflake server-side behavior;
> MinIO/DuckDB has no external-table metadata cache to reproduce it against. Per senior-DE verdict:
> "not a gym gap, it's a physics-of-MinIO gap" — don't grade L-SNO-03 at L5+ without a real Snowflake
> session in the loop, which the incubator (ADR-006-A1) deliberately never touches.
> Owned by @incident-responder · Governed by ADR-006 / ADR-006-A1.

---

### L-SNO-01 — Half-published Gold (`_current` partially overwritten)  ★  [✅ HARDENED]
- Symptom         : (prevented) — the veneer would read a run where some models are new and some old.
- Diagnosis       : confirm publish verifies ALL objects before touching `_current`; a failed publish must leave `_current` at the last-good state.
- Root cause      : N/A — documents the verify-then-copy guard.
- Fix / Recovery  : keep the order: `verify_run()` (every object exists + non-empty) THEN copy to `_current`; abort on any miss.
- Evidence        : `scripts/publish_gold.py:81-85` (verify before copy), `:60-63` (copy-not-rename; untouched models keep last-good `_current`), `:93-97` (RuntimeError → exit 1, no partial publish). ✅ HARDENED.
- ⚠️ Junior mistake : copy `gold/<run_id>/` → `gold/_current/` without verifying all objects first — one missing model and the veneer serves a half-written run.
- 🎤 Soundbite      : "I verify every Gold object exists and is non-empty before the pointer swap — S3 has no atomic rename, so without verify-first the serving layer can read a half-published run."

---

### L-SNO-02 — Stale / missing `gold/_current/` pointer (veneer returns nothing)  ★  [🟡 APPLICABLE]
- Symptom         : Snowflake external-table query returns 0 rows / file-not-found; dashboards empty.
- Diagnosis       : list `s3://<bucket>/gold/_current/`; check the last successful publish run_id. (No copy history to consult — external tables.)
- Root cause      : publish never ran, or a teardown removed the `_current` objects the external table points at.
- Fix / Recovery  : re-publish the last good run — `python scripts/publish_gold.py --run-id <last-good>` (re-copies that run into `_current/`).
- Evidence        : `scripts/publish_gold.py:75` (`--run-id` selects which run to publish) + external table reads ONLY `gold/_current/` (`scripts/provision_snowflake_veneer.sql`). Placement: a monitor on `_current/` object presence. Tradeoff: cheap liveness check.
- ⚠️ Junior mistake : re-pointing the external table straight at `gold/<run_id>/` to "fix it fast" — breaks the `_current` contract the whole serving design depends on.
- 🎤 Soundbite      : "Recovery here is a data op, not DDL — I re-run publish with the last-good run_id to repopulate `_current`, never re-point the external table at a raw run dir."

---

### L-SNO-03 — Stale external-table metadata (REFRESH not run after publish)  [🟡 APPLICABLE]
- Symptom         : after a SUCCESSFUL Gold publish, the veneer still serves OLD/partial data — the query "succeeds" but the numbers are stale.
- Diagnosis       : did `ALTER EXTERNAL TABLE ... REFRESH` run after the pointer swap? External tables cache file metadata; a freshly-published `gold/_current/` isn't visible until a REFRESH.
- Root cause      : publish refreshed `gold/_current/` but the external-table METADATA wasn't refreshed → it serves the previous snapshot.
- Fix / Recovery  : run the documented REFRESH after each publish, or automate it as a DAG task right after `publish_gold.py`.
- Evidence        : `scripts/provision_snowflake_veneer.sql:80-82` (`ALTER EXTERNAL TABLE obt_*_ext REFRESH` documented as the post-publish step) + `:61-66` (`INFER_SCHEMA` — columns auto-inferred, so the failure is stale METADATA, not a hand-typed schema mismatch). Placement: wire REFRESH into the DAG after publish. Tradeoff: one more task; removes a silent-stale class.
- ⚠️ Junior mistake : assuming "new parquet published = veneer updated" — an external table serves cached metadata until REFRESH, so you ship stale numbers that look perfectly valid.
- 🎤 Soundbite      : "Publishing new Gold parquet doesn't refresh an external table by itself — without the post-publish `REFRESH` the veneer serves a stale snapshot, so I automate it right after the pointer swap."

---

### L-SNO-04 — Rollback by run-id (the recovery pattern)  [✅ HARDENED]
- Symptom         : (recovery) — a bad run reached `_current`; need to revert without warehouse DDL.
- Diagnosis       : identify the last-good run_id from retained `gold/<run_id>/` lineage.
- Root cause      : N/A — documents the rollback mechanism.
- Fix / Recovery  : `python scripts/publish_gold.py --run-id <older-good>` — re-copies that prior run back into `_current/`. Pure data op, no DDL, no Snowflake privilege.
- Evidence        : `scripts/publish_gold.py:75` + `:88` (per-run lineage retained, not deleted → rollback target exists). ✅ HARDENED.
- ⚠️ Junior mistake : reaching for Snowflake DDL / `CREATE OR REPLACE` to "roll back" — unnecessary; the rollback is an S3 copy of a retained prior run.
- 🎤 Soundbite      : "Because every run is retained at `gold/<run_id>/`, rollback is just re-publishing an older run_id — no DDL, no privileges, a one-command data operation."

---

### L-SNO-05 — Per-run dir accumulation (small-file / scan-cost creep)  [🟡 APPLICABLE]
- Symptom         : over time, S3 list/scan latency + cost on the gold prefix creeps up.
- Diagnosis       : count `gold/<run_id>/` dirs retained; each is kept for lineage and never pruned.
- Root cause      : lineage retention with no lifecycle = unbounded accumulation of run dirs (the project's small-file analog — see translation table).
- Fix / Recovery  : an S3 lifecycle rule to expire old `gold/<run_id>/` after N days (keep `_current/` + a window for rollback).
- Evidence        : `scripts/publish_gold.py:88` (lineage retained, not deleted). Placement: bucket lifecycle policy. Tradeoff: shorter rollback window vs lower storage/scan cost.
- ⚠️ Junior mistake : never pruning run dirs — "storage is cheap" until the list/scan over thousands of run prefixes is the slow part.
- 🎤 Soundbite      : "Lineage retention is great until it's unbounded — I lifecycle old run dirs so rollback stays possible without the gold prefix becoming a small-file scan tax."

---

## Phase tally
✅ HARDENED: 2 · 🟡 APPLICABLE: 3 · ⚪ N/A: 0 — **5 cards** (drill-ready w/ one caveat, C3 cleared).
4 of 5 cards (L-SNO-01/02/04/05) drill-ready to L10; L-SNO-03 capped — see banner above.
