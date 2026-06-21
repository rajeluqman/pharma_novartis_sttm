# SIGN_OFF_LOG.md
**Owner**: @project-manager

Phase transition sign-offs.

---

## Phase 1 — Discovery
**Date**: YYYY-MM-DD
**Status**: APPROVED / VETOED / CONDITIONAL

| Agent | Status | Reason |
|-------|--------|--------|
| @product-owner | ✅ | <reason> |
| @business-analyst | ✅ | <reason> |
| @data-architect | ✅/⚠️/🛑 | <reason> |
| @scope-guardian | ✅ | <reason> |
| @finops-agent | ✅ | <reason> |

**Outcome**: <Phase locked / Pivot required>

---

## Phase 2 — Exploration
(repeat)

---

## Phase 3 — Design
(repeat)

---

## Phase 4 — Build
**Date**: 2026-06-18
**Status**: CONDITIONAL → APPROVED (conditions resolved same session — retroactive review, see `docs/DEBATE_LOG_phase_4.md`)

| Agent | Status | Reason |
|-------|--------|--------|
| @data-architect | ✅ | RBAC veto (GRANT ALL) resolved via ADR-004 + scoped re-grant; dim_drug/SCD2/hash-key decisions approved (one with conditions, both met: `drug_member_type` column added, singular row-count test added) |
| @business-analyst | ✅ | Crosswalk hardened (word-boundary + length guard, combination-product exclusion, deterministic tie-break); SLA set for fact_review.drug_sk (≥65%) and condition_sk (≥90%) in DQD.md; manufacturer-attribution caveat documented |
| @data-quality-steward | ✅ | DATA_DICTIONARY.md and DQD.md filled; dq_flag/dq_reason traceability added; Great Expectations suite populated (3/3 passing) — all stated conditions met |
| @scope-guardian | ✅ | Snowflake provisioning event retroactively logged in DECISION_LOG.md/JOURNEY_LOG.md; Beta bulk download, cross-dialect macros, and dbt tests all confirmed in-scope |
| @data-platform-engineer | n/a | not convened this session |
| @finops-agent | n/a | not convened this session — Snowflake spend still $0 (XSMALL, auto-suspend 60s, no prod dbt build run yet) |

**Outcome**: Phase 4 locked. The process gap that prompted this retroactive review (no cabinet
review before Phase 4 shipped) is itself logged in `JOURNEY_LOG.md` [006] as a process fix for
future phases — convene the relevant cabinet agents *before* running build-affecting or
cloud-affecting actions, not after.

---

## Phase 5 — Quality + Docs
**Date**: 2026-06-18
**Status**: APPROVED (current/pre-ADR-005 build) — with explicit, tracked carve-outs, not a clean close

| Agent | Status | Reason |
|-------|--------|--------|
| @data-platform-engineer | ✅ (conditional) | Wired `airflow/dags/pharma_sttm_pipeline.py` for real (every task now shells out to the actual script/dbt command). Cloud-readiness verdict: NOT YET ready for an MWAA spike — found a real, verified Airflow version mismatch (local `.venv` unpinned `apache-airflow==3.2.2` vs. MWAA's supported 2.10.x line), documented as a pre-spike gate in `docs/OPS_RUNBOOK.md`. Separately gave the pending ADR-005 sign-off: APPROVED-WITH-AMENDED-CONDITIONS (P1 tightened, P5 added covering this same Airflow-version gap) — assessment only, migration not started |
| @qa-engineer | ✅ (conditional) | Local QA pass: `dbt test` re-run (50/50, 49 pass/1 documented warn, unchanged), Great Expectations re-run (13/13 across 3 suites, pass), wrote 9 new integration tests (`tests/integration/test_pipeline_reconciliation.py`) covering source→Bronze→Silver→Gold reconciliation that didn't exist before — independently re-verified by hand against the live warehouse this session (9/9 pass). Conditional only on the judgment call that dbt's own tests serve as the unit-test-equivalent layer (see `DECISION_LOG.md`) |
| @cikgu | ✅ | Drafted `docs/INTERVIEW_GUIDE.md` (8 sections — Quick Reference, 3 STAR stories, lessons, decision logic, Q&A, resume bullets, interviewer questions), sourced from real logs; explicitly avoided the stale Databricks/Spark `PERFORMANCE_LOG.md`/`COST_LOG.md` boilerplate; flagged 2 tone spots for @business-analyst |
| @business-analyst | ✅ | Honesty-checked `INTERVIEW_GUIDE.md` — cross-verified every Quick Reference number, all 3 STAR stories, and every resume-bullet number (Section 7) against `DQD.md`/`STTM.md`/`JOURNEY_LOG.md`/`DECISION_LOG.md`. Verdict: APPROVED, no fabrication or over-claiming found. Noted (out of scope to fix here) a pre-existing internal inconsistency in `DQD.md` itself (4.1%/5,524 vs. 4.4%/5,881 for the same seed-reach metric) — owned by @data-quality-steward |
| @data-architect | n/a | not convened this Phase 5 session — ADR-005's architecture decision and @data-architect's veto-holder approval of it predate this session |
| @scope-guardian | n/a | not convened this session |
| @finops-agent | n/a | not convened this session — ADR-005's FinOps conditions were signed off before this session; no new spend, $0 |

**Outcome**: Phase 5 as scoped by `CLAUDE.md` (DQD + OPS_RUNBOOK + README + INTERVIEW_GUIDE) is
complete and real — `README.md` and `OPS_RUNBOOK.md` filled from verified build evidence,
`INTERVIEW_GUIDE.md` drafted and honesty-checked, `DQD.md`/`DATA_DICTIONARY.md` already done ahead of
schedule in Phase 4 remediation. All three Phase 4→5 hard blockers are resolved, conditionally, with
the conditions documented rather than hidden: unit tests (50 dbt tests + 9 integration tests, all
passing), QA sign-off local (conditional — dbt-tests-as-unit-tests interpretation, see
`DECISION_LOG.md`), DPE cloud-readiness confirm (conditional — the Airflow-version-pin gap is a real,
documented, **not-yet-closed** blocker before any MWAA spike).

**Explicitly NOT closed, and not silently dropped**: `docs/architecture_handbook/AH.md` and
`docs/erwin/ERD.md` remain `[TEMPLATE]` — the Documentation Governance (D1) and Data-Model Governance
(M1) deliverables (~50% combined JD weight per `PROJECT_BRIEF.md`) have not been started. `CLAUDE.md`'s
narrow Phase 5 definition doesn't gate on them, but the project's own Success Criteria do — tracked as
open work in `PROJECT_STATUS.md`, not implied done by this sign-off.

**ADR-005** (S3-canonical storage pivot): accepted (conditional) before this session;
@data-platform-engineer's then-pending sign-off was closed this session
(APPROVED-WITH-AMENDED-CONDITIONS). Per the owner's explicit choice (close out Phase 5 on the current
build first), the actual migration has **not been started** — tracked as its own next phase.

