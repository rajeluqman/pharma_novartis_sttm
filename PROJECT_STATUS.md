# PROJECT_STATUS.md
**Last updated**: 2026-06-22 (full backfill of the 2026-06-20→2026-06-21 sessions — Track I
incident-response library, ADR-007 Spark+Delta demonstration track, the `O-AIR-01` gold-publish fix —
now caught up; previous header's "still owed" backfill is closed out by this edit)
**Current phase**: Phase 5 — Quality + Docs complete, cabinet-reviewed. **ADR-005 (S3-canonical
storage pivot) MIGRATED & LIVE on real AWS as of 2026-06-19** (run_id `run-20260619-045115`) —
S3-canonical storage + DuckDB httpfs compute + Snowflake external-table serving veneer, verified
end-to-end (dbt 63 PASS/1 WARN/0 ERROR, GE PASS, KPIs identical to baseline). AH/ERD/STTM
re-published to Confluence reflecting the as-built migrated state. **Repo flipped PRIVATE on
2026-06-21** (owner-driven). MWAA orchestration still **not** stood up — remaining wrap-up only.

**2026-06-20 — Fasa A CLOSED, now committed**: `O-AIR-07` (orchestrated DAG could never complete a
run across per-task `:memory:` subprocess boundaries) and `P-PMR-07` (`stg_beta__ndc` dedup
non-idempotent, inflated `dim_drug` 133,654→133,758 on rerun) both fixed and independently
re-verified by @senior-data-engineer + ratified by @data-architect against the local MinIO
`gym-lake` incubator (zero contact with the live AWS bucket) — see `SIGN_OFF_LOG.md` "Fasa A
closure" entry and `docs/OPS_RUNBOOK.md` Known Gaps. No ADR amendment. Committed `c0ad879`. This was
ADR-007's (Spark+Delta demonstration track) hard sequencing prerequisite — now unblocked.

**2026-06-21 — `O-AIR-01` CLOSED** (the real gap this status doc's "Next Step" had flagged as
unaddressed): `pharma_sttm_pipeline.py` now threads one `run_id` through every `dbt(...)` subprocess
call and splits the old combined `dq_checks()` task into `dbt_test → publish_gold → dq_validate`, so
each orchestrated run's Gold output is verify-then-copied into `gold/_current/` *before* GE reads it.
Previously every MWAA/local-runner run silently wrote to the fixed `gold/dev/` prefix that nothing
downstream — Snowflake veneer or GE — ever read. Committed `e722973`.

**2026-06-19/20 — Track I (Incident-Response Gym, ADR-006/ADR-006-A1) fully built and DA-signed-off**:
all 8 phases (`cheatsheets/troubleshooting/00_INDEX.md` + `01_triage_blast_radius` →
`08_postmortem_recovery`), 51 cards total, every phase independently re-verified against the real
`gym-lake` MinIO incubator by @senior-data-engineer then @data-architect — checklist is both
structurally complete and mechanism-proven (not just scaffolded). The reps surfaced `O-AIR-07` and
`P-PMR-07` above, plus the substrate-limit cap on `L-SNO-03` (Snowflake `REFRESH` staleness can't be
reproduced on MinIO — permanent, accepted, codified in ADR-006-A1). Committed `7d5f0fa`.

**2026-06-20/21 — Track S (ADR-007, Spark+Delta DEMONSTRATION track) fully closed, B1–B9, including
the one real AWS run**: fenced `local[*]`-only PySpark+Delta reading `gold/_current/` read-only and
writing to its own staging bucket (`novartis-pharma-sttm-spark-staging`), gated by
`spark_gym_guard.py` (drill-mode MinIO + new demo-mode real-AWS branch), CI-gated, reconciled
exact-match against DuckDB on all 5 star models (dim_date 4383, dim_condition 836, dim_drug 133654,
fact_sales 16848, fact_review 215063). Cabinet-reviewed (DPE → senior-DE → DA) at every gate with zero
outstanding findings. See `SIGN_OFF_LOG.md` "ADR-007" entries and `docs/ADR/
ADR-007-spark-delta-demonstration-track.md`. Commits `938ce34`, `320e6ba`, `4ce9a0e`, `edbd568`,
`cf9810f` — **all pushed to `origin/main`** (verified 2026-06-22, local `main` and `origin/main` are
identical, nothing unpushed).

**Housekeeping note (2026-06-22)**: a stale local branch `feature/adr-005-p5-mwaa-parse-gate`
(commit `1728a47`, the SLA-gym L3/L5/L8 self-play work) predates a history rewrite/squash and shares
no merge-base with `main` — but its file contents are byte-identical to what's already on `main`
(folded into the squashed initial commit `e9d9102`). No work was lost; the branch is fully superseded
and safe to delete whenever convenient.

## Phase Overview
| Phase | Name | Status |
|-------|------|--------|
| 1 | Discovery | ✅ (brief + JD mapping) |
| 2 | Exploration | 🔄 (datasets chosen; profiled implicitly during build — see Done) |
| 3 | Design | ✅ (ADR-001/002/003/004/005, DATA_MODEL, ARCHITECTURE) |
| 4 | Build | ✅ (dev/DuckDB target: bronze→enrich→marts→serving, all tests green, cabinet-reviewed) |
| 5 | Quality + Docs | ✅ (DQD/OPS_RUNBOOK/README/INTERVIEW_GUIDE — CLAUDE.md's narrow scope); ✅ AH.md/ERD.md/STTM.md all @data-architect-signed-off + Confluence-published, **re-published 2026-06-19 post-migration** (AH page 131460 v3, ERD page 98553 v2, STTM page 98534 v3) — all 3 Lead Deliverables live and current, Confluence publish workstream fully CLOSED |
| — | **ADR-005 S3-canonical migration** | ✅ **DONE & LIVE on real AWS (2026-06-19)** — S3 + DuckDB-httpfs compute + Snowflake external-table veneer; see Done ✅ below |

## Done ✅
- [x] PROJECT_BRIEF reframed: 3 real sources, JD weighting 40/30/20/10, 4-tier topology
- [x] Stack: HYBRID (mwaa-local-runner dev → MWAA+Snowflake artifact); .env.example + CLAUDE.md updated
- [x] ADR-001 (star+OBT), ADR-002 (4-tier landing), ADR-003 (conformed dim_drug crosswalk), ADR-004 (Snowflake least-privilege RBAC)
- [x] DATA_MODEL + ARCHITECTURE filled
- [x] `.env` fully populated; **all creds verified live 2026-06-18**:
  - AWS: `aws sts get-caller-identity` OK (account 579880301047)
  - Kaggle: `kaggle datasets list` OK
  - Snowflake: role/warehouse/database (`NOVARTIS_STTM_ROLE`/`_WH`/`_DB`) did **not** exist in the
    trial account — provisioned via `scripts/setup_snowflake.sql`, then re-provisioned with
    least-privilege grants after @data-architect's veto (ADR-004). `dbt debug --target prod` OK
    both before and after the grant correction. Re-run that script if the trial account is ever
    recreated.
- [x] Landed all 3 sources (`data/landing/{alpha,beta,gamma}/2026-06-18/`):
  - Alpha: Kaggle `milanzdravkovic/pharma-sales-data` (salesdaily/hourly/weekly/monthly CSVs)
  - Beta: openFDA NDC directory — switched ingest script to the **bulk zip** (136,038 products,
    not the 1,000-row API page) for better crosswalk match odds; `scripts/ingest_beta_ndc.py`
  - Gamma: Kaggle `jessicali9530/kuc-hackathon-winter-2018` (215,063 reviews, train+test)
- [x] `scripts/load_bronze.py` — landing → DuckDB `bronze` schema (no cleaning, +load_ts/source_file)
- [x] Enrich (staging) built for all 3: `stg_alpha__sales` (unpivot 8 ATC cols), `stg_beta__ndc`
  (dedup on product_ndc, parse dates, flatten pharm_class array), `stg_gamma__reviews` (normalize
  drug name, null out scrape-artifact `condition` values, `dq_flag`/`dq_reason` audit columns)
- [x] `int_drug_crosswalk` — tiered match (exact/normalized/fuzzy/combination_unverified/unmatched)
  NDC↔ATC via seed, with word-boundary + length guards and combination-product handling
- [x] `dim_drug` SCD2 — real `dbt snapshot` (`snap_beta_ndc`, check strategy) + ATC category rows
  unioned in so `fact_sales` always has a join target (Alpha has no NDC-level grain);
  `drug_member_type` discriminator separates the two row types structurally
- [x] `dim_date` (date spine 2008–2019), `dim_condition`, `fact_sales`, `fact_review` all built
- [x] `obt_sales_wide`, `obt_review_wide` (RRD serving layer)
- [x] 50 dbt tests (not_null/unique/relationships/accepted_range/accepted_values + 1 singular row-count
  test) — 49 pass, 1 documented `warn` (3 NDC products with brand_name but no generic_name — real, not a bug)
- [x] Full `dbt build` reproducible from a dropped warehouse file: bronze load → seed → run
  staging → snapshot → run (rest) → test, all green
- [x] `docs/sttm/STTM.md` filled to v1.1 — every Enrich/Mart/RRD column mapped, both crosswalk
  coverage KPIs measured, reported separately (seed-reach vs. match-quality), and recorded
- [x] **Retroactive Phase 4 cabinet review held** (`docs/DEBATE_LOG_phase_4.md`) — 4 independent
  reviewer agents (data-architect, business-analyst, data-quality-steward, scope-guardian), real
  findings not rubber stamps: 2 hard vetoes (Snowflake RBAC over-grant; undocumented reactive cloud
  provisioning) + 2 soft vetoes (crosswalk testability gaps; missing DQ artifacts). **All four
  resolved same session** — see Decisions Made and SIGN_OFF_LOG.md Phase 4 entry.
- [x] `docs/DATA_DICTIONARY.md` and `docs/DQD.md` filled (were templates despite Gold being built —
  flagged by @data-quality-steward); fact_review.drug_sk SLA set at ≥65% (measured 71.9%),
  condition_sk at ≥90% (measured 98.9%)
- [x] Great Expectations suite populated under `data_quality/expectations/` (3 suites: dim_drug,
  fact_sales, fact_review — row counts + the new SLA thresholds), runnable via
  `scripts/run_ge_validation.py`, all passing
- [x] `DECISION_LOG.md` and `JOURNEY_LOG.md` backfilled with real Phase 4 entries (were templates)
- [x] **Phase 5 closed out** (current/pre-ADR-005 build):
  - `airflow/dags/pharma_sttm_pipeline.py` fully wired — every task shells out to real scripts/dbt commands (no more `...` stubs)
  - `@qa-engineer` local QA pass: `dbt test` re-run (50/50 unchanged), GE re-run (13/13), + 9 new integration tests (`tests/integration/test_pipeline_reconciliation.py`) — independently re-verified live, 9/9 pass
  - `docs/OPS_RUNBOOK.md` filled (monitoring endpoints, alert SLA mapping, 4 playbook scenarios, backfill procedure, session checklists)
  - `docs/INTERVIEW_GUIDE.md` drafted (`@cikgu`) and honesty-checked (`@business-analyst`) — every number/claim cross-verified against source logs, APPROVED
  - `README.md` filled from real build evidence (re-verified live KPIs, honest Business Questions status per G1-G4/D1-D2/M1-M2/S1)
  - ADR-005's then-pending `@data-platform-engineer` sign-off closed: APPROVED-WITH-AMENDED-CONDITIONS (P1 tightened — pointer-swap atomicity mechanism specified; P5 added — Airflow version-pin gate sequenced before any MWAA step). Migration itself **not started**.
- [x] All three Phase 4→5 hard blockers resolved, conditionally, conditions documented (not hidden) — see `SIGN_OFF_LOG.md` Phase 5 entry
- [x] **`docs/architecture_handbook/AH.md` (v1.0) and `docs/erwin/ERD.md` (v1.0) filled** —
  Documentation Governance (D1) and Data-Model Governance (M1), ~50% combined JD weight. @data-architect
  convened *before* the fill (R1–R8 ruling memo), filled from real build evidence, then signed off on the
  drafts (all R1–R8 satisfied, 3 minor non-blocking notes). Both document the **as-built DuckDB pipeline**
  as normative with the ADR-005 S3-canonical target clearly fenced as approved-but-not-migrated. See
  `SIGN_OFF_LOG.md` "Lead Deliverables" entry.
- [x] **AH.md + ERD.md + STTM.md all published to Confluence** (2026-06-18) — @data-platform-engineer built
  `scripts/publish_to_confluence.py` (was specced, never built) and ran it under the existing
  @data-architect approvals. AH → updated page id 131460 (v1→v2); ERD → created page id 98553 (v1);
  STTM → updated page id 98534 (v1→v2, 11 tables landed clean), all space NSL, site
  luqman10.atlassian.net. Env key `CONFLUENCE_PAGE_ID_ERD=98553` persisted. **All three Lead
  Deliverables are now live in Confluence — the Confluence publish workstream is fully CLOSED.** See
  `SIGN_OFF_LOG.md` "Confluence Publish — AH + ERD" and "Confluence Publish — STTM" entries
- [x] **ADR-005 S3-canonical migration — MIGRATED & LIVE on real AWS (2026-06-19)**, run_id
  `run-20260619-045115`. Bucket `novartis-pharma-sttm-lake` (`ap-southeast-1`) created with
  versioning + 30-day noncurrent-version lifecycle + `aws:RequestedRegion` Deny + `landing/`
  write-once. Full pipeline run end-to-end on real S3: landing→bronze→silver→gold parquet via
  DuckDB httpfs; dbt `external` materialization; `snap_beta_ndc` snapshot externalized to
  `s3://.../snapshots/`; Gold published to `gold/<run_id>/` then promoted to `gold/_current/`. dbt
  build PASS=63/WARN=1/ERROR=0, Great Expectations PASS, KPIs identical to pre-migration baseline
  (`fact_review` 215,063, `dim_drug` 133,654, `fact_sales` 16,848, drug_sk 71.9%, condition_sk
  98.9%). See `docs/ADR/ADR-005-build-decisions.md` for the six build-decision rulings.
- [x] **Snowflake serving veneer LIVE** — `STORAGE INTEGRATION s3_gold_integration` + new scoped
  role `snowflake_gold_reader` (separate from `NOVARTIS_STTM_ROLE`, ADR-004 least-privilege
  preserved) + `gold_stage` pointed at `gold/_current/` + external tables `obt_sales_wide_ext`
  (16,848 rows) and `obt_review_wide_ext` (215,063 rows), both reading the same S3 Gold data
  directly — "warehouse over lakehouse" proven. Snowflake now holds **zero dbt-written tables**;
  it is a read-only external-table veneer only.
- [x] **AH/ERD/STTM re-published to Confluence post-migration** (2026-06-19) — @data-architect
  refreshed all three to as-built MIGRATED framing (logical model unchanged), then
  @data-platform-engineer re-ran `scripts/publish_to_confluence.py`: AH 131460 v2→v3, ERD 98553
  v1→v2, STTM 98534 v2→v3, space NSL. Supersedes the 2026-06-18 versions, which had gone stale the
  moment the migration went live. See `SIGN_OFF_LOG.md` "AH/ERD/STTM Post-Migration Refresh +
  Re-Sign-off" and "Confluence Re-Publish — AH/ERD/STTM Post-Migration" entries
- [x] **`README.md` refresh** — corrected all remaining pre-migration storage/compute/serving
  framing to the as-built S3-canonical + DuckDB-httpfs + Snowflake-external-table-veneer state; KPI
  and business-question content kept as-is (already honest).
- [x] **Track B seed — SLA-gym self-play (L3/L5/L8) + `@cikgu` handover** (2026-06-19) —
  `@senior-data-engineer` self-play solved L3 (`gym_l3_sequential_trap`), L5
  (`gym_l5_full_reload_trap`), L8 (`gym_l8_sensor_hang_trap`) as worked-example answer keys (all
  DagBag-parse clean); `docs/sla/SABOTAGE_LOG.md` + `docs/sla/SLA_ANALYSIS.md` populated;
  `learning/CURRICULUM.md` marks L3/L5/L8 as answer keys to re-derive, not skip to.
  `LEARNING_LOG.md` "HANDOVER TO CIKGU" entry closes the build→learn handover, score 100/100 (no
  hints spent). Owner's own L1 hands-on build is the one piece still open — see In Progress.
- [x] **`O-AIR-01` fixed** (2026-06-21) — `pharma_sttm_pipeline.py` now threads a shared `run_id`
  through every dbt subprocess call and publishes Gold to `gold/_current/` via
  verify-then-copy before GE validation runs, closing the gap where orchestrated runs silently
  wrote to an unread `gold/dev/` prefix. Committed `e722973`.
- [x] **Track I — Incident-Response Gym (ADR-006/ADR-006-A1) — all 8 phases DRILL-READY, 51
  cards** (2026-06-19/20) — `cheatsheets/troubleshooting/00_INDEX.md` through
  `08_postmortem_recovery.md`; fail-closed `gym_guard.py` incubator (MinIO `gym-lake`, never the
  live bucket); every phase independently re-verified via a real MinIO pipeline loop by
  @senior-data-engineer then ratified by @data-architect. Surfaced `O-AIR-07`/`P-PMR-07` (fixed,
  Fasa A) and the permanent `L-SNO-03` substrate-limit cap (Snowflake `REFRESH` staleness
  unreproducible on MinIO). Committed `7d5f0fa`.
- [x] **Track S — ADR-007 Spark+Delta DEMONSTRATION track — B1–B9 fully closed, including the one
  real AWS run** (2026-06-20/21) — fenced `local[*]`-only PySpark+Delta, reads `gold/_current/`
  read-only, writes to its own staging bucket (`novartis-pharma-sttm-spark-staging`) behind
  `spark_gym_guard.py`'s demo-mode branch, CI-gated, real run reconciled exact-match vs DuckDB on
  all 5 star models. Cabinet-reviewed at every gate (DPE → senior-DE → DA), zero outstanding
  findings. Commits `938ce34`/`320e6ba`/`4ce9a0e`/`edbd568`/`cf9810f`.

## Coverage KPIs (DQD, measured 2026-06-18, post-hardening)
| Metric | Result |
|--------|--------|
| Beta NDC products matched to an ATC code (seed reach, NOT match quality) | 4.1% (5,524/133,646) — expected: 8 seed categories vs full national catalog |
| Beta NDC products flagged as combination products | 7.3% (9,805/133,646) |
| fact_sales date_sk / drug_sk resolution | 100% / 100% (by design — atc_category rows) |
| fact_review date_sk resolution | 100% |
| fact_review drug_sk resolution (free-text match quality, independent of ATC seed) | 71.9% (154,641/215,063) — SLA floor ≥65% |
| fact_review condition_sk resolution | 98.9% (212,698/215,063) — target ≥90% |

## In Progress 🔄
- [ ] **Owner's own Track B hands-on build** — `@senior-data-engineer` self-play already solved
  **L3/L5/L8** as worked examples (answer keys, not to be skipped-to) and `@cikgu` handed over
  (`LEARNING_LOG.md`, 100/100, no hints spent). The owner has **not yet** built **L1**
  (`hello_pharma`) themselves — ticket waiting at `learning/diy/TICKET_l1_hello_pharma.md`. This is
  an owner-driven learning exercise (WHY-before-HOW, hints cost score) — not something to auto-build
  on the owner's behalf.
- [ ] MWAA stand-up — still not provisioned; owner-gated cloud spike (~$3–5), needs explicit
  confirmation before any AWS create.
- [ ] Optional: extend the ADR-007 Spark demo with an actual join/aggregation job — flagged in
  `spark/README.md` as not-yet-exercised; not required, just the lowest-effort next increment if the
  owner wants more Track S depth.

## Resolved / Superseded This Session (2026-06-19)
- [x] ✅ **ADR-005 S3-canonical migration — DONE & LIVE** (was "sign-off closed, migration not
  started"). See Done ✅ above for full evidence (run_id `run-20260619-045115`).
- [x] ✅ **ADR-005 Condition P4 (httpfs offline-load gate)** — satisfied by the live migration itself;
  the full pipeline ran end-to-end against real S3 via DuckDB httpfs, which is the gate's substance.
- [x] ✅ **RESOLVED 2026-06-19 (ADR-005 P5 parse gate CLOSED)**: MWAA Airflow pinned to 2.10.3/py3.11
  in the SEPARATE `requirements/requirements-mwaa.txt` (dev `.venv`/`requirements.txt` untouched), and
  `pharma_sttm_pipeline` parse-tested CLEAN (zero import errors) on the real `aws-mwaa-local:2_10_3`
  image. Reproducible on demand via `scripts/parse_test_mwaa.sh` ($0, local-only). Scope note: this
  closed the PARSE gate only — it was NOT an MWAA spike and did not provision anything (MWAA itself
  is still not stood up).
- [x] ✅ **MOOT — "no Bronze loader in Snowflake / `dbt build --target prod` fails"**: this was a real
  finding (Bronze was only ever loaded into the local DuckDB file, never into Snowflake), but
  ADR-005 removes the need for a Snowflake Bronze schema entirely — Snowflake is now a read-only
  external-table veneer over S3 Gold (`obt_sales_wide_ext`, `obt_review_wide_ext`), with no
  dbt-written tables at all. No loader will ever be built for the old architecture; not a future
  task. The stray pre-migration objects (`dim_date`, `atc_pharmclass_crosswalk` seed) left in
  Snowflake from that earlier attempt remain untouched, per owner decision — see Known Issues.

## Next Step When Resuming
1. **Owner's own Track B hands-on build (TOP item, owner-driven)** — build **L1** (`hello_pharma`)
   per `learning/diy/TICKET_l1_hello_pharma.md`, guided by `@cikgu` (WHY-before-HOW, hints cost
   score). L3/L5/L8 worked examples already exist as answer keys to re-derive, not skip to — don't
   open `gym_l8_*` before earning it. This is the one genuinely open Track B item; everything else
   (seeding, handover) is done.
2. **MWAA stand-up remains open and owner-gated** — when/if pursued, budget a short ~$3–5
   spike-and-teardown window (see `COST_LOG.md`); no cloud provisioning without explicit owner
   confirmation first.
3. **Optional — extend ADR-007 Spark demo with a real join/aggregation job** — `spark/README.md`
   already discloses this as not-yet-exercised; lowest-effort next increment for Track S depth if
   the owner wants it.
4. **Housekeeping** — delete the stale `feature/adr-005-p5-mwaa-parse-gate` branch (orphaned by a
   history rewrite; content already folded into `main`'s squashed initial commit, nothing to lose).
5. `dbt/seeds/atc_pharmclass_crosswalk.csv` only covers 8 ATC categories — if @business-analyst
   wants higher Beta-side seed coverage (a separate number from match-quality, see DQD.md), that
   seed is the lever (more rows = more match surface).
6. ✅ ALL DONE — ADR-005 migration + Confluence re-publish (2026-06-19); ADR-005 P5 parse gate
   (2026-06-19); README refresh, Track B seeding, `@cikgu` handover (2026-06-19); `O-AIR-01` Gold
   publish fix (2026-06-21); Track I incident-response library, all 8 phases/51 cards (2026-06-19/20);
   Track S ADR-007 Spark+Delta demonstration track B1–B9 incl. the one real AWS run (2026-06-20/21).
   Nothing left to publish, migrate, or close out on any of these fronts.
7. **Process note, reaffirmed every phase since**: convening the cabinet *before* build-affecting
   decisions keeps paying off (DPE/senior-DE/DA each independently re-derived findings rather than
   rubber-stamping, across ADR-005, Track I, and Track S) — keep doing this for any remaining work,
   including the eventual MWAA stand-up.

## Known Issues / Risks
| Issue | Severity | Notes |
|-------|----------|-------|
| dim_drug crosswalk seed-reach (NDC↔ATC) | HIGH (accepted) | 4.1% — honest per ADR-003, not a defect; distinct from the 71.9% match-quality KPI |
| MWAA not stood up | MED | still $0, still not provisioned; orchestration runs on local `aws-mwaa-local-runner` only. Remains owner-gated; budget ~$3–5/spike + teardown if/when pursued (see `COST_LOG.md`) — this is now the only piece of the stack still pre-ADR-005 |
| Snowflake warehouse left running | LOW | XSMALL + auto_suspend=60s; least-privilege grants in place (ADR-004); new `snowflake_gold_reader` role (ADR-005) is read-only over `gold/*` only |
| 215k reviews + hourly sales | MED | fact_review handles 215k fine (incremental + hash PK); sales_hourly landed in bronze but unused downstream (grain is daily) |
| No dedicated quarantine table | LOW (accepted for now) | `dq_flag`/`dq_reason` columns give traceability without a separate table; @data-quality-steward accepted this as the minimum-viable option — revisit if more HIGH-severity defect types appear |
| Airflow version mismatch (local 3.x vs MWAA 2.10.x) — PARSE GATE | RESOLVED 2026-06-19 (ADR-005 P5 closed) | MWAA target pinned to Airflow 2.10.3/py3.11 in the SEPARATE `requirements/requirements-mwaa.txt` (dev `.venv`/`requirements.txt` untouched). `pharma_sttm_pipeline` parsed CLEAN (zero import errors) on the real `amazon/mwaa-local:2_10_3` image; reproducible via `scripts/parse_test_mwaa.sh` ($0, local-only). NOTE: closes the PARSE gate only — NOT an MWAA spike; actual MWAA provisioning still owner-gated/not done |
| AH.md / ERD.md / STTM.md filled + signed off + published | RESOLVED 2026-06-18, RE-PUBLISHED 2026-06-19 | Documentation D1 + Data-Model M1 + Lineage governance, all @data-architect-signed-off; as-built normative. Confluence-published 2026-06-18, then **re-published 2026-06-19** post-migration (AH page 131460 v3, ERD page 98553 v2, STTM page 98534 v3, space NSL) to reflect the live S3-canonical state — Confluence publish workstream fully CLOSED, nothing pending |
| ADR-005 migration not started | **RESOLVED 2026-06-19 — MIGRATED & LIVE** | S3-canonical storage + DuckDB httpfs compute + Snowflake external-table veneer, verified end-to-end on real AWS (run_id `run-20260619-045115`). No longer a tracked risk. |
| Snowflake `prod` has no Bronze loader / `dbt build --target prod` fails | **MOOT as of 2026-06-19 (ADR-005 migrated)** | Was a real finding (Bronze only ever loaded locally into DuckDB, never into Snowflake). ADR-005 removes the need entirely: Snowflake is now a read-only external-table veneer over S3 Gold (`obt_sales_wide_ext`, `obt_review_wide_ext`) with zero dbt-written tables — there is no Bronze-in-Snowflake concept to build a loader for anymore. |
| Partial objects left in Snowflake (`dim_date`, `atc_pharmclass_crosswalk` seed) | NONE (owner decision) | Owner confirmed 2026-06-18: no teardown needed, $400/30d trial budget has ample headroom — leave as-is, not an oversight. Pre-dates and is unrelated to the new external-table veneer objects. |

## Decisions Made
| Decision | Reason |
|----------|--------|
| Thick build (not thin) | maximize learning surface |
| Star core + OBT serving | governance + BI perf (ADR-001) |
| 3 real datasets (not 1 split) | authentic cross-team consolidation |
| Hybrid stack | dev free, cloud artifact cheap |
| Beta ingest: bulk zip not 1k-row API page | full 136k catalog meaningfully raises crosswalk match odds vs a small arbitrary slice |
| drug_sk/condition_sk as hash keys (varchar), not sequence INT | standard `dbt_utils.generate_surrogate_key` pattern; avoids collision issues across UNIONed row sources; @data-architect approved |
| dim_drug includes 8 synthetic "atc_category" rows | Alpha sales never report below ATC-category grain; a real NDC row would misrepresent a whole category as one product |
| fact_review collapses multi-NDC name matches to one representative drug_sk | many NDC products share a generic/brand name; without collapsing, the join would fan out past the declared 1-row-per-review grain; @business-analyst flagged the manufacturer-attribution loss this causes — documented as a caveat in STTM.md, not reversed (grain-preservation requires it) |
| `drug_member_type` split out of `match_confidence` | @data-architect veto: overloading match_confidence with row provenance corrupted the crosswalk coverage KPI denominator |
| Snowflake RBAC: USAGE+CREATE SCHEMA only, no GRANT ALL | @data-architect veto: least-privilege; role owns what it creates, no FUTURE grants needed (ADR-004) |
| Crosswalk fuzzy tier: word-boundary regex + length guard + combination-product exclusion | @business-analyst review: naive LIKE substring matching had no guardrails; combination products were getting confidently (and wrongly) tagged with one ingredient's ATC code |
| dq_flag/dq_reason columns added (no separate quarantine table) | @data-quality-steward's minimum-viable ask — traceability for silently-altered rows without building a full quarantine mechanism for a single defect type |
| "Unit tests pass" blocker satisfied via dbt tests + new integration tests, not standalone pytest | No standalone Python transform functions exist to unit-test in this dbt-SQL-centric build; see DECISION_LOG.md |
| Close out Phase 5 on the current build before starting ADR-005 migration | Owner's explicit choice — avoids reworking Phase 5 artifacts twice; see DECISION_LOG.md |
| ADR-005 migration executed 2026-06-19 (after design ruling) | @data-architect's six build-decision rulings (immutable `gold/_current/` copy-on-publish, externalized snapshot, new scoped Snowflake role, bucket name/region/guardrails, full-rewrite facts, S3 layout) applied as-is during the apply; see `docs/ADR/ADR-005-build-decisions.md` and `SIGN_OFF_LOG.md` |

## Cost Tracking
| Service | Budget | Used | Remaining |
|---------|--------|------|-----------|
| S3 (steady-state, always-on) | n/a (Free Tier at this volume) | ~<$1/month equivalent at ~1GB landing+bronze+silver+gold parquet | n/a — not a teardown item anymore |
| MWAA spike | ~$3–5 | $0 (not yet stood up) | ~$3–5 (unspent) |
| Snowflake trial | $400/30d | ~$0 (a few cents — XSMALL warehouse, auto-suspend 60s; external-table reads over S3 Gold only, no dbt-written tables) | ~$400 |

See `COST_LOG.md` for the full post-migration FinOps writeup (steady-state S3 line item,
region-lock egress protection, retired "$3–5 short-window teardown" premise for the whole stack).

## Cikgu Score
Current: 100/100 (no hints spent — owner hasn't started Track B's hands-on L1 build yet; see
`LEARNING_LOG.md` "HANDOVER TO CIKGU")
