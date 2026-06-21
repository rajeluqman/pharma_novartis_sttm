# JOURNEY_LOG.md
Chronological record of problems + solutions. Source for INTERVIEW_GUIDE.md.

FORMAT:
[ID] [DATE · PHASE]
PROBLEM   : what went wrong / unexpected discovery
SYMPTOM   : exact observation
ROOT CAUSE: underlying reason
SOLUTION  : exactly what was done
FIX IN    : file/line ref
OUTCOME   : result

---

## Phase 1 — Discovery

[001] [YYYY-MM-DD · Phase 1]
PROBLEM   : <title>
SYMPTOM   : <observation>
ROOT CAUSE: <reason>
SOLUTION  : <fix>
FIX IN    : <file>
OUTCOME   : <result>

---

## Phase 2 — Exploration

<entries go here>

---

## Phase 3 — Design

<entries>

---

## Phase 4 — Build

[002] [2026-06-18 · Phase 4]
PROBLEM   : Snowflake `prod` target credentials looked complete in `.env` but `dbt debug --target prod` failed.
SYMPTOM   : `Role 'NOVARTIS_STTM_ROLE' specified in the connect string does not exist or not authorized.`
ROOT CAUSE: `.env` had been populated with intended object names during Phase 3, but the actual Snowflake
            role/warehouse/database were never created in the trial account — only default
            `ACCOUNTADMIN`/`SYSADMIN`/`PUBLIC` roles and `COMPUTE_WH` existed.
SOLUTION  : Wrote and ran `scripts/setup_snowflake.sql` (with user approval) to create the role, an XSMALL
            warehouse with 60s auto-suspend, and the database.
FIX IN    : scripts/setup_snowflake.sql
OUTCOME   : `dbt debug --target prod` passed. Later flagged by @scope-guardian in the Phase 4 retroactive
            cabinet review as a reactive scope decision that should have been logged at the time — see
            DECISION_LOG.md and [003].

[003] [2026-06-18 · Phase 4]
PROBLEM   : The first version of `setup_snowflake.sql` granted `GRANT ALL ON DATABASE`/`SCHEMA
            PUBLIC`/`FUTURE SCHEMAS`/`FUTURE TABLES` to the dbt role.
SYMPTOM   : Caught not by a test, but by @data-architect during the Phase 4 retroactive cabinet review
            (DEBATE_LOG_phase_4.md) — `ALL` was never actually needed; nothing failed at the time.
ROOT CAUSE: Cabinet/governance review was skipped before the script was run (the original process gap this
            whole retroactive session exists to fix) — an RBAC over-grant shipped because no one with
            least-privilege authority looked at it before it touched the live account.
SOLUTION  : Replaced with `USAGE` + `CREATE SCHEMA` at the database level (the role owns whatever schemas it
            creates, so no `FUTURE` grants are needed); wrote ADR-004 to record the model; re-ran the
            corrected grants live (REVOKE then GRANT) and re-verified `dbt debug --target prod` still passes.
FIX IN    : scripts/setup_snowflake.sql, docs/ADR/ADR-004-snowflake-rbac.md
OUTCOME   : Same dbt functionality, materially smaller blast radius. Veto resolved.

[004] [2026-06-18 · Phase 4]
PROBLEM   : Editing a dbt model file did not change query results on the next run of a *different* model
            that referenced it.
SYMPTOM   : Edited `stg_beta__ndc.sql` to flatten `pharm_class` from an array to a string, then immediately
            ran `dim_drug` — got `Binder Error: No function matches lower(VARCHAR[])`, as if the edit hadn't
            happened. Recurred a second time with `stg_gamma__reviews.sql` after adding `review_id`.
ROOT CAUSE: DuckDB views are materialized with whatever SQL was live at `CREATE VIEW` time; editing the
            `.sql` file only changes the file on disk, not the view already created in the warehouse — that
            requires an explicit `dbt run` on the changed model before anything downstream sees the new
            definition.
SOLUTION  : Always `dbt run -s staging` (or the specific changed model) immediately after any staging-layer
            edit, before running anything downstream that references it.
FIX IN    : (workflow, not a code fix)
OUTCOME   : No further stale-view errors once the rerun-staging-first habit was applied consistently.

[005] [2026-06-18 · Phase 4]
PROBLEM   : `dim_drug` build failed with a UNION type-mismatch (`pharm_class` VARCHAR vs VARCHAR[]) even
            after [004]'s fix was applied to `stg_beta__ndc.sql`.