---

## Lead Deliverables — AH.md + ERD.md (Documentation D1 + Data-Model M1 governance)
**Date**: 2026-06-18
**Status**: APPROVED (signed off by veto-holder owner)

| Agent | Status | Reason |
|-------|--------|--------|
| @data-architect | ✅ | Convened **before** the fill (R1–R8 ruling memo: as-built normative + ADR-005 fenced as unmigrated TARGET; ERD all 3 layers, varchar hash SKs w/ date_sk int exception; dim_drug ONE table w/ `drug_member_type` discriminator + standing match_confidence/provenance veto reproduced; SCD0/2/1; naming conventions verbatim; least-privilege RBAC principle). Filled drafts brought back for sign-off review — cross-checked against as-built code, **SIGNED OFF**, all R1–R8 satisfied, 3 minor non-blocking notes recorded, no veto |

**Outcome**: `docs/architecture_handbook/AH.md` (v1.0) and `docs/erwin/ERD.md` (v1.0) filled from real
build evidence and signed off by @data-architect. Both now describe the **as-built DuckDB pipeline**
as normative, with the ADR-005 S3-canonical target clearly fenced as approved-but-not-migrated.
**Next gate (not done here)**: Confluence publish — @data-platform-engineer runs
`scripts/publish_to_confluence.py`, @project-manager logs the publish event. Process note: convening
@data-architect *before* filling (per `JOURNEY_LOG.md` [006] process fix) worked as intended — real
rulings issued and verified, not a rubber stamp.

---

## Confluence Publish — AH + ERD (closes the Lead Deliverables publish gate)
**Date**: 2026-06-18
**Status**: PUBLISHED (executed under the existing @data-architect approval — no new sign-off gate)

| Agent | Status | Reason |
|-------|--------|--------|
| @data-platform-engineer | ✅ (executor) | Built `scripts/publish_to_confluence.py` (previously specced in `CLAUDE.md` Lead Deliverables, never actually built) and ran it against Confluence Cloud (site luqman10.atlassian.net, space NSL). Published the two **already-signed-off** Lead Deliverables — no content re-approval needed, the @data-architect gate was PASSED in the "Lead Deliverables" entry above |
| @data-architect | ✅ (pre-existing gate) | Approval gate on AH.md/ERD.md before Confluence publish (per `CLAUDE.md`) was already PASSED in the "Lead Deliverables — AH.md + ERD.md" entry above — this publish was the mechanical execution of that approved decision, not a new ruling |

**What was published**:
- **AH** (`docs/architecture_handbook/AH.md` v1.0) → UPDATED existing page id **131460**, version v1 → **v2**. URL: https://luqman10.atlassian.net/wiki/spaces/NSL/pages/131460
- **ERD** (`docs/erwin/ERD.md` v1.0) → CREATED new page id **98553**, title "Erwin Data Model (ERD) — Novartis Pharma STTM Lab", version **v1**. URL: https://luqman10.atlassian.net/wiki/spaces/NSL/pages/98553
- New env key persisted: `CONFLUENCE_PAGE_ID_ERD=98553` (in `.env`, placeholder in `.env.example`).

**Outcome**: The previously-open "Confluence publish gate" on the AH + ERD Lead Deliverables (flagged
in the "Lead Deliverables" entry above and tracked open in `PROJECT_STATUS.md`) is now **CLOSED** —
both documents are live in Confluence space NSL. **STTM remains UNPUBLISHED / open**: `docs/sttm/STTM.md`
(page 98534) was explicitly **out of scope** this run — owner asked for AH + ERD only. STTM publish is
still a future step, not closed by this entry.

---

## STTM Publish Sign-off — docs/sttm/STTM.md (Lineage governance, approval gate before Confluence)
**Date**: 2026-06-18
**Status**: SIGNED OFF WITH ONE REQUIRED PRE-PUBLISH FIX (applied by @data-architect; no veto)

| Agent | Status | Reason |
|-------|--------|--------|
| @data-architect | ✅ | Approval gate on `docs/sttm/STTM.md` before Confluence publish (per `CLAUDE.md` Lead Deliverables). Reviewed v1.1 in full against as-built code and governance with the same R1–R8 rigor applied to AH/ERD. **Five-point check passed**, one banner fix required-and-applied (below). No substantive rework needed — not a veto. |

**What was checked (and the basis):**
- **As-built fidelity** — STTM maps the pipeline that actually runs: DuckDB local target named throughout (line 6 banner, RRD note line 169 "no-op on the DuckDB dev target"); real Enrich (`stg_alpha__sales` unpivot, `stg_beta__ndc` dedup/array-flatten, `stg_gamma__reviews` normalize+scrub), `int_drug_crosswalk` (ephemeral, ADR-003), Mart (`dim_drug` SCD2 + 8 synthetic category rows, `dim_date` SCD0, `dim_condition` SCD1, `fact_sales`, `fact_review`), and RRD OBTs. Matches AH §3/§4 and the ERD. ✅
- **ADR-005 fencing** — STTM correctly **stays silent** on the S3-canonical / `external`-materialization target. The sole forward-looking mention (line 169) frames Snowflake `cluster_by` as a target-conditional no-op on DuckDB; it does **not** imply S3 external materialization is live. No governance defect (cf. AH R1 — an unmigrated target must never read as current state). The required banner fix (below) makes the as-built / not-migrated stance explicit on the doc's face. ✅
- **Standing vetoes preserved** — (1) `match_confidence` is NOT overloaded with row provenance; provenance lives in `drug_member_type` (lines 94, 109–118, plus the explicit Phase-4 revision note reproducing the veto). ✅ (2) least-privilege RBAC (ADR-004) is not contradicted — STTM is column-lineage, RBAC lives in AH §2 / ADR-004, no over-grant implied. ✅ (3) `atc_category` vs `ndc_product` row-type distinction is structural (line 94 + exact-8 singular test, line 112). ✅ (4) varchar hash SKs with `date_sk` as the only smart-integer exception (lines 93, 123, 131, 137, 148). ✅
- **Coverage KPIs honest** — presented as ADR-003 partial-match DQD KPIs, not hidden bugs: seed-reach 4.1% (5,524/133,646) explicitly labelled "measures seed reach, not matching-algorithm quality" (lines 80–88); free-text match-quality 71.9% (154,641/215,063, SLA ≥65%) and condition 98.9% (212,698/215,063) on `fact_review` (line 158). **STTM does NOT repeat the known DQD.md internal inconsistency** (4.1%/5,524 vs 4.4%/5,881 for seed-reach) — it uses 4.1%/5,524 consistently throughout. That DQD inconsistency remains owned by @data-quality-steward and is out of scope for this STTM gate. ✅
- **Version/status banner** — the only real pre-publish defect: header read "Phase 4 build complete..." which is not an externally-honest publish-state banner. **Fixed** (below). ✅

