# ADR-006 — Incident-Response Practice Library + Track I Fault-Injection

- **Status:** Accepted
- **Date:** 2026-06-19
- **Decider:** Data Architect (veto — APPROVED w/ conditions), co-reviewed by Senior Data Engineer
  (conditions on the Spark→DuckDB translation, §6 below)
- **Supersedes / extends:** ADR-005 (stack lock — confirms ZERO new tooling); precedent =
  `cheatsheets/optimization/`

## Context

The optimization library (`cheatsheets/optimization/`) turns the repo's *already-optimized*
code into interview ammunition: one pattern card per technique, each proven at a `file:line`,
each paired with the junior mistake it avoids.

This adds the **failure-path counterpart**: a governed catalog of how to *diagnose and recover*
this pipeline when it breaks, fed by a closed practice loop so real on-call troubleshooting
muscle gets built deliberately, not accidentally. Source material was a Spark-stack incident
checklist (S3→Spark→Snowflake on Airflow); this project has **no Spark** (DuckDB single-process
+ dbt-duckdb external + Snowflake external-table veneer + MWAA), so the taxonomy must be
translated, not copied.

## Decision

1. **New library** `cheatsheets/troubleshooting/` — a governed mirror of the optimization
   library. One file per incident-response phase (an 8-step checklist), plus `00_INDEX.md`
   (entry point) and a roll-up file. Bucket classification **✅ HARDENED / 🟡 APPLICABLE / ⚪
   N/A**, same "no card without `file:line` proof or placement" rule as the optimization
   library.

2. **New per-incident walkthrough tree** `docs/incidents/INCIDENT_<id>.md` — the live 8-step
   diagnostic runbook for one occurrence (triage+blast-radius → run logs → ingestion →
   transformation → load → validation → CI/CD → post-mortem+recovery).

3. **Curation follows the same non-authoritative-source rule as the optimization library**:
   may **read** AH/STTM/ERD/DATA_MODEL/ADR as evidence but **never writes** them; writes only to
   `cheatsheets/troubleshooting/` and `docs/incidents/`.

4. **Track I fault-injection (I1–I10)** — extends the existing fault-injection tooling's mandate
   from *slowness* (S-track, SLA practice) to *failure* incidents (0-byte/truncated file, schema
   drift, type/contract mismatch, silent data drop, bad join, CI/CD merge break). Symptom-only,
   root cause sealed, always recoverable.

5. **The loop:** a failure is injected (Track I) → the diagnosis is logged as an 8-step drill in
   `docs/incidents/` and distilled into a `cheatsheets/troubleshooting/` card → the symptom +
   card are studied retrospectively, without ever reading the sealed root cause first.

6. **Spark→DuckDB translation is binding**: NO "broadcast join" card, NO "shuffle tuning" card.
   Reframe skew→aggregation/cardinality blowup, shuffle→spill-to-`temp_directory`,
   partition-pruning→date-prefix scoping. Promote **OOM (DuckDB + MWAA worker)** and **silent
   data drops** to top-priority cards. Snowflake step is rewritten for external tables (no COPY
   history / no COPY INTO); logs step uses CloudWatch + DuckDB Python traceback (no Spark UI).
   The full table lives in `cheatsheets/troubleshooting/00_INDEX.md`.

## Binding conditions

- **Pilot gate:** build the Ingestion (S3) loop end-to-end FIRST; sign-off before the other 7
  phases are scaffolded. No mass folder creation up front.
- **Log of record:** symptom registry stays `docs/sla/SABOTAGE_LOG.md` (single registry, S- and
  I-tracks); detailed walkthroughs live in `docs/incidents/`.
- **Destructive-injection guardrail:** Track I failure modes injected ONLY against gym copies
  (`airflow/dags/broken/`), env-toggles, or synthetic fixtures — NEVER against real
  landing/bronze/silver/gold S3 objects or the live Snowflake veneer; always revertible
  (git/`.bak`).
- **English-only** library content; the hint-don't-tell, Socratic practice format is preserved.

## Consequences

- (+) Failure-path coverage + on-call muscle, symmetric with the optimization library.
- (+) Cards are stack-honest (DuckDB/MWAA/external-table), not imported Spark fiction.
- (−) New tooling surface to maintain (fault-injection script, incident-response docs).
- (−) The fault-injection tool now has a destructive mode → guardrails above are load-bearing.