SYMPTOM   : `Conversion Error: Type VARCHAR ... can't be cast to the destination type VARCHAR[] when casting
            from source column pharm_class`.
ROOT CAUSE: `dbt snapshot` bakes the target table's column types in at first creation. The snapshot had
            already been built once against the OLD (array-typed) `stg_beta__ndc` definition before the
            staging fix landed, so its `pharm_class` column was permanently VARCHAR[] regardless of what the
            now-corrected staging view produced.
SOLUTION  : Dropped the stale `snapshots.snap_beta_ndc` table directly in DuckDB, then re-ran `dbt snapshot`
            so it was rebuilt fresh against the corrected staging schema.
FIX IN    : dbt/snapshots/snap_beta_ndc.sql (no code change — operational fix)
OUTCOME   : Snapshot and `dim_drug` built clean. Generalizes [004]'s lesson: snapshots need a full
            drop-and-rebuild, not just a rerun, when an upstream column *type* changes during active
            development (acceptable for a dev snapshot with no real history yet; would need an actual
            migration plan if this happened against a snapshot already carrying production SCD2 history).

[006] [2026-06-18 · Phase 4]
PROBLEM   : Phase 4 was built and shipped to a fully working, tested local pipeline before any cabinet
            review happened — the process the rest of this repo follows (Phase 1 has a debate log) was
            skipped entirely.
SYMPTOM   : User noticed `DEBATE_LOG_phase_1.md` exists with no `_phase_4` counterpart and asked directly.
ROOT CAUSE: The build session went straight from "read the plan" to "execute," treating the `.claude/agents/`
            cabinet personas as background lore rather than an actual review gate to invoke.
SOLUTION  : Ran a retroactive Phase 4 cabinet review — four independent reviewer agents (data-architect,
            business-analyst, data-quality-steward, scope-guardian), each given the real artifacts (not a
            self-assessment) and explicit veto authority. Two hard vetoes landed (RBAC over-grant [003]; the
            undocumented Snowflake provisioning decision, see DECISION_LOG.md) plus two soft vetoes
            (crosswalk/match-rule testability; missing DQ artifacts) — all real findings, not rubber stamps.
FIX IN    : docs/DEBATE_LOG_phase_4.md
OUTCOME   : Two hard vetoes resolved this session (see [003], DECISION_LOG.md). Soft-veto remediation
            (DATA_DICTIONARY.md, DQD.md, dq_flag column, crosswalk hardening) tracked in the same session —
            see PROJECT_STATUS.md for final state.

---

## Phase 5 — Quality

[007] [2026-06-18 · Phase 5]
PROBLEM   : The Phase 4→5 hard blocker "QA sign-off local" had never had a dedicated QA pass — only
            the cabinet's Phase 4 data-quality review, which is a different lens (governance, not
            test-execution verification).
SYMPTOM   : PROJECT_STATUS.md listed it as "⏳ no dedicated QA pass yet" going into Phase 5.
ROOT CAUSE: No standalone Python transform functions exist in this codebase to unit-test in the
            traditional pytest sense — all transform logic lives in dbt SQL models, so "unit tests"
            as originally written in CLAUDE.md's hard-blocker list didn't map cleanly onto this
            dbt-centric architecture.
SOLUTION  : Convened @qa-engineer independently: re-ran `dbt test` (50/50, unchanged), re-ran the GE
            suites (13/13), and wrote 9 new integration tests covering source→Bronze→Silver→Gold
            reconciliation (`tests/integration/test_pipeline_reconciliation.py`) that didn't exist
            before. Accepted dbt's own test framework as the unit-test-equivalent layer for a
            SQL-centric build — standard practice for dbt projects, not a workaround.
FIX IN    : tests/integration/test_pipeline_reconciliation.py
OUTCOME   : Conditional pass — see DECISION_LOG.md for the interpretation call and SIGN_OFF_LOG.md
            Phase 5 entry.

[008] [2026-06-18 · Phase 5]
PROBLEM   : `airflow/dags/pharma_sttm_pipeline.py` had `...` stub task bodies — the other Phase 4→5
            hard blocker, "DPE confirm cloud readiness," was blocked on this.
SYMPTOM   : DAG could not actually run; no real subprocess/dbt calls existed in any task.
ROOT CAUSE: DAG skeleton was scaffolded early but never wired once the real scripts/dbt commands
            existed.
