# PROJECT_STATUS.md
**Last updated**: 2026-06-20 (header note only — see below; full backfill of the
troubleshooting-library/ADR-006/ADR-006-A1/ADR-007 sessions still owed, out of scope for this edit)
**Current phase**: Phase 5 — Quality + Docs complete, cabinet-reviewed. **ADR-005 (S3-canonical
storage pivot) MIGRATED & LIVE on real AWS as of 2026-06-19** (run_id `run-20260619-045115`) —
S3-canonical storage + DuckDB httpfs compute + Snowflake external-table serving veneer, verified
end-to-end (dbt 63 PASS/1 WARN/0 ERROR, GE PASS, KPIs identical to baseline). AH/ERD/STTM
re-published to Confluence reflecting the as-built migrated state. MWAA orchestration still **not**
stood up — remaining wrap-up only.

**2026-06-20 — Fasa A CLOSED**: `O-AIR-07` (orchestrated DAG could never complete a run across
per-task `:memory:` subprocess boundaries) and `P-PMR-07` (`stg_beta__ndc` dedup non-idempotent,
inflated `dim_drug` 133,654→133,758 on rerun) both fixed in the working tree and independently
re-verified by @senior-data-engineer + ratified by @data-architect against the local MinIO
`gym-lake` incubator (zero contact with the live AWS bucket) — see `SIGN_OFF_LOG.md` "Fasa A
closure" entry and `docs/OPS_RUNBOOK.md` Known Gaps. No ADR amendment. Still uncommitted. This was
ADR-007's (Spark+Delta demonstration track) hard sequencing prerequisite — now unblocked.

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
- [ ] `README.md` refresh to reflect the live migration (storage/compute/serving framing) — being
  done in parallel this session.
- [ ] Track B — SLA-gym self-play (`learning/CURRICULUM.md` L1→L10) — not yet started.
- [ ] `@cikgu` handover / scoring pass — not yet started.

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
1. **README.md refresh (TOP item, in progress in parallel)** — correct the remaining pre-migration
   framing (storage/compute/serving sections) to the as-built S3-canonical + DuckDB-httpfs +
   Snowflake-external-table-veneer state. Keep all honest KPI/business-question content as-is.
2. **Track B — SLA-gym self-play** (`learning/CURRICULUM.md` L1→L10, `SLA_GYM_PROMPT.md`) — next
   after the README refresh lands. Not yet started.
3. **`@cikgu` handover** — scoring pass / interview-readiness review, after Track B. Not yet started.
4. ✅ DONE 2026-06-19: ADR-005 S3-canonical migration — went LIVE on real AWS end-to-end. ✅ DONE
   2026-06-19: AH/ERD/STTM re-published to Confluence reflecting the migrated state (AH 131460 v3,
   ERD 98553 v2, STTM 98534 v3). Nothing left to publish or migrate on this front.
5. ✅ DONE 2026-06-19 (ADR-005 P5 parse gate CLOSED): Airflow pinned to MWAA-supported 2.10.3 in the
   separate `requirements/requirements-mwaa.txt`, and `pharma_sttm_pipeline.py` parse-tested CLEAN
   (zero import errors) via `aws-mwaa-local-runner`. Reproduce on demand: `bash scripts/parse_test_mwaa.sh`
   ($0, local-only). This is the parse gate only — MWAA itself is still NOT stood up.
6. **MWAA stand-up remains open and owner-gated** — when/if pursued, budget a short ~$3–5
   spike-and-teardown window (see `COST_LOG.md`); no cloud provisioning without explicit owner
   confirmation first.
7. `dbt/seeds/atc_pharmclass_crosswalk.csv` only covers 8 ATC categories — if @business-analyst
   wants higher Beta-side seed coverage (a separate number from match-quality, see DQD.md), that
   seed is the lever (more rows = more match surface).
8. **Process note, reaffirmed this phase**: convening the cabinet *before* build-affecting decisions
   worked well this session (DPE reviewed the DAG wiring and gave a real ADR-005 verdict rather than
   rubber-stamping pre-drafted conditions — see `JOURNEY_LOG.md` [010]; @data-architect's ADR-005
   build-decisions ruling and the post-migration re-sign-off followed the same pattern) — keep doing
   this for any remaining work, including the eventual MWAA stand-up.

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
Current: —/100 (Phase 4 build + cabinet remediation complete; not yet scored)