**Edit applied to `docs/sttm/STTM.md` (banner, line 6) — non-substantive, status only:**
- OLD: `**Status:** Phase 4 build complete + retroactive cabinet review remediated (local/DuckDB dev target) — see docs/DEBATE_LOG_phase_4.md`
- NEW: `**Status:** APPROVED FOR PUBLISH — @data-architect signed off 2026-06-18 (SIGN_OFF_LOG.md "STTM Publish Sign-off"). Describes the as-built DuckDB local target (Phase 4 build complete + retroactive cabinet review remediated — see docs/DEBATE_LOG_phase_4.md). The ADR-005 S3-canonical target is approved but NOT migrated; this map is normative for what runs today.`
- No content/lineage rows changed.

**Outcome**: `docs/sttm/STTM.md` v1.1 is **fit to publish externally as-is** (with the banner fix landed). The @data-architect approval gate (per `CLAUDE.md`) is **PASSED**. **GO** for @data-platform-engineer to publish STTM to Confluence page **98534** via `scripts/publish_to_confluence.py`; @project-manager logs the publish event. This entry is the approval — the publish itself is mechanical execution, no new ruling required.

---

## Confluence Publish — STTM (closes the STTM publish gate; completes the AH+ERD+STTM set)
**Date**: 2026-06-18
**Status**: PUBLISHED (executed under the existing @data-architect GO — no new sign-off gate)

| Agent | Status | Reason |
|-------|--------|--------|
| @data-platform-engineer | ✅ (executor) | Ran `scripts/publish_to_confluence.py sttm` against Confluence Cloud (site luqman10.atlassian.net, space NSL). Published the **already-signed-off** STTM — no content re-approval needed, the @data-architect GO was given in the "STTM Publish Sign-off" entry above. Table conversion verified clean (11 tables landed). |
| @data-architect | ✅ (pre-existing gate) | Approval gate on `docs/sttm/STTM.md` before Confluence publish (per `CLAUDE.md`) was already PASSED in the "STTM Publish Sign-off" entry above (GO given, status banner bumped to "APPROVED FOR PUBLISH") — this publish was the mechanical execution of that approved decision, not a new ruling. |

**What was published**:
- **STTM** (`docs/sttm/STTM.md`) → UPDATED existing page id **98534**, title "Source-to-Target Mapping (STTM) — Novartis Pharma STTM Lab", version **v1 → v2**, space NSL. URL: https://luqman10.atlassian.net/wiki/spaces/NSL/pages/98534
- **AH** (page 131460) and **ERD** (page 98553) were **NOT touched** by this run.
- 11 tables converted and landed cleanly (verified).

**Outcome**: The previously-open "STTM Confluence publish" item (flagged in the "STTM Publish Sign-off" entry above and tracked open in `PROJECT_STATUS.md`) is now **CLOSED** — STTM is live in Confluence space NSL. With AH (131460 v2) and ERD (98553 v1) already published, **all three Lead Deliverables are now live in Confluence — the Confluence publish workstream is fully CLOSED**.

---

## ADR-005 Build Design Ruling (@data-architect)
**Date**: 2026-06-19
**Status**: DESIGN RULING APPROVED — apply remains OWNER-GATED (human). Recorded in `docs/ADR/ADR-005-build-decisions.md`.

| Agent | Status | Reason |
|-------|--------|--------|
| @data-architect | ✅ | Veto-holder ruling on the six *how* decisions ADR-005 deferred to "the build PR". Each ruled with Decision / Reasoning / ADR-or-principle ref, grounded against as-built code (`load_bronze.py`, `_sources.yml`, `dbt_project.yml`, `profiles.yml`, `stg_alpha__sales.sql`, `snap_beta_ndc.sql`, `fact_sales.sql`, `fact_review.sql`, `obt_sales_wide.sql`). No veto. |

**The six decisions (one line each):**
1. **P1 pointer-swap** — adopt **(B) immutable `gold/_current/` copy-on-publish**; Snowflake reads the fixed `_current/` prefix, never re-points DDL per run. Rollback = re-copy prior run, no DDL, smaller blast radius than (A). (ADR-005 P1 / Condition A)
2. **Condition C snapshot state** — externalize `snap_beta_ndc` history to `s3://<bucket>/snapshots/` as parquet (the ONE accepted persistent store; it is canonical *data*, not a catalog → does not violate "no persistent `warehouse.duckdb` as truth"). (ADR-005 Condition C/B, ADR-003)
3. **Snowflake role** — provision a **NEW separate `snowflake_gold_reader`** role scoped to `gold/*`; do NOT widen `NOVARTIS_STTM_ROLE`. (ADR-005 P1, ADR-004 owner-vs-scoped-grant)
4. **S3 bucket** — name **`novartis-pharma-sttm-lake`**, region **`ap-southeast-1`** (== compute region); guardrails ship in the SAME create step: versioning ON, noncurrent-version expiry ≈30d, `aws:RequestedRegion` Deny, `landing/` delete-deny (write-once). (ADR-005 P2/P3/FinOps)
5. **Incremental facts** — drop `incremental`; **full deterministic rewrite** of `fact_sales`/`fact_review` (facts are small, hashed SKs are reproducible). Staging+merge rejected. (ADR-005 Condition A no-atomic-rename, Condition C ephemeral catalog)
6. **S3 layout + load-meta** — confirm `landing/` · `bronze/<src>/<date>/` · `silver/` · `snapshots/` · `gold/<run_id>/` + `gold/_current/`; `load_ts`/`source_file` ride on every bronze+ object (preserved through the parquet migration). (ADR-005 §1/Guardrails, ADR-002)

**Authorized (design only)**: bucket `novartis-pharma-sttm-lake` @ `ap-southeast-1`.
**MWAA is OUT this round** — orchestration stays on local `aws-mwaa-local-runner` ($0); P4/P5 (Airflow-version MWAA gates) not triggered.
**The apply remains OWNER-GATED (human)** — every AWS/Snowflake create command needs the owner's explicit per-command confirmation at execution time (ADR-005 "Provisioning & Teardown (OWNER-GATED)", CLAUDE.md). This entry authorizes the PLAN, not the apply.

---