SOLUTION  : Convened @data-platform-engineer to wire every task (`alpha`/`beta`/`gamma` land+bronze,
            `dbt_enrich`, `dbt_marts`, `dbt_serving`, `dq_checks`) to real subprocess calls. While
            verifying cloud-readiness, the same review surfaced a genuine, independent finding: local
            `.venv` has `apache-airflow==3.2.2` unpinned, while AWS MWAA only supports the 2.10.x
            line — the DAG has never been parse-tested against an MWAA-compatible version.
FIX IN    : airflow/dags/pharma_sttm_pipeline.py, docs/OPS_RUNBOOK.md (Session Start Checklist)
OUTCOME   : DAG is real and wired, but the Airflow-version gap is a genuine, documented, NOT-YET-CLOSED
            blocker before any MWAA spike — tracked in PROJECT_STATUS.md, not silently passed over.

[009] [2026-06-18 · Phase 5]
PROBLEM   : @cikgu's first draft of `docs/INTERVIEW_GUIDE.md` described the DAG as "still has stub
            task bodies" in several places (Quick Reference, "What I Would Do Differently," the
            pipeline-architecture Q&A) — stale, because [008]'s DAG wiring had already happened
            earlier in the same session, before @cikgu was convened.
SYMPTOM   : Caught during verification (re-reading @cikgu's output against the actual current file
            state, not trusting the subagent's self-report) — the DAG file itself had no `...` stubs
            left, contradicting the draft's own claims.
ROOT CAUSE: @cikgu was not told about the DAG wiring in its task prompt, so it fell back on
            PROJECT_STATUS.md's older "Next Step When Resuming" text, which predated the wiring.
SOLUTION  : Corrected the stale claims directly (header note, Quick Reference row, "What I Would Do
            Differently" section, pipeline-architecture Q&A) before sending the doc to
            @business-analyst for its honesty check, rather than letting an inaccurate claim ship.
FIX IN    : docs/INTERVIEW_GUIDE.md
OUTCOME   : Generalizes [004]/[005]'s lesson to docs, not just code: a subagent's output is only as
            current as the context it was given — always re-verify against live file state before
            treating a draft as final, especially when other work happened earlier in the same session.

[010] [2026-06-18 · Phase 5]
PROBLEM   : ADR-005 (the S3-canonical storage pivot, landed mid-session) had an internal
            inconsistency: its "Decider" line said "@data-platform-engineer pending," but the document
            already contained a full pre-drafted "Platform / Provisioning Conditions" section (P1–P4)
            and a Stakeholder Sign-off table that already marked @data-platform-engineer as
            "APPROVED-WITH-CONDITIONS" — as if the review had both not happened and already happened.
SYMPTOM   : Noticed on a careful re-read while sourcing context for the DPE sign-off task — no
            debate-log entry existed for ADR-005, unlike the real one for Phase 4.
ROOT CAUSE: P1–P4 were pre-drafted placeholders (a plausible guess at what DPE conditions would look
            like) written when the ADR was authored, never actually independently reviewed.
SOLUTION  : Convened @data-platform-engineer for a genuine review, not a rubber stamp: confirmed
            Condition D's ~2-day migration sizing against the actual current `load_bronze.py` /
            `_sources.yml` code (not understated); tightened P1 (the S3 pointer-swap atomicity
            mechanism was named but not actually specified); added P5 closing a real gap P4 missed —
            the same Airflow 3.x/2.10.x version mismatch from [008] is a precondition for any MWAA
            step in ADR-005's provisioning order, but nothing in the ADR said so until now.
FIX IN    : docs/ADR/ADR-005-s3-canonical-storage-duckdb-compute.md
OUTCOME   : ADR-005's @data-platform-engineer sign-off is now real and internally consistent
            (APPROVED-WITH-AMENDED-CONDITIONS). Migration itself has NOT been started — per the
            owner's explicit choice this session to close out Phase 5 on the current build first.

[011] [2026-06-18 · Phase 5]
PROBLEM   : While sourcing real status for README.md's Business Questions section, found that
            `docs/architecture_handbook/AH.md` and `docs/erwin/ERD.md` are still `[TEMPLATE]` v0.1 —
            i.e. the Documentation Governance (D1, ~30% JD weight) and Data-Model Governance (M1,
            ~20% JD weight) deliverables have not actually been started, despite STTM (G1/G2) being
            fully real at v1.1.
SYMPTOM   : Read both files directly rather than trusting their presence in `docs/` as proof of
            completion.
ROOT CAUSE: Phase 4's build effort concentrated on the dbt pipeline + STTM; AH.md/ERD.md were never
            picked up because CLAUDE.md's narrow Phase 5 definition (DQD+OPS_RUNBOOK+README+
            INTERVIEW_GUIDE) doesn't gate on them, even though the project's own Success Criteria and
            PROJECT_BRIEF's JD weighting do.
SOLUTION  : Reported honestly in README.md's Business Questions table (D1/M1 marked "Not done", not
            glossed over) rather than implying a status that wasn't true. Carried forward as explicit
            open work in PROJECT_STATUS.md rather than silently dropped.
