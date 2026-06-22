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

## ADR-005 Migration — 2026-06-19

[013] [2026-06-19 · ADR-005 Migration]
PROBLEM   : ADR-005 (S3-canonical storage pivot) was already approved, but the document explicitly
            deferred six concrete implementation mechanics to "the build PR" — there was no decided
            answer yet for how the Gold pointer-swap would work atomically, where SCD2 snapshot state
            would persist, whether to widen or separate the Snowflake role, the exact bucket
            name/region/guardrails, whether facts would be incremental or full-rewrite, or the exact
            S3 path layout.
SYMPTOM   : Re-reading ADR-005 before starting the apply showed six "decide at build time" gaps
            rather than a fully specifiable plan — coding would have meant making six
            architecture-adjacent calls ad hoc, mid-implementation, with no review.
ROOT CAUSE: The ADR was written and approved at the "what/why" level (the S3-canonical pivot itself);
            the "how" mechanics were genuinely undecided, not omitted by accident.
SOLUTION  : Convened @data-architect for a dedicated ruling session before writing any migration code.
            Six decisions made and recorded with reasoning each: immutable `gold/_current/`
            copy-on-publish (not a per-run DDL re-point); externalize the `snap_beta_ndc` snapshot to
            `s3://.../snapshots/` as the one accepted persistent store; a NEW scoped
            `snowflake_gold_reader` role instead of widening the existing one; bucket
            `novartis-pharma-sttm-lake` in `ap-southeast-1` with versioning/lifecycle/region-lock
            guardrails shipped in the same create step; full deterministic rewrite of the (small)
            fact tables instead of incremental; and the exact S3 layout for every tier.
FIX IN    : docs/ADR/ADR-005-build-decisions.md
OUTCOME   : The migration apply (still owner-gated per command) had an unambiguous spec to implement
            against. Generalizes [010]'s lesson: an approved ADR is not automatically a buildable one
            — "how" decisions deferred to implementation still need their own reviewed ruling, not an
            ad hoc call made while writing code.

[014] [2026-06-19 · Track I — Incident-Response Gym]
PROBLEM   : `scripts/s3_env.py` failed OPEN — if `S3_ENDPOINT` was simply unset (e.g. someone forgot
            to `source gym.env` before running a drill), it silently resolved to the real, live AWS
            bucket instead of refusing to run.
SYMPTOM   : Found while designing the Track I incident-response gym's safety model, not by an actual
            incident — the failure-injection track (ADR-006) needed to deliberately corrupt/break
            pipeline state, and the existing env-resolution logic had no hard stop preventing that
            from happening against production storage.
ROOT CAUSE: The original env-loading code only branched on whether `S3_ENDPOINT` was *set*, with the
            unset case falling through to whatever default the AWS SDK resolves — which is the real
            bucket, not a deliberate local one.
SOLUTION  : Built `gym.env` (hard-pins `GYM_MODE=1`, bucket=`gym-lake`, local MinIO endpoint, fake
            creds) plus `scripts/gym_guard.py`, a fail-closed preflight every drill script must call:
            it aborts unless every storage variable is verifiably pointed at the local incubator —
            closing the fail-open hole structurally rather than relying on remembering to `source`
            the right file. Codified as ADR-006-A1.
FIX IN    : gym.env, scripts/gym_guard.py, docs/ADR/ADR-006-A1-incubator-fidelity-amendment.md
OUTCOME   : Every subsequent Track I (and later Track S) drill is mechanically blocked from touching
            the live bucket, not just discouraged by convention. This became the project's standard
            incubator pattern, reused unchanged for the Spark+Delta gym in ADR-007.

[015] [2026-06-19 · Track I — Incident-Response Gym]
PROBLEM   : Clearing the Track I troubleshooting library's Snowflake-veneer layer (05) to
            drill-ready hit a wall: the local MinIO pipeline loop needed to independently re-verify
            it kept failing.