## AH/ERD/STTM Post-Migration Refresh + Re-Sign-off (@data-architect)
**Date**: 2026-06-19
**Status**: APPROVED FOR RE-PUBLISH (@data-architect approval gate PASSED — no veto)

**Why**: ADR-005 was MIGRATED and went LIVE on real AWS this session (run_id `run-20260619-045115`), verified end-to-end. The three Lead Deliverables, as published to Confluence 2026-06-18 (AH 131460 v2 / ERD 98553 v1 / STTM 98534 v2), still framed ADR-005 as "approved but NOT migrated, DuckDB local target, pre-ADR-005" — now factually STALE. Refreshed all three to the as-built MIGRATED reality and re-signed off.

| Agent | Status | Reason |
|-------|--------|--------|
| @data-architect | ✅ | Approval gate on AH.md / ERD.md / STTM.md. All three refreshed to as-built S3-canonical MIGRATED state, consistent with `docs/ADR/ADR-005-build-decisions.md` (six build decisions, all reflected). Logical model UNCHANGED (no grain/key/SCD change → ERD not re-cut, STTM lineage rows untouched). Honest on scope: MWAA still OUT, orchestration local; Snowflake holds zero dbt-written tables (external-table veneer only). No veto. |

**What changed in each doc (versions bumped):**
- **AH.md → v3.0** (Last approved 2026-06-19). §1 scope flipped to as-built MIGRATED; §3 Layer Definitions rewritten to S3-canonical + DuckDB httpfs + `external` materialization + Snowflake external-table veneer; new §3a migration evidence (dbt 63 PASS/1 WARN/0 ERR, GE PASS, KPIs == baseline, gold/_current/ publish, storage guardrails, snapshot externalization); old DuckDB-local-file build moved to §3b (historical/superseded, kept short). §2 RBAC principle notes the new scoped `snowflake_gold_reader` role (ADR-005 Decision 3). §4 lineage paths → S3 parquet + Snowflake external tables. §5 orchestration → local runner, MWAA out, parse gate closed. §7 added migration row. §8 ADR-005 marked DONE & LIVE; re-publish flagged.
- **ERD.md → v2.0** (Last approved 2026-06-19). Status banner → as-built MIGRATED (physical layer now S3 external parquet; staging reads `read_parquet('s3://.../bronze/...')`; snapshot to `snapshots/`; facts full rebuild). **Logical model (DBML tables/keys/grains/SCD) UNCHANGED.** OBT notes + RRD group comment updated to the Snowflake external-table veneer (`obt_sales_wide_ext` 16,848 / `obt_review_wide_ext` 215,063). Open items: migration DONE.
- **STTM.md → v3.0** (status APPROVED FOR RE-PUBLISH). Status banner → as-built MIGRATED + a migration note explaining the physical **source binding** change (relational `bronze.x` → `read_parquet('s3://.../bronze/<src>/<date>/...')`, Silver/Gold `external` on S3, facts full deterministic rebuild per Decision 5). **Column-level lineage rows UNCHANGED** (same source tables/columns/transforms). OBT serving section refreshed to the external-table veneer. Change-log row added. Version jumped 1.1→3.0 to align with AH v3.

**Standing vetoes/principles preserved**: ADR-001 (OBT derived from star, not a source of truth), ADR-003 (honest partial-match KPIs — 71.9%/98.9% unchanged), ADR-004 least-privilege (new reader role is *narrower*, not a widening), `drug_member_type` structural distinction, varchar hash SKs with `date_sk` exception. KPIs identical to baseline — no overclaiming.

**Outcome**: AH v3 / ERD v2 / STTM v3 are **APPROVED FOR RE-PUBLISH to Confluence** (AH 131460, ERD 98553, STTM 98534, space NSL), superseding the 2026-06-18 stale versions. **GO** for @data-platform-engineer to re-publish via `scripts/publish_to_confluence.py`; @project-manager logs the re-publish event. Re-publish is mechanical execution of this approved decision — no new ruling required. @data-architect does NOT publish; infra apply stays owner-gated (unchanged by this doc refresh).

---

## Confluence Re-Publish — AH/ERD/STTM Post-Migration (executed under @data-architect re-sign-off)
**Date**: 2026-06-19
**Status**: PUBLISHED (executed under the existing @data-architect GO above — no new sign-off gate)

| Agent | Status | Reason |
|-------|--------|--------|
| @data-platform-engineer | ✅ (executor) | Ran `scripts/publish_to_confluence.py` against Confluence Cloud (site luqman10.atlassian.net, space NSL) to re-publish the three **already-signed-off** post-migration refreshes (AH v3 / ERD v2 / STTM v3) — no content re-approval needed, the @data-architect gate was PASSED in the "AH/ERD/STTM Post-Migration Refresh + Re-Sign-off" entry above. |
| @data-architect | ✅ (pre-existing gate) | Approval gate on AH.md / ERD.md / STTM.md before re-publish (per `CLAUDE.md`) was already PASSED in the "AH/ERD/STTM Post-Migration Refresh + Re-Sign-off" entry above — this re-publish was the mechanical execution of that approved decision, not a new ruling. |

**What was published (version bumps)**:
- **AH** (`docs/architecture_handbook/AH.md` v3.0) → page id **131460**, version **v2 → v3**. URL: https://luqman10.atlassian.net/wiki/spaces/NSL/pages/131460
- **ERD** (`docs/erwin/ERD.md` v2.0) → page id **98553**, version **v1 → v2**. URL: https://luqman10.atlassian.net/wiki/spaces/NSL/pages/98553
- **STTM** (`docs/sttm/STTM.md` v3.0) → page id **98534**, version **v2 → v3**. URL: https://luqman10.atlassian.net/wiki/spaces/NSL/pages/98534

**Outcome**: This re-publish **supersedes the stale 2026-06-18 versions** (AH v2, ERD v1, STTM v2), which described ADR-005 as "approved but NOT migrated" / DuckDB-local as the as-built target — no longer true after the real S3-canonical migration went live on AWS this session (run_id `run-20260619-045115`). The staleness gap between as-built reality and the published Confluence record is now **CLOSED** — all three Lead Deliverables in Confluence space NSL reflect the as-built MIGRATED state (S3-canonical storage, DuckDB httpfs compute, Snowflake external-table serving veneer). This entry is mechanical execution of the existing @data-architect GO — no new ruling issued.

---

## Track-I Troubleshooting Library — Layers 04/05/06 Drill-Ready Clearance (C3, ADR-006-A1)
**Date**: 2026-06-19
**Status**: APPROVED (DA sign-off, conditional clearance on layer 05)