FIX IN    : README.md, PROJECT_STATUS.md
OUTCOME   : Still open — real, scoped, tracked work, not yet started.

[012] [2026-06-18 · Phase 5]
PROBLEM   : Ran `dbt build --target prod` (owner-approved cloud artifact check) against the
            already-provisioned, least-privilege Snowflake objects — it failed.
SYMPTOM   : `dbt debug --target prod` passed (connection OK), but `dbt build` errored on all 3 staging
            models: `SQL compilation error: Schema 'NOVARTIS_STTM_DB.BRONZE' does not exist or not
            authorized.` The seed (`atc_pharmclass_crosswalk`) and `dim_date` built fine — they don't
            depend on Bronze.
ROOT CAUSE: `scripts/load_bronze.py` only ever wrote Bronze into the local DuckDB file
            (`data/warehouse.duckdb`). No equivalent loader has ever pushed Bronze data into Snowflake
            — the `prod` target's connection was verified (`dbt debug`) but the data it depends on was
            never staged there. This had never been caught before because no one had run a full
            `dbt build --target prod` until now — only `dbt debug`.
SOLUTION  : Did not attempt to build a Snowflake Bronze loader as a quick patch — that's new scope
            (a real ingestion-path design decision, ADR-002 territory) requiring its own cabinet
            review, not something to improvise mid-Phase-5-closeout. Confirmed the warehouse
            auto-suspended correctly afterward (state: SUSPENDED, ~3s of actual compute, effectively
            $0 cost) and reported the finding honestly instead of claiming a clean cloud artifact.
FIX IN    : (none yet — root cause is a missing capability, not a bug to patch)
OUTCOME   : Real, valuable finding: this is concrete evidence *for* ADR-005's direction — under
            ADR-005, Snowflake never needs its own Bronze schema at all (it only reads finished Gold
            S3 files as a serving veneer), which sidesteps this exact gap rather than requiring a
            second full Bronze/Silver loader built and maintained for Snowflake. Tracked in
            PROJECT_STATUS.md; the cloud artifact for the *current* architecture is now known to be
            genuinely incomplete (dim_date + seed only), not a deferred "haven't tried yet."

---

## Summary Per Phase

| ID | Problem | Fix Type |
|----|---------|----------|
| 002 | Snowflake role/warehouse/database referenced in `.env` never actually provisioned | Config |
| 003 | RBAC over-grant (`GRANT ALL`) caught by retroactive cabinet review, not a test | Config |
| 004 | DuckDB views don't pick up `.sql` file edits until the model is re-run | Workaround |
| 005 | `dbt snapshot` target table types frozen at first creation; stale after an upstream type fix | Workaround |
| 006 | Phase 4 build shipped without the cabinet review process the rest of the repo follows | Doc/Process |
| 007 | "Unit tests pass" blocker didn't map onto a dbt-SQL-centric build with no standalone Python transforms | Process/Test |
| 008 | DAG had stub task bodies; wiring it surfaced a real Airflow 3.x(dev)/2.10.x(MWAA) version mismatch | Config/Risk |
| 009 | @cikgu's INTERVIEW_GUIDE draft had stale "DAG still stub" claims from before [008]'s wiring | Doc/Process |
| 010 | ADR-005 had a pre-drafted, never-actually-reviewed DPE sign-off section (header said pending) | Doc/Process |
| 011 | AH.md/ERD.md (Docs + Data-Model governance, ~50% combined JD weight) still templates, not started | Scope/Gap |
| 012 | `dbt build --target prod` failed — Bronze schema never loaded into Snowflake, only ever local | Gap (architecture) |