SYMPTOM   : `gym-minio` container rejected the credentials in `gym.env` (`mang`/`mangmang`).
ROOT CAUSE: The container had been created in an earlier session with different (stale) credentials
            baked into its volume; `gym.env` had since been updated but the running container never
            picked up the change.
SOLUTION  : Recreated the `gym-minio` container fresh (new anonymous volume, creds aligned to the
            current `gym.env`) and recreated the `gym-lake` bucket, then re-ran the full pipeline loop.
FIX IN    : (operational fix, no code change)
OUTCOME   : Loop passed end-to-end (`dbt build` PASS=63/WARN=1/ERROR=0, `publish_gold.py`,
            GE PASS); layers 04 and 06 cleared to drill-ready (L10), layer 05 cleared with one
            permanent caveat — see [016].

[016] [2026-06-19 · Track I — Incident-Response Gym]
PROBLEM   : One Snowflake card (`L-SNO-03` — `ALTER EXTERNAL TABLE ... REFRESH` stale-metadata
            caching behavior) could not be cleared to drill-ready like its siblings.
SYMPTOM   : Every attempt to reproduce the staleness behavior against the MinIO/DuckDB incubator
            produced no observable caching effect at all.
ROOT CAUSE: The staleness behavior is a property of Snowflake's own external-table metadata cache —
            it has no equivalent in DuckDB+MinIO, so the incubator is structurally incapable of
            reproducing it, not under-tested.
SOLUTION  : Accepted this as a permanent substrate-limit cap rather than a gap to keep chasing —
            `L-SNO-03` stays capped below L5 difficulty permanently. Codified as an ADR-006-A1
            Consequences entry so future sessions don't re-attempt closing an unclosable gap.
FIX IN    : docs/ADR/ADR-006-A1-incubator-fidelity-amendment.md
OUTCOME   : Honest, documented limitation rather than a silently-skipped card. Library proceeded to
            51 cards / all 8 phases drill-ready with this one explicit, accepted exception.

---

## Track I → Track S Transition — 2026-06-20

[017] [2026-06-20 · ADR-007 scoping]
PROBLEM   : The initial proposal for fixing `O-AIR-07` (see [018]) assumed BOTH the SCD2 snapshot
            AND the staging view were losing state across the per-task subprocess boundary — a
            bigger, more expensive fix than was actually needed.
SYMPTOM   : Caught during @senior-data-engineer's Round-1 feasibility review of the proposed
            ADR-007 Spark track sequencing, not by running anything new.
ROOT CAUSE: The snapshot already has its own `snapshot_s3_roundtrip.sql` on-run hook from the
            original ADR-005 build, which the proposer hadn't re-checked before assuming it was
            broken too — only `marts.core`/`dim_drug`'s read of the staging *view* was the actual
            failure point.
SOLUTION  : Corrected the framing before any fix code was written: external-materializing staging
            via a `silver_location()`-style macro is the whole fix; the snapshot needs nothing
            additional.
FIX IN    : (scoping correction, folded into the [018] fix)
OUTCOME   : Avoided building unnecessary snapshot-persistence machinery. Generalizes [010]'s lesson —
            verify an assumed root cause against the actual current code before sizing a fix, even
            (especially) when the assumption sounds plausible.

[018] [2026-06-20 · ADR-007 Fasa A]
PROBLEM   : The orchestrated DAG could never complete a single real run, full stop.
SYMPTOM   : Every dbt-invoking task succeeded individually, but a downstream task referencing an
            upstream model's output failed with a `Catalog Error` as if the upstream had never run.
ROOT CAUSE: Each Airflow task shells out to a separate `dbt` subprocess, and ADR-005 Condition C
            deliberately keeps the DuckDB catalog ephemeral (`:memory:`, no persistent
            `warehouse.duckdb`) — so Silver/snapshot/seed state built by one task's subprocess
            simply did not exist anymore by the time the next task's subprocess started.