| Agent | Status | Reason |
|-------|--------|--------|
| @senior-data-engineer | ✅ | Independently re-verified the provisioned MinIO loop (did not trust the orchestrator's summary): confirmed `gym-minio` container creds match `gym.env` (mang/mangmang), re-ran `scripts/gym_guard.py` themselves, independently queried `gold/_current/` via DuckDB+httpfs and cross-checked row counts (dim_drug=133654, fact_sales=16848, fact_review=215063 — exact match), re-read the T-XFM-02/03 and `publish_gold.py` citation lines to confirm cards are mechanically true, and confirmed GE's read path has no caching layer (so "stale validation" is structurally impossible). Verdict: layers 04 + 06 READY to L10; layer 05 READY WITH CAVEAT — L-SNO-03 (Snowflake `ALTER EXTERNAL TABLE ... REFRESH` stale-metadata semantics) cannot be reproduced against MinIO/DuckDB ("not a gym gap, it's a physics-of-MinIO gap"). |
| @data-architect | ✅ | C3 (ADR-006-A1 §1-2 mechanism-proof bar) satisfied: a real pipeline run (seed→`load_bronze.py`→`dbt build` PASS=63/WARN=1/ERROR=0→`publish_gold.py`verify-then-copy→`run_ge_validation.py` OVERALL:PASS) executed against local MinIO `gym-lake`, independently re-verified by @senior-data-engineer. Required an ADR-006-A1 addendum (added) documenting the L-SNO-03 permanent cap as an accepted substrate limit, not a pending gap. No veto. |

**What changed**:
- `cheatsheets/troubleshooting/04_transformation.md` — STRUCTURE-ONLY → **DRILL-READY** (6 cards, drill-ready to L10).
- `cheatsheets/troubleshooting/06_data_validation.md` — STRUCTURE-ONLY → **DRILL-READY** (5 cards, drill-ready to L10).
- `cheatsheets/troubleshooting/05_load_snowflake.md` — STRUCTURE-ONLY → **DRILL-READY, 1 caveat** (L-SNO-01/02/04/05 to L10; L-SNO-03 capped below L5 permanently).
- `cheatsheets/troubleshooting/00_INDEX.md` — phase map table updated to reflect all three clearances.
- `docs/ADR/ADR-006-A1-incubator-fidelity-amendment.md` — new "Consequences" entry (permanent fidelity boundary on L-SNO-03) + new "C3 clearance (2026-06-19)" section recording the binding verdict.
- Infra: local `gym-minio` Docker container recreated (fresh anonymous volume, creds aligned to `gym.env`'s `mang`/`mangmang`) to fix a stale-credential mismatch from an earlier session; bucket `gym-lake` recreated; full pipeline run committed nothing to prod (incubator-isolated per ADR-006-A1).

**Outcome**: Troubleshooting library is now **22 cards across 4 drill-ready phases** (03 pilot + 04/05/06 cleared). Remaining phases 01 (triage), 02 (orchestration/logs), 07 (CI/CD audit), 08 (post-mortem/recovery) are the next build batch — not yet started. `CLAUDE.md` Track-I status line still owed an update to reflect this clearance (governance follow-up from DA verdict).

---

## Track-I Troubleshooting Library — Final 4 Phases Built (01/02/07/08, C2, ADR-006/ADR-006-A1)
**Date**: 2026-06-20
**Status**: APPROVED (C2 content gate — STRUCTURE-ONLY, not yet drill-ready)

| Agent | Status | Reason |
|-------|--------|--------|
| @senior-data-engineer | ✅ | Independently re-read every cited source file in all 4 new files (the DAG, `dbt_project.yml`, `s3_paths.sql`, `run_ge_validation.py`, `run_pipeline_aws.sh`, `load_bronze.py`, `seed_landing_to_s3.py`, `OPS_RUNBOOK.md`, `ci.yml`, `parse_test_mwaa.sh`, `DQD.md`, `publish_gold.py`) rather than trusting the orchestrator's summary. Confirmed the headline finding (`O-AIR-01`: the DAG never calls `publish_gold.py` and never threads `run_id`, so every orchestrated run writes Gold to a constant `gold/dev/` the Snowflake veneer never reads) is TRUE, not overstated — verified via a repo-wide grep that `run_pipeline_aws.sh:35` is the ONLY `publish_gold.py` call site anywhere. Also independently confirmed two corrections to stale `docs/OPS_RUNBOOK.md` lines (the `latest_dir()` fallback actually lives in `seed_landing_to_s3.py`, not `load_bronze.py`; bronze writes are `COPY...TO` parquet, not `CREATE OR REPLACE TABLE`) and confirmed zero Spark/executor/shuffle leakage across all 24 new cards. Verdict: APPROVE all 4 files, every citation exact. |
| @data-architect | ✅ | Re-derived `O-AIR-01` independently from source (did not take senior-DE's check on faith) and confirmed it. Ruled the C2 bar (ADR-006 Decision 1 + ADR-006-A1 §2) is a content/citation-discipline gate, not a "MinIO rep must already exist" gate — all 4 files are honestly self-tagged `[STRUCTURE-ONLY]` and satisfy it. Ruled `O-AIR-01` is a real production-documentation gap (not a gym/ADR governance matter) and required it be disclosed in `docs/OPS_RUNBOOK.md` directly, separate from the cheatsheet, citing ADR-006 §3's TRUTH-artifact boundary (`@incident-responder` reads operational docs as evidence but the runbook is the operational source of record). No ADR amendment required — this is documentation hygiene, not a gym-mechanism decision. |

**What changed**:
- `cheatsheets/troubleshooting/01_triage_blast_radius.md` — new, 6 cards, STRUCTURE-ONLY.
- `cheatsheets/troubleshooting/02_orchestration_airflow.md` — new, 6 cards, STRUCTURE-ONLY (carries the `O-AIR-01` headline finding + the binding CloudWatch/DuckDB-traceback-not-Spark-UI framing).
- `cheatsheets/troubleshooting/07_cicd_github.md` — new, 6 cards, STRUCTURE-ONLY.
- `cheatsheets/troubleshooting/08_postmortem_recovery.md` — new, 6 cards, STRUCTURE-ONLY.
- `cheatsheets/troubleshooting/00_INDEX.md` — phase map + tallies updated to 46 cards across all 8 phases; Top Junior Mistakes table extended with 4 new cross-phase entries.
- `docs/OPS_RUNBOOK.md` — new "Known Gaps" section disclosing `O-AIR-01` (DAG never publishes Gold to `_current`) as as-built production behavior, per DA requirement.
- `CLAUDE.md` Track-I status line — updated (see below).

**Outcome**: Troubleshooting library checklist is now **complete — 46 cards across all 8 phases** (03/04/05/06 drill-ready per the prior clearance; 01/02/07/08 STRUCTURE-ONLY, pending their own MinIO reps before C3 grading — same bar 04/05/06 already cleared). No ADR amendment issued. The DAG's missing Gold-publish step (`O-AIR-01`) is now documented in both the cheatsheet and the operational runbook; patching the DAG itself is a separate, not-yet-proposed build decision.

---

## Track-I Troubleshooting Library — Final 4 Phases Drill-Ready Clearance (C3, ADR-006-A1) — All 8 Phases Now C3

**Date**: 2026-06-20
**Status**: APPROVED (DA sign-off, no veto)

| Agent | Status | Reason |
|-------|--------|--------|
| @senior-data-engineer | ✅ | Independently re-verified, not on faith: re-ran the `O-AIR-07` reproduction from a cold shell (exact `Catalog Error` text match), re-ran `scripts/parse_test_mwaa.sh` to confirm it stays green regardless (confirms no gate anywhere catches this), independently queried real bronze data and confirmed the 1,317 `(product_ndc, marketing_start_date)` tie-group / 2,972-row count behind `P-PMR-07`, independently re-executed the `P-PMR-03` rollback rep, and independently re-reproduced `T-TRI-02`. Flagged one non-defect note (checked, not assumed): the `snapshot_s3_roundtrip.sql` hook persists the snapshot table across `dbt build`/`dbt snapshot` invocations specifically, but does not solve the upstream `stg_beta__ndc` view's loss across a process boundary — `O-AIR-07`'s root-cause text does not overclaim on this point. Verdict: PASS, no soft veto. |
| @data-architect | ✅ | Re-derived the C3 bar (ADR-006-A1 §1-2 — "the cited file:line guards behave as described against real S3-compatible storage, not just read as source") independently against all 4 files, not from the senior-DE summary. All 4 show genuine execution evidence, the same evidentiary shape that cleared 04/05/06 on 2026-06-19: 01's stale-date rep prints literal wrong S3 keys; 02 reproduces the exact `Catalog Error` text from two real per-task subprocess invocations and confirms the parse gate's blind spot live; 07 actually runs all 5 `ci.yml` steps locally (incidentally surfacing 2 real pre-existing `ruff` findings unrelated to this session — proof the lint gate isn't theater); 08 runs two real Gold publishes, a live rollback, and a live `dim_drug` row-count diff (133,654→133,758). **Bar satisfied for all 4 — 01/02/07/08 now DRILL-READY (C3), same as 04/05/06.** Ruled `O-AIR-07` and `P-PMR-07` are real production-pipeline defects discovered *by* the gym, not facts *about* the gym's own mechanics — applying the identical standard used for `O-AIR-01` (OPS_RUNBOOK disclosure, no addendum) and distinguishing it from `L-SNO-03` (which DID need the ADR-006-A1 addendum because it changed a permanent grading cap / incubator-fidelity boundary). Neither new finding touches ADR-006-A1's mechanism, grading rubric, or any fidelity boundary — **no ADR amendment**. Ruled `T-XFM-05`'s in-place correction in the already-C3-cleared `04_transformation.md` is sufficient as written: it narrows the claim honestly ("checked for ONE model, not audited codebase-wide") without overclaiming a fix, and the original card's mechanism-proof (the crosswalk's own guard, at its own file:line) was never about a codebase-wide audit — **04's C3 status is not reopened**. No veto. |

**What changed**:
- `cheatsheets/troubleshooting/01_triage_blast_radius.md` — STRUCTURE-ONLY → **DRILL-READY** (7 cards; `T-TRI-02` reproduced live, `T-TRI-05` corrected in place + new `T-TRI-07`).
- `cheatsheets/troubleshooting/02_orchestration_airflow.md` — STRUCTURE-ONLY → **DRILL-READY** (7 cards; new headline finding `O-AIR-07`, `O-AIR-01`/`O-AIR-03` corrected in place).
- `cheatsheets/troubleshooting/07_cicd_github.md` — STRUCTURE-ONLY → **DRILL-READY** (6 cards; `C-CICD-02` deepened with a live finding — even the real MWAA parse gate misses `O-AIR-07`).
- `cheatsheets/troubleshooting/08_postmortem_recovery.md` — STRUCTURE-ONLY → **DRILL-READY** (7 cards; new headline finding `P-PMR-07`, rollback mechanism in `P-PMR-03` reproduced live).
- `cheatsheets/troubleshooting/04_transformation.md` — `T-XFM-05` corrected in place (narrowed claim, cross-references `P-PMR-07`); C3 status unchanged.
- `cheatsheets/troubleshooting/00_INDEX.md` — phase map updated to all 8 phases DRILL-READY (C3), 51 cards total; headline-findings section and Top Junior Mistakes table extended.
- `docs/OPS_RUNBOOK.md` Known Gaps — two new entries (`O-AIR-07`, `P-PMR-07`) placed ahead of/superseding the prior `O-AIR-01` entry.
- No ADR amendment. `CLAUDE.md` Track-I status line update owed (governance follow-up, out of scope for @data-architect this entry — separate role).

**Outcome**: Troubleshooting library is now **51 cards, all 8 phases DRILL-READY (C3)** — the checklist is both structurally complete and mechanism-proven end to end, with the sole permanent exception carried over from the prior clearance (`L-SNO-03`, capped below L5, ADR-006-A1 Consequences). Two real, previously-unknown production-pipeline defects were found by the gym mechanism working as designed (`O-AIR-07` — the orchestrated DAG cannot complete a single real run, supersedes `O-AIR-01` as today's first symptom; `P-PMR-07` — `stg_beta__ndc` reruns are not idempotent) — both disclosed in `docs/OPS_RUNBOOK.md` per the same documentation-hygiene standard applied to `O-AIR-01`, no ADR amendment required. `T-XFM-05`'s in-place narrowing is accepted as sufficient; `04_transformation.md` keeps its C3 status unchanged.

---

## ADR-007 — Parallel Spark + Delta DEMONSTRATION track (Round-2 synthesis ruling)

**Date**: 2026-06-20
**Status**: APPROVED WITH BINDING CONDITIONS (ADR-007 GO — B1–B9 binding/testable; ADR-005 boundary reaffirmed, NOT amended)

| Agent | Status | Reason |
|-------|--------|--------|
| @senior-data-engineer | ✅ (Round 1 — feasibility) | FEASIBLE WITH CHANGES. Soft-veto conditions: pin Java 21 + the Spark 3.5.x/hadoop-aws 3.3.4/aws-java-sdk-bundle 1.12.262/delta-spark 3.2.x matrix in `requirements-spark.txt`; CORRECT the `O-AIR-07` framing (SCD2 snapshot already survives task boundaries via `snapshot_s3_roundtrip.sql` on-run hooks — the ONLY failure is `marts.core`/`dim_drug` reading the staging VIEW; external-materializing staging via `silver_location()` IS the whole fix, snapshot needs nothing); `P-PMR-07` is a trivial tie-break copy from `int_drug_crosswalk`. `local[*]` must not be over-claimed (no real shuffle/executor-recovery/dynamic-allocation). All folded into B1, B2, B9. |
| @data-platform-engineer | ✅ (Round 1 — infra) | GREEN WITH CONDITIONS. C1 (HARD GATE): existing `gym_guard.py` inspects DuckDB-httpfs env vars but NOT Spark's `spark.hadoop.fs.s3a.*` client — a Spark drill could be guard-green and still mutate the live lake; MUST build `spark_gym_guard.py` + a single `spark_session_factory()`, NO raw `SparkSession.builder`. C2: separate owner-gated staging bucket w/ region-lock+PAB+versioning+30d+short-TTL. C3: DAG via `spark-submit` subprocess, pass `parse_test_mwaa.sh`, no O-AIR-07 trap. C4: extend `ci.yml`. C5: Slack env-only + wire to the EXISTING DuckDB DAG. Over-engineering watch: no unused Glue IaC, reuse `gym-minio` for drills, Step Functions out of scope. C1→B3, C2→B4, C3→B5, C4→B6, C5→B7. |
| @data-architect | ✅ (Round 2 — SYNTHESIS RULING, veto holder) | Re-derived the core question from ADR-005 directly (read §4 + Alternative #1 + CLAUDE.md stack table), did NOT take Round-1 verdicts on faith. RULED: a `local[*]`, Glue-ready, never-paid-compute Spark+Delta track **EXTENDS** ADR-005's hybrid/cost-discipline principle and does NOT violate its boundary — ADR-005 rejected Glue **as a production/deploy compute path** (§4, Alt #1), and `local[*]`-only Spark is the SAME category as the already-blessed `aws-mwaa-local-runner` (demonstrate a managed AWS service via a local runner, never provision the paid service). ADR-005's Glue rejection is **reaffirmed, not amended**. Stated the controlling **5-part demonstration-fence** (additive/never-substitutive · never paid compute · mechanically guard-isolated · derives-from-never-becomes the governed star · honestly scoped) so this cannot be cited to justify arbitrary future tool additions. Ruled a NEW ADR-007 is required (new decision admitting a fenced non-production track — NOT an ADR-005 amendment since the production stack is unchanged, NOT an ADR-006 amendment since it is not a gym-mechanism change). Adopted senior-DE's O-AIR-07 reframe as binding (B1) and confirmed the data-model/lineage implication: materialized Silver-on-S3 is already required by ADR-005 Condition B — not a new layer. Made B3 (`spark_gym_guard`) the LOAD-BEARING gate (it re-opens the exact fail-open hole ADR-006-A1 §1 closed). Added DA-owned two-engine consistency governance (B8): DuckDB+S3 stays the SOLE system of record, Spark+Delta is a demonstration artifact never read by serving, reconciled per `<date>` against the DuckDB mart. No veto. |

**What changed**:
- `docs/ADR/ADR-007-spark-delta-demonstration-track.md` — NEW. The decision + the 5-part demonstration-fence principle + binding conditions B1–B9 (each names its proof) + sequencing/sign-off chain.
- `SIGN_OFF_LOG.md` — this entry.
- NOT authored here (separate roles): the code (Fasa A fixes, `spark/`, guards, DAG, CI), and the `CLAUDE.md` stack-note update (governance follow-up owed).

**Outcome**: **ADR-007 GO, APPROVED WITH BINDING CONDITIONS.** The Spark+Delta track is admitted as a fenced, non-production, `local[*]`-only demonstration track. ADR-005's stack boundary is reaffirmed (Glue still rejected as production compute). Fasa A (`O-AIR-07` external-staging fix + `P-PMR-07` tie-break) sequences FIRST with the corrected, cheaper framing. The Spark track runs NO sabotage drill until `spark_gym_guard.py` (B3) is proven fail-closed against real S3-compatible storage and independently re-verified by @senior-data-engineer — the same C3 bar that cleared Track-I layers 04/05/06. Two-engine divergence is a defect to investigate, never an accepted fork (B8).

---

## Fasa A closure — O-AIR-07 + P-PMR-07 production defect fixes

**Date**: 2026-06-20
**Status**: APPROVED (DA ratification of independent re-verification, no veto)

| Agent | Status | Reason |
|-------|--------|--------|
| @senior-data-engineer | ✅ | Independently re-verified against the local MinIO `gym-lake` incubator (never the live AWS bucket), own run_id tags, not trusting the orchestrating session's numbers. **O-AIR-07**: re-ran all 6 dbt steps (`seed`→`run -s staging`→`snapshot`→`run -s marts.core`→`run -s marts.serving`→`test`) as genuinely separate subprocesses, fresh `:memory:` catalog each time — all exit 0, final `dbt test` PASS=54 WARN=1 ERROR=0 (the one warn is the known/accepted `not_null_stg_beta__ndc_generic_name` OTC case). Read-verified `register_external_upstreams()` actually recurses through the ephemeral `int_drug_crosswalk` node to register external `stg_beta__ndc` (not a degenerate direct-dependency case), and confirmed the load/export WHICH-gate asymmetry fires correctly live (seed/snapshot reload firing under `run` and `test`, never silently re-exporting on a bare run). **P-PMR-07**: two fresh full `dbt build` reps, same byte-identical bronze input, `dim_drug` = 133,654 / 133,654 — equal, no growth to 133,758; `snap_beta_ndc` clean (no spurious open/close history) despite 3 snapshot invocations across both checks. Flagged one residual gap: the tie-break order-by omitted `load_ts` (selected but not ordered on); checked `scripts/load_bronze.py:43-70` and confirmed `load_ts` is `current_timestamp` evaluated once per bronze-load query (constant across all rows in one load, so today's risk is zero) but not structurally guaranteed against a future per-row-timestamp ingestion refactor — recommended adding it to the order-by now while free. Verdict: PASS both, no soft veto. |
| @data-architect | ✅ | Re-read the as-built artifacts directly (`stg_beta__ndc.sql`, `register_external.sql`, `dbt_project.yml`), not just the senior-DE summary — confirmed the code matches the verdict. Ratified both fixes CLOSED per this project's standing bar (DA ratifies an independent re-verification; does not re-execute). Ratified the orchestrating session's follow-up patch (added `load_ts desc nulls last` to the tie-break, applied after senior-DE's review, re-run once locally as `dbt run -s stg_beta__ndc` PASS=6 ERROR=0 but not re-submitted through a fresh senior-DE loop) as in-scope of this same closure — additive, currently a no-op given `load_ts`'s per-load-constant nature, so it doesn't reopen the proven invariant. **No ADR amendment for either fix**: O-AIR-07 *implements* ADR-005 Condition C / ADR-007 B1 (mechanism those ADRs already anticipated, not a new decision); P-PMR-07 is a pure idempotency bug-fix, same class already hardened in `int_drug_crosswalk.sql`. Documentation hygiene only, consistent with the `O-AIR-01` precedent. No veto. |

**What changed**:
- `dbt/dbt_project.yml`, `dbt/macros/register_external.sql` (new), `dbt/macros/seed_s3_roundtrip.sql` (new), `dbt/macros/snapshot_s3_roundtrip.sql` — O-AIR-07 fix (staging `view`→`external`, transitive external-upstream registration through ephemeral nodes, seed/snapshot S3-roundtrip load gates extended to `run`/`test`).
- `airflow/dags/pharma_sttm_pipeline.py` — new `dbt_seed()` task upstream of `dbt_enrich()`.
- `dbt/models/staging/beta/stg_beta__ndc.sql` — P-PMR-07 fix (fully deterministic secondary tie-break on the dedup `row_number()`, including `load_ts`).
- `docs/OPS_RUNBOOK.md` Known Gaps — the `O-AIR-07` and `P-PMR-07` bullets replaced with a single RESOLVED note; the `gold/_current` publish gap's back-reference updated from "becomes live once fixed" to "is now LIVE — next pickup."
- `SIGN_OFF_LOG.md` — this entry.

**Outcome**: **Fasa A CLOSED.** Both production defects found by the troubleshooting-library gym mechanism are now fixed in the working tree and independently re-verified end-to-end against `gym-lake` (zero contact with the live AWS bucket). The orchestrated DAG can complete a real run for the first time; `stg_beta__ndc` reruns are now a safe no-op. No ADR amendment. Next gap in line: `gold/_current` is never published by the DAG (now live since O-AIR-07 no longer blocks reaching it) — separate, not-yet-proposed build decision. ADR-007's Spark+Delta track is now unblocked to begin per its sequencing (Fasa A was its hard prerequisite).

---

## O-AIR-01 closure — DAG Gold publish wiring

**Date**: 2026-06-21
**Status**: APPROVED (no veto)

| Agent | Status | Reason |
|-------|--------|--------|
| @senior-data-engineer | ✅ | Independently re-verified: `py_compile` clean on `airflow/dags/pharma_sttm_pipeline.py`. Ran the REAL MWAA parse gate (`scripts/parse_test_mwaa.sh` against genuine Airflow 2.10.3 via `aws-mwaa-local-runner`, image already cached) — `IMPORT_ERRORS: {}`, exit 0, `pharma_sttm_pipeline_v1` parses clean. Ran a full independent rep against the local MinIO `gym-lake` incubator with a fresh run_id (`run-sdeverify20260621a`, distinct from every prior session's run_id) covering the DAG's exact task sequence: `seed`→`run -s staging`→`snapshot` (no-op, no new SCD2 deltas)→`run -s marts.core`→`run -s marts.serving`→`dbt test` (PASS=54 WARN=1 ERROR=0, the warn is the known pre-existing soft-warn, not a regression)→`publish_gold.py --run-id` (all 7 Gold objects verified+copied)→`run_ge_validation.py` (OVERALL: PASS, all 3 suites green). Cross-checked `gold/_current/` counts against the run-scoped prefix directly — exact match, including the correct un-inflated `dim_drug`=133,654 (confirmed the P-PMR-07 regression count of 133,758 is NOT present). Re-ran `publish_gold.py` with the same run_id again afterward — idempotent, no errors. Independently confirmed (by reading `scripts/run_ge_validation.py` source, not trusting the implementer's code comment) that the `dbt_test`→`publish_gold`→`dq_validate` task reordering is correct: `gold_current()` has no run_id override, so GE must run after the pointer swap or it silently re-validates the prior run's data forever; `dbt test` running pre-publish against `gold/<run_id>/` is also correct since dbt's generic tests query the run-scoped external tables directly, not a cache. Flagged two non-blocking risks: (1) `publish_gold.py`'s copy loop has no rollback/atomicity across the 7 objects if it dies mid-loop; (2) `gold/<run_id>/` prefixes accumulate with no retention policy. Verdict: ship-it, no soft veto. |
| @data-architect | ✅ | Read the diff and `scripts/publish_gold.py` directly, not just the senior-DE summary, for the architectural read. Confirmed this implements ADR-005 Decision 1 mechanism (B) exactly as already specified — `dbt/macros/s3_paths.sql`'s `var('run_id', 'dev')` convention pre-existed; the DAG was simply never wired to invoke it. No new pattern, no ADR amendment. The `dbt_test`→`publish_gold`→`dq_validate` reordering is correct and not optional, for the same reason the senior-DE independently found. Both flagged risks ACCEPTED as documented-but-not-blocking: per-model publish independence (a network blip mid-loop degrades but never corrupts any single model's `_current/` object) is the deliberate ADR-005 Decision 1 design, not an oversight, and is further mitigated in practice by Airflow's `retries=2` plus confirmed-idempotent re-publish; `gold/<run_id>/` retention is explicitly out of scope for a portfolio gym and already flagged as a FinOps watch item in ADR-005. No veto. |

**What changed**:
- `airflow/dags/pharma_sttm_pipeline.py` — added `gold_run_id(ts_nodash)` helper (one shared `run_id` per DAG run, derived from the logical timestamp, no XCom); threaded `--vars '{"run_id": ...}'` through every `dbt(...)` call; split the old combined `dq_checks()` task into `dbt_test` (against unpublished `gold/<run_id>/`) → `publish_gold` (`scripts/publish_gold.py --run-id`) → `dq_validate` (`scripts/run_ge_validation.py` against `gold/_current/` only).
- `docs/OPS_RUNBOOK.md` Known Gaps — the `gold/_current` publish-gap bullet replaced with a RESOLVED note.
- `SIGN_OFF_LOG.md` — this entry.

**Outcome**: **O-AIR-01 CLOSED.** No ADR amendment. The orchestrated DAG now publishes every run's Gold output to `gold/_current/`, the prefix Snowflake serving and GE validation actually read — closing the last open gap from the 2026-06-20 troubleshooting-library reps. Fasa A's full defect list (O-AIR-07, P-PMR-07, O-AIR-01) is now entirely closed. ADR-007's Spark+Delta track build (B2 onward) is unblocked to proceed.