SOLUTION  : Externally materialized staging models to S3 (so their data persists independent of any
            one process's in-memory catalog) and added `register_external.sql`, a macro that walks
            through ephemeral intermediate nodes (like `int_drug_crosswalk`) to register their
            external ancestors — without it, a downstream model couldn't even see through an
            ephemeral node to its real external source. Extended the existing seed/snapshot
            S3-roundtrip hooks to fire on `run` and `test`, not just `snapshot`.
FIX IN    : dbt/dbt_project.yml, dbt/macros/register_external.sql,
            dbt/macros/seed_s3_roundtrip.sql, dbt/macros/snapshot_s3_roundtrip.sql,
            airflow/dags/pharma_sttm_pipeline.py
OUTCOME   : Verified against the local MinIO incubator: all 6 dbt steps as genuinely separate
            subprocesses, fresh `:memory:` catalog each time, full `dbt test` PASS=54/WARN=1/ERROR=0.
            The real MWAA parse gate stays green throughout — confirming no gate at any tier had ever
            actually executed a task body, only parsed the DAG file. This defect (named `O-AIR-07`)
            superseded the previously-known `O-AIR-01` as the pipeline's actual first symptom.

[019] [2026-06-20 · ADR-007 Fasa A]
PROBLEM   : A same-day rerun of the pipeline against identical input silently inflated `dim_drug`'s
            SCD2 history.
SYMPTOM   : `dim_drug` row count grew from 133,654 to 133,758 on a rerun where nothing in the source
            data had actually changed.
ROOT CAUSE: `stg_beta__ndc`'s dedup used `row_number() over (partition by product_ndc order by ...)`
            with no fully deterministic secondary sort key — when multiple raw rows for the same
            `product_ndc` tied on the primary sort column, the "winner" row could differ between
            runs, which `dim_drug`'s SCD2 snapshot then recorded as a real change.
SOLUTION  : Added a deterministic secondary tie-break to the `row_number()` ordering — the same bug
            class already hardened in `int_drug_crosswalk.sql`, just missed here. A reviewer flagged
            one residual gap (the tie-break didn't include `load_ts`); checked that `load_ts` is a
            single `current_timestamp` evaluated once per bronze-load query (constant within one
            load, so today's risk was already zero) but added it to the order-by anyway as a
            structural guard against a future per-row-timestamp ingestion refactor.
FIX IN    : dbt/models/staging/beta/stg_beta__ndc.sql
OUTCOME   : Two fresh full `dbt build` reps against byte-identical input produced identical
            `dim_drug` = 133,654 / 133,654 — no growth. Verified against the local MinIO incubator,
            zero contact with the live bucket. Closes "Fasa A" alongside [018]; unblocks ADR-007's
            Spark+Delta track, which had this fix as its hard sequencing prerequisite.

---

## O-AIR-01 + ADR-007 Build — 2026-06-21

[020] [2026-06-21 · Production gap]
PROBLEM   : Even after [018]/[019] let the DAG complete a real run, the run's output still never
            reached anything that read it.
SYMPTOM   : Surfaced by the Track I troubleshooting-library gym (not a live incident) while building
            the orchestration-logs phase: a repo-wide grep showed exactly one call site for
            `publish_gold.py` anywhere in the codebase — the manual `run_pipeline_aws.sh` script —
            and the DAG was not it.
ROOT CAUSE: `pharma_sttm_pipeline.py` had never been wired to thread a `run_id` through its dbt calls
            or to call `publish_gold.py` at all. Every orchestrated run wrote Gold to the fixed
            `gold/dev/` prefix (the `var('run_id', 'dev')` default), which Snowflake's external-table
            veneer and Great Expectations both read from `gold/_current/` instead — a prefix the DAG
            never touched.
SOLUTION  : Added a `gold_run_id(ts_nodash)` helper deriving one shared `run_id` per DAG run from the
            logical timestamp (no XCom needed), threaded it through every `dbt(...)` call via
            `--vars`, and split the old combined `dq_checks()` task into
            `dbt_test → publish_gold → dq_validate` so Gold is verify-then-copied into
            `gold/_current/` *before* GE validation reads it.
FIX IN    : airflow/dags/pharma_sttm_pipeline.py
OUTCOME   : Independently re-verified against a fresh MinIO incubator run end-to-end (dbt test
            PASS=54/WARN=1/ERROR=0, all 7 Gold objects verify-then-copied, GE PASS, re-run idempotent)
            and against the real MWAA parse gate. This defect (`O-AIR-01`) had been quietly true
            since the DAG was first wired in Phase 5 [008] — only became visible once [018] let a run
            get far enough to reach it. Two non-blocking risks flagged and accepted: no
            rollback/atomicity across `publish_gold.py`'s per-object copy loop (deliberate ADR-005
            design — a mid-loop failure degrades, never corrupts, any single model), and no
            `gold/<run_id>/` retention policy (acceptable for a portfolio gym, already a tracked
            FinOps watch item).

[021] [2026-06-21 · ADR-007 gate-0]
PROBLEM   : Before any Spark drill could run against even the local MinIO incubator,
            `scripts/spark_gym_guard.py`'s own safety checks had two real holes.
SYMPTOM   : Found by @data-platform-engineer's gate-0 review, reading the guard's logic directly
            rather than trusting that "it has checks" meant the checks were sound: (1) the local-host
            check matched `SPARK_S3_ENDPOINT` via a naive substring test against a list of local
            hints, so a spoofed hostname like `evil-localhost.attacker.com` would incorrectly pass;
            (2) `SPARK_AWS_SECRET_ACCESS_KEY` was not shape-validated at all, so a real-looking AWS
            secret could ride through a "drill" run undetected.
ROOT CAUSE: The guard's first-pass implementation matched the SAME pattern class ADR-006-A1's
            `gym_guard.py` already had to harden, just not yet applied here — substring/presence
            checks instead of exact, structural validation.
SOLUTION  : Parsed the endpoint via `urllib.parse.urlsplit(...).hostname` and compared it against an
            exact `LOCAL_HOSTNAMES` set (no substring matching); added `_looks_real_aws_secret()` to
            reject any 40+-character base64-charset value. Both fixed the same day they were found.
FIX IN    : scripts/spark_gym_guard.py, tests/unit/test_spark_gym_guard.py
OUTCOME   : Regression-pinned into 16 unit checks (later 31 after the demo-mode extension), including
            3 spoofed-endpoint cases and 1 real-shaped-secret case. Independently re-verified by
            @senior-data-engineer with additional adversarial cases of their own before ratification.

[022] [2026-06-21 · ADR-007 B4]
PROBLEM   : The first real run of the Spark+Delta demonstration track crashed immediately.
SYMPTOM   : `java.lang.UnsupportedOperationException: getSubject is not supported`, thrown during
            JVM/Spark gateway startup, before `SparkSession.builder.getOrCreate()` completed.
ROOT CAUSE: This Codespace's default JDK is 25, but Hadoop 3.3.4's
            `UserGroupInformation.getCurrentUser()` calls `Subject.getSubject()`, which was removed
            in JDK 24+. `scripts/run_spark_demo_aws.sh` set a `SPARK_JAVA_HOME` variable (mirroring
            the name `spark_delta_demo_dag.py`'s `run()` helper reads) but never itself translated
            that into the actual `JAVA_HOME`/`PATH` the JVM launcher reads — so the pinned Java 21
            from `requirements-spark.txt` was never actually picked up by this entrypoint.
SOLUTION  : Added `export JAVA_HOME="${SPARK_JAVA_HOME}"` plus prepending
            `${SPARK_JAVA_HOME}/bin` to `PATH`, mirroring the override the DAG helper already did per
            subprocess.
FIX IN    : scripts/run_spark_demo_aws.sh
OUTCOME   : Crash occurred before any S3A client was constructed, so neither the real prod bucket nor
            the new staging bucket was ever contacted by the failed attempt — zero blast radius.
            Second attempt succeeded: read `gold/_current/` read-only, wrote 5 Delta tables to the
            isolated staging bucket, and `reconcile.py` matched the DuckDB mart exactly on all 5 star
            models (dim_date 4,383, dim_condition 836, dim_drug 133,654, fact_sales 16,848,
            fact_review 215,063).

[023] [2026-06-21 · Governance housekeeping]
PROBLEM   : A CI gate that had nothing to do with the work being reviewed showed up red.
SYMPTOM   : `.github/workflows/ci.yml`'s "sealed answer keys must stay untracked" step was failing on
            `main`, discovered as a side-finding during the ADR-007 gate-0 ratification, not because
            anyone touched that gate directly.
ROOT CAUSE: The check encoded an assumption from ADR-006-A1 (gym answer keys under
            `docs/incidents/.solutions/` must never be committed, to keep them sealed). That
            assumption stopped holding the moment the repo went private and the owner deliberately
            committed the rubric files for `@cikgu`-teaching durability against Codespace data loss —
            the gate had no way to know that change of context was intentional.
SOLUTION  : Rather than reverting the deliberate tracking decision to satisfy a stale gate, retired
            the now-superseded CI step and recorded why in a one-line ADR-006-A1 addendum — the
            owner's call, presented as a choice rather than forced.
FIX IN    : .github/workflows/ci.yml, docs/ADR/ADR-006-A1-incubator-fidelity-amendment.md
OUTCOME   : CI green again for the right reason (gate retired with a documented rationale), not by
            quietly reverting a real decision to make a check pass.

---

## Repo Governance — 2026-06-21

[024] [2026-06-21 · Repo governance]
PROBLEM   : All of the AI/agent scaffolding driving this project's process (`.claude/`, `CLAUDE.md`,
            the cabinet agent prompts, `learning/`, the optimization/troubleshooting cheatsheets,
            `docs/incidents/`, and the working logs like this one) had been kept local-only via
            `.git/info/exclude` — deliberately never pushed, to keep Claude/cabinet traces out of a
            public GitHub repo. That left a single point of failure.
SYMPTOM   : None yet observed — this was a risk caught proactively, not an incident. All of that
            local-only material existed nowhere but this one Codespace's working tree.
ROOT CAUSE: A Codespace's local filesystem is not durable against the environment being reclaimed,
            timed out, or usage-limited — anything excluded from git had exactly one copy, with no
            backup.
SOLUTION  : Committed everything previously local-only in one pass (`93c83a5`), explicitly
            conditioned on the owner separately flipping the repo to private right after — removing
            the original reason that material had been excluded in the first place. Real env files,
            `data/` (already canonical in S3 per ADR-005), `.venv/`, and `target/` stayed excluded
            (genuinely regenerable/sensitive, not process history).
FIX IN    : (git history — commit 93c83a5; repo visibility flip — owner action, 2026-06-21)
OUTCOME   : Project's full process history — every ADR, sign-off, cabinet prompt, and learning
            artifact — now durable in git, not just on one Codespace's disk. This is also why the
            "no Claude traces in public repos" scrubbing rule is currently suspended for this repo:
            the repo is private and the owner deliberately chose to keep the scaffolding, not an
            oversight to fix later.

---

## Housekeeping — 2026-06-22

[025] [2026-06-22 · Repo hygiene]
PROBLEM   : A local branch looked like it might contain unmerged work that had been lost.
SYMPTOM   : `git merge-base main feature/adr-005-p5-mwaa-parse-gate` returned nothing — the two
            branches share no common history at all, and the branch's tip commit (the SLA-gym
            L3/L5/L8 self-play work) is reachable from neither `main`'s current HEAD nor any ancestor
            of it.
ROOT CAUSE: An earlier session squashed/rewrote the repo's history into a single fresh initial commit
            (e.g. for the public-repo Claude/cabinet-trace scrub), which orphaned any branch that had
            been pointing into the old, now-discarded commit graph — without deleting the branch
            itself.
SOLUTION  : Before assuming anything was lost, diffed the orphaned branch's file contents directly
            against `main`'s working tree (`git diff <branch>:<path> HEAD:<path>` per file) instead of
            trusting the absence of a merge-base as proof of data loss.
FIX IN    : (verification only, no code change)
OUTCOME   : Confirmed byte-identical — the branch's content had already been folded into `main`'s
            squashed initial commit. Nothing was lost; the branch is safe to delete. Generalizes
            [009]'s lesson once more: an alarming git signal (no merge-base) needs the same
            verify-before-trusting treatment as a stale doc or a subagent's claim.

[026] [2026-06-22 · Documentation drift]
PROBLEM   : Several of the project's own status documents had quietly fallen out of sync with the
            actual state of the repo across sessions — not just "incomplete," but actively saying the
            opposite of what had already happened.
SYMPTOM   : `PROJECT_STATUS.md`'s own header admitted a backfill was "still owed"; its "Next Step"
            section listed the README refresh, Track B SLA-gym seeding, and the `@cikgu` handover as
            not-yet-started, when git history and `LEARNING_LOG.md` showed all three already done and
            committed. Separately, `CLAUDE.md`'s "Project Overview" header still held the gym's
            literal `<PROJECT_NAME>`/`<domain>` template text even though every other section of the
            same file was filled in with real specifics, and `COST_LOG.md` had zero mention of the
            Spark staging bucket despite it being a real, provisioned AWS resource.
ROOT CAUSE: Each status doc was updated within the session that produced the work it describes, but
            no session made a pass to re-sync ALL the status docs against the cumulative state after
            several sessions' worth of Track I/Track S work had landed — staleness compounded
            silently because nothing ever re-read these docs against `git log` to check.
SOLUTION  : Verified actual state directly (git log, working-tree greps for unfilled template
            patterns, `LEARNING_LOG.md`) rather than trusting any one doc's self-description, then
            backfilled `PROJECT_STATUS.md`, `CLAUDE.md`, `COST_LOG.md`, and `learning/CURRICULUM.md`
            to match reality.
FIX IN    : PROJECT_STATUS.md, CLAUDE.md, COST_LOG.md, learning/CURRICULUM.md
OUTCOME   : All four docs now reflect actual current state. Generalizes [009]/[025]: trust the
            primary sources (git log, working tree, code) over any document's claim about itself —
            including this project's own status-tracking docs, which are just as capable of drifting
            stale as a subagent's draft or a confusing git signal.

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
| 013 | ADR-005 approved at "what" level; six "how" build mechanics undecided at apply time | Doc/Process |
| 014 | `scripts/s3_env.py` failed open on an unset `S3_ENDPOINT`, silently defaulting to the live bucket | Security/Config |
| 015 | Stale `gym-minio` container credentials blocked the MinIO incubator loop | Infra/Workaround |
| 016 | Snowflake `REFRESH` stale-metadata caching can't be reproduced on MinIO/DuckDB | Gap (architecture, accepted) |
| 017 | Initial `O-AIR-07` fix proposal over-scoped — assumed snapshot state was lost too | Scope/Process |
| 018 | Orchestrated DAG could never complete a real run — ephemeral `:memory:` catalog lost state across task subprocess boundaries | Bug (production) |
| 019 | `stg_beta__ndc` dedup non-idempotent — same-day rerun inflated `dim_drug` SCD2 history | Bug (production) |
| 020 | DAG never threaded `run_id` / never called `publish_gold.py` — every run silently wrote to an unread `gold/dev/` prefix | Bug (production) |
| 021 | `spark_gym_guard.py` had a spoofable hostname check and no AWS-secret-shape validation | Security |
| 022 | Real Spark demo run crashed at JVM startup — JDK 25 incompatible with Hadoop 3.3.4 | Config/Infra |
| 023 | CI gate asserting sealed rubrics stay untracked went red after a deliberate tracking decision | Doc/Process |
| 024 | AI/agent scaffolding existed only on one Codespace's disk, with no backup | Risk/Process |
| 025 | Orphaned git branch with no merge-base to `main`, looked like lost work | Repo hygiene |
| 026 | Project status docs (PROJECT_STATUS/CLAUDE/COST_LOG/CURRICULUM) drifted stale across sessions | Doc/Process |
