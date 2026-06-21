# INTERVIEW_GUIDE.md
**Owner**: @cikgu (generate) + @business-analyst (honesty check)

Generated during Phase 5 (Quality + Docs) from `JOURNEY_LOG.md`, `DECISION_LOG.md`,
`docs/DEBATE_LOG_phase_4.md`, `docs/DQD.md`, and `docs/sttm/STTM.md`. The Airflow DAG
(`airflow/dags/pharma_sttm_pipeline.py`) has since been wired for real (subprocess calls to the
actual scripts/dbt commands) and a local QA sign-off pass has run — but no MWAA/Snowflake cloud
artifact has been deployed yet, and `ADR-005` (S3-canonical storage, ~2-day migration, conditional
accept) landed after this build and is tracked as separate follow-on work, not yet started. This
guide is honest about those gaps rather than pretending they're closed.

**Note on sourcing**: `PERFORMANCE_LOG.md` and `COST_LOG.md` are stale boilerplate from a different
reference project (mention Databricks/PySpark/Snowflake clustering on a "6.3M-row" table — none of
that happened here) and were deliberately NOT used as source material for this guide. Performance
and cost claims below come from `PROJECT_STATUS.md`'s real Cost Tracking table and the actual stack
(DuckDB dev / Snowflake prod-not-yet-deployed / dbt / Airflow-not-yet-wired).

---

## 1. Quick Reference Numbers

| Metric | Value |
|--------|-------|
| Sources consolidated | 3 (Alpha: Kaggle pharma sales CSV · Beta: openFDA NDC bulk directory · Gamma: UCI/drugs.com reviews) |
| Dataset size | Beta 136,038 NDC products (raw) / 133,646 deduped; Gamma 215,063 reviews; Alpha 2,106 daily rows -> 16,848 unpivoted; all on DuckDB, single `.duckdb` file, no cluster |
| Tables built | Bronze: 3 (alpha/beta/gamma raw) · Enrich/staging: 3 + 1 intermediate (`int_drug_crosswalk`) · Mart/core: 5 (`dim_drug` SCD2, `dim_date`, `dim_condition`, `fact_sales`, `fact_review`) + 1 snapshot (`snap_beta_ndc`) · Serving/OBT: 2 (`obt_sales_wide`, `obt_review_wide`) |
| Pipeline duration | Not yet measured end-to-end — the DAG is wired for real now but has never actually been run (no local Airflow scheduler session, no MWAA deploy yet); full `dbt build` itself runs in low single-digit seconds on DuckDB at this volume |
| Tests written | 50 dbt tests (schema tests: not_null/unique/relationships/accepted_range/accepted_values, + 1 singular row-count test on `dim_drug` category rows) — 49 pass, 1 documented `warn`; 3 Great Expectations suites (`dim_drug`, `fact_sales`, `fact_review`), all passing; +9 new Python integration tests (`tests/integration/test_pipeline_reconciliation.py`) covering source→Bronze→Silver→Gold reconciliation, all passing |
| DQ pass rate | dbt: 49/50 pass + 1 accepted warn (97.7% raw-number prior to the warn being formally accepted, 100% of non-deferred checks after); GE: 3/3 suites pass |
| Coverage KPIs (measured, not assumed) | `fact_review.drug_sk` 71.9% (154,641/215,063) vs SLA ≥65% · `fact_review.condition_sk` 98.9% (212,698/215,063) vs target ≥90% · Beta NDC→ATC seed-reach 4.1% (5,524/133,646) — an intentionally different, much lower number measuring 8-category seed coverage, not match quality |
| Performance optimizations | 0 formal tuning passes — no perf wall hit yet at this volume (largest table 215k rows, sub-second to low-seconds on DuckDB); see Section 4 for what I'd profile first at 10x |
| ML models | 0 — out of scope by design (`PROJECT_BRIEF.md`: "ML/NLP on reviews... is out," Gamma is a governance source, not a sentiment-modelling target) |
| Total cost (cloud) | ~$0 spent. Snowflake 30-day trial: $400 budget, ~$0 used (role/warehouse/database provisioned least-privilege, XSMALL, auto-suspend 60s, no `prod` dbt build run yet). MWAA: ~$5 same-day spike budget, $0 used (not yet stood up) |
| Cikgu final score | —/100 (Phase 4 build + cabinet remediation complete; not yet scored — see `PROJECT_STATUS.md`) |

---

## 2. STAR Stories — 3 Strongest

### Story 1: Catching and reversing a Snowflake RBAC over-grant during a retroactive cabinet review

- **Situation**: Mid Phase-4 build, `dbt debug --target prod` failed because `NOVARTIS_STTM_ROLE`/
  `_WH`/`_DB` didn't exist in the Snowflake trial account yet (`.env` had the *intended* names from
  Phase 3, but nothing had actually been provisioned). I wrote and ran `scripts/setup_snowflake.sql`
  to create them, and the first version granted `GRANT ALL ON DATABASE`, `GRANT ALL ON SCHEMA
  PUBLIC`, and `GRANT ALL ON FUTURE SCHEMAS/TABLES` to the dbt role. It worked — `dbt debug` passed —
  so nothing flagged it as a problem at the time.
- **Task**: Days later, this project runs a "cabinet" governance model where named reviewer personas
  (architect, business analyst, QA/DQ steward, scope guardian) are supposed to review build-affecting
  decisions before they ship — and I'd skipped that step entirely for the whole Phase 4 build. Once
  caught, the task became: hold the review retroactively, with real veto authority, against the
  artifacts as they actually existed.
- **Action**: I convened four independent reviewer agents and gave them the real `setup_snowflake.sql`
  and the build it touched — not a self-assessment. `@data-architect` reviewed the grants and issued a
  hard veto: `GRANT ALL` hands a transform-only role ownership-class privileges (`CREATE`/`MODIFY`/
  `MANAGE GRANTS`/`DROP`) over the entire database and everything that will ever exist in it — far more
  than dbt needs to create and write its own schemas. I rewrote the grants to `USAGE` + `CREATE SCHEMA`
  at the database level only (the role owns whatever schemas it creates, so no `FUTURE` grants are
  needed), wrote `ADR-004` to record the least-privilege model, then re-ran the corrected grants live
  against the same trial account (`REVOKE` then `GRANT`) and re-verified `dbt debug --target prod`
  still passed.
- **Result**: Same dbt functionality, materially smaller blast radius — the role can no longer drop or
  alter anything outside what it created, or manage grants on the database. Verified empirically, not
  just asserted: `dbt debug --target prod` passed both before and after the re-grant.
- **Lesson**: "It's a trial account" is not an exception to least-privilege RBAC — the habit is the
  point, and a working credential check is not the same thing as a correctly-scoped one. I now treat
  "it worked" as necessary but not sufficient for any grant statement.

### Story 2: Recognizing and fixing my own process gap — shipping a phase without the review gate it required

- **Situation**: This project's cabinet model has a documented precedent: Phase 1 (Discovery) has a
  `DEBATE_LOG_phase_1.md` recording a real multi-persona review before that phase was signed off.
  Phase 4 (Build) — dim_drug's SCD2 design, the RBAC grants, 43 dbt tests, the Beta ingestion source
  switch — went from "read the plan" straight to "execute" with no equivalent review. I treated the
  cabinet personas as background lore for most of the build instead of an actual gate to invoke.
- **Task**: The user noticed the missing `DEBATE_LOG_phase_4.md` and asked about it directly. The task
  was to fix the actual gap, not produce a retroactive rubber stamp that just says everything was fine.
- **Action**: I ran a genuine retroactive cabinet review — four reviewer agents, each handed the real
  build artifacts, each with explicit veto authority, none told what answer to give. It surfaced real
  findings, not theater: two hard vetoes (the RBAC over-grant in Story 1, and `@scope-guardian`'s
  separate veto of the live Snowflake provisioning *event* itself — provisioning cloud infra reactively
  mid-session, outside the brief's "short, deliberate, FinOps-gated artifact window," with zero entry
  in `DECISION_LOG.md` at the time) plus two soft vetoes (`@business-analyst` on crosswalk
  testability/combination-drug handling; `@data-quality-steward` on missing `DATA_DICTIONARY.md`/
  `DQD.md`/quarantine traceability, despite Gold already being built). I resolved all four in the same
  session rather than deferring to Phase 5, and backfilled `DECISION_LOG.md` and `JOURNEY_LOG.md` so
  the paper trail exists going forward.
- **Result**: All four findings closed same-session, verified by a clean `dbt build` + `dbt test`
  re-run (50 tests, 49 pass + 1 unchanged documented warn) and a clean 3/3 GE suite re-run. Recorded in
  `docs/DEBATE_LOG_phase_4.md` and `SIGN_OFF_LOG.md`'s Phase 4 entry.
- **Lesson**: A governance process that exists on paper but gets skipped under momentum isn't a
  process — `JOURNEY_LOG.md [006]` records this explicitly as a fix for future phases: convene the
  relevant reviewers *before* build- or cloud-affecting actions, not after. I'd rather have an
  uncomfortable retroactive finding than a comfortable rubber stamp.

### Story 3: Hardening a fuzzy crosswalk match rule after it was shown to produce confident wrong answers on combination drugs

- **Situation**: The project's core governance problem is that three pharma data sources identify "a
  drug" three incompatible ways with no shared key — Alpha by ATC category, Beta by NDC code + generic/
  brand name, Gamma by free-text `drugName`. `int_drug_crosswalk.sql` resolves this with a tiered match
  (exact > normalized > fuzzy > unmatched), and the original `fuzzy` tier used a naive
  `generic_name LIKE '%example_generic%'` substring match with no word-boundary or minimum-length
  guard.
- **Task**: During the Phase 4 cabinet review, `@business-analyst` flagged that this tier would
  mishandle combination drugs — e.g. a product named "ibuprofen and famotidine" could get silently
  tagged with just the ATC code for ibuprofen, losing the famotidine component entirely. That's not a
  missing match, it's a *confidently wrong* one, which is worse than `unmatched` because nothing
  downstream knows to distrust it.
- **Action**: I added a word-boundary regex match plus a minimum-length guard (≥5 chars) to the fuzzy
  tier, and split out a new `is_combination_product` flag (`generic_name` containing `% and %`,
  `% with %`, or `/`). Products that would have hit the fuzzy criteria but are flagged as combinations
  now route to a distinct `combination_unverified` tier instead of being silently folded into `fuzzy`.
  I also added a deterministic secondary tie-break (`order by atc_code`) for cases where two seed rows
  hit the same tier.
- **Result**: Measured before/after: fuzzy-tier matches dropped from 419 to 322 (97 removed were
  word-boundary false positives); 69 previously-fuzzy matches were reclassified as
  `combination_unverified` instead of silently assigned one ingredient's code. 9,805/133,646 products
  (7.3%) are now flagged as combination products overall. The crosswalk's stated coverage number (4.1%
  seed-reach) didn't change in spirit — it was always honest about being low — but the matches it does
  claim are now defensible.
- **Lesson**: A match-rate percentage is meaningless without asking "wrong in which direction?" — a
  silent false-positive is more dangerous than an honest `unmatched`, because nothing downstream
  questions it. I now design fuzzy-match tiers to fail toward `unmatched`/flagged-uncertain rather than
  toward a confident guess.

---

## 3. What Went Wrong + Lessons

### Issue: Snowflake objects referenced in `.env` were never actually provisioned
- **What happened**: `dbt debug --target prod` failed with `Role 'NOVARTIS_STTM_ROLE' specified in the
  connect string does not exist or not authorized` (`JOURNEY_LOG.md [002]`).
- **Why**: `.env` was populated with the *intended* object names during Phase 3 design, but the actual
  role/warehouse/database were never created in the trial account — only the default `ACCOUNTADMIN`/
  `SYSADMIN`/`PUBLIC` roles and `COMPUTE_WH` existed.
- **Fix**: Wrote and ran `scripts/setup_snowflake.sql` (with user approval in the moment) to create the
  role, an XSMALL warehouse with 60-second auto-suspend, and the database.
- **Lesson for interview**: "Next time I would treat cloud provisioning as its own bounded, logged,
  FinOps-sign-off task scheduled *before* the step that needs it — not a reactive fix-it-now reaction
  to a failed credential check." (This exact gap is what `@scope-guardian` separately vetoed later —
  see the next issue.)

### Issue: RBAC over-grant (`GRANT ALL`) shipped because no governance review happened before the script touched the live account
- **What happened**: The first version of `setup_snowflake.sql` granted `GRANT ALL ON DATABASE`/
  `SCHEMA PUBLIC`/`FUTURE SCHEMAS`/`FUTURE TABLES` to the dbt role. Nothing failed at the time — it
  was caught by `@data-architect` during the retroactive Phase 4 cabinet review, not by a test.
- **Why**: The cabinet/governance review step was skipped before the script was run — the exact
  process gap the retroactive session existed to fix.
- **Fix**: Replaced with `USAGE` + `CREATE SCHEMA` at the database level; wrote `ADR-004`; re-ran the
  corrected grants live (`REVOKE` then `GRANT`) and re-verified `dbt debug --target prod` still passed.
- **Lesson for interview**: "Next time I would write the least-privilege grant first and widen it only
  if something concrete fails — not start broad because 'it's a trial account.'"

### Issue: Editing a staging model's SQL file didn't change what a downstream model saw
- **What happened**: Edited `stg_beta__ndc.sql` to flatten `pharm_class` from an array to a string,
  then immediately ran `dim_drug` and got `Binder Error: No function matches lower(VARCHAR[])` — as if
  the edit hadn't happened. Recurred with `stg_gamma__reviews.sql` after adding `review_id`
  (`JOURNEY_LOG.md [004]`).
- **Why**: DuckDB views are materialized with whatever SQL was live at `CREATE VIEW` time. Editing the
  `.sql` file on disk doesn't change the view already created in the warehouse — that requires an
  explicit `dbt run` on the changed model before anything downstream sees the new definition.
- **Fix**: Adopted the habit of always running `dbt run -s staging` (or the specific changed model)
  immediately after any staging-layer edit, before running anything downstream.
- **Lesson for interview**: "Next time I would treat 'did the warehouse object actually get rebuilt'
  as a separate question from 'did I save the file' — views and snapshots both cache old definitions
  in ways that surprised me."

### Issue: A `dbt snapshot` kept the wrong column type even after the upstream bug was fixed
- **What happened**: `dim_drug` failed with a UNION type-mismatch (`pharm_class` VARCHAR vs
  VARCHAR[]) even *after* the staging fix from the previous issue was applied (`JOURNEY_LOG.md [005]`).
- **Why**: `dbt snapshot` bakes the target table's column types in at first creation. The snapshot had
  already been built once against the old (array-typed) staging definition before the fix landed, so
  its `pharm_class` column stayed permanently VARCHAR[] regardless of what the corrected staging view
  now produced.
- **Fix**: Dropped the stale `snapshots.snap_beta_ndc` table directly in DuckDB, then re-ran
  `dbt snapshot` so it rebuilt fresh against the corrected schema.
- **Lesson for interview**: "Next time, if an upstream column *type* changes mid-development, I'd
  expect to drop-and-rebuild any snapshot built on it, not just rerun it — and I'd plan an actual
  migration (not a drop) if that snapshot already carried real SCD2 history instead of zero-history
  dev data."

### Issue: An entire build phase shipped without the cabinet review process the rest of the repo follows
- **What happened**: Phase 4 went from plan to a fully working, fully tested local pipeline with no
  cabinet review — `DEBATE_LOG_phase_1.md` exists, `DEBATE_LOG_phase_4.md` did not, until the user
  asked directly (`JOURNEY_LOG.md [006]`).
- **Why**: The build session treated `.claude/agents/` cabinet personas as background lore rather than
  an actual review gate to invoke before build-affecting decisions.
- **Fix**: Ran the retroactive four-persona review described in Story 2, with real veto authority,
  resolving all findings the same session.
- **Lesson for interview**: "Next time I would convene the relevant reviewers *before* the
  build-affecting or cloud-affecting action, not retroactively — retroactive review still catches real
  problems, but it costs a full remediation pass that prevention wouldn't have needed."

---

## 4. What I Would Do Differently

Improvements not implemented due to scope:
- **Quarantine table for DQ defects** — currently `dq_flag`/`dq_reason` columns give traceability
  in-place (e.g. `stg_gamma__reviews`'s 1,171 HTML-scrape-artifact `condition` values are nulled with a
  flag, not moved). `@data-quality-steward` accepted this as the minimum-viable option for a single
  known defect type; a real quarantine table is the natural next step if more HIGH-severity defect
  types appear (`PROJECT_STATUS.md` Known Issues).
- **Wider ATC seed for the crosswalk** — `dbt/seeds/atc_pharmclass_crosswalk.csv` only covers 8 ATC
  categories, which caps the seed-reach KPI at 4.1% regardless of match-rule quality. Deferred because
  expanding it is a deliberate `@business-analyst` content decision, not an engineering fix — it's
  the lever, clearly identified, just not pulled yet.
- **MWAA / cloud deployment** — `airflow/dags/pharma_sttm_pipeline.py` is now wired for real (every
  task shells out to the actual script/dbt command), but it has never been run against a live
  Airflow scheduler or AWS MWAA, and a cabinet review of cloud-readiness (`@data-platform-engineer`)
  surfaced a real blocking gap before any MWAA spike: the local dev environment has
  `apache-airflow==3.2.2` installed unpinned, while MWAA only supports the 2.10.x line — the DAG
  hasn't been parse-tested against an MWAA-compatible version yet. The Snowflake `prod` target is
  provisioned (least-privilege, ADR-004) but no `dbt build --target prod` has been run against it.
  Deferred deliberately — the brief locks cloud as a short, FinOps-gated, same-day artifact window,
  not a standing dev target, and the Airflow version pin needs closing before that window opens.
- **ADR-005 (S3-canonical storage)** — accepted (conditional) after this build: storage moves to
  S3 as the canonical layer for every tier, DuckDB becomes ephemeral/httpfs-only compute (no
  persistent `warehouse.duckdb`), and Snowflake is demoted to a read-only external-table serving
  veneer. Estimated ~2-day migration, `@data-platform-engineer` sign-off still pending. Deliberately
  *not* started yet — closing out Phase 5 on the current working build first, then scoping the
  migration as its own tracked phase, rather than rewriting storage mid-doc-pass.
- **`dbt snapshot` close-out on delisted products** — the `check` strategy won't close
  `dbt_valid_to` if a product is delisted from the Beta source feed; `@data-architect` accepted this
  as out of scope for the build but flagged it for `OPS_RUNBOOK.md`.

Production-readiness gaps:
- No formal performance-tuning pass has happened at this data volume. The largest table is 215k rows
  (`fact_review`); the full `dbt build` runs in seconds on DuckDB. I have not hit a wall that forced a
  profiling exercise, and I'd rather say that honestly than invent a tuning story.

Scale-up considerations:
- **At 10x data volume** (≈2M reviews, ≈1.3M NDC products): I'd profile the crosswalk's fuzzy-match
  tier first — it's a string-comparison join against a seed table, and at this volume the join
  strategy (and whether DuckDB's single-threaded-per-query-by-default behavior becomes a bottleneck)
  is the part I have the least empirical evidence about today. I'd also expect the `min(drug_sk)`
  collapse in `fact_review` (resolving many NDC products sharing a name to one representative key) to
  need a materialized lookup table rather than an inline subquery, to avoid recomputing it per fact
  build.
- **At 100x users** (BI/dashboard load against `obt_*_wide`): the OBT tables are already designed to
  be rebuilt from the star rather than hand-maintained (ADR-001), so the scaling lever there is
  Snowflake warehouse sizing and `cluster_by` (already specified as `year, atc_code` / `year` in the
  Snowflake target, currently a no-op on DuckDB) — not a redesign.
- **At 10x source count** (more "Project Delta/Epsilon" teams joining the consolidation): the
  crosswalk pattern (conformed dimension + tiered match + explicit `match_confidence`) generalizes,
  but the seed-maintenance process would need to become a tracked, owned artifact rather than a single
  CSV — that's a governance scaling question, which is the actual JD this project targets.

---

## 5. Decision Logic Guide

### Decision: Why provision Snowflake reactively mid-session, instead of deferring to a bounded artifact window?
- **Code/doc reference**: `DECISION_LOG.md` row 1; `scripts/setup_snowflake.sql`; `JOURNEY_LOG.md [002]`
- **Why chosen**: Unblocked `dbt debug --target prod` in the same step it was being verified, with the
  user's approval in the moment.
- **Alternative rejected**: Stay on `dev`/DuckDB and defer cloud entirely to a later bounded artifact
  window — this was the *correct* alternative per `@scope-guardian`'s later veto.
- **Trade-off accepted**: Speed now, governance debt later — `@scope-guardian` vetoed the decision
  retroactively (reactive cloud spend outside the brief's deliberate-artifact-window scope; zero
  `DECISION_LOG.md` entry at the time it was made).
- **Risk**: This is the one decision in this guide I'd flag as a genuine mistake, not just a documented
  trade-off — "the user approved it live" is not equivalent to a FinOps-gated artifact window. It's
  retroactively logged now per the veto's required action, but the right call was to ask "is this the
  bounded window, or am I improvising one" before running the script.

### Decision: `USAGE` + `CREATE SCHEMA` least-privilege grants, not `GRANT ALL`
- **Code reference**: `scripts/setup_snowflake.sql`; `docs/ADR/ADR-004-snowflake-rbac.md`
- **Why chosen**: The role provisions and therefore owns its own working schemas (`enrich`,
  `data_mart`, `rrd`, `snapshots`) via `CREATE SCHEMA` — no `FUTURE` grants are needed because
  ownership of self-created objects already carries full rights on them.
- **Alternative rejected**: `GRANT ALL` on the database/schema/future objects — rejected because it
  hands ownership-class privileges (`CREATE`/`MODIFY`/`MANAGE GRANTS`/`DROP`) across the *entire*
  database, not just what the role itself creates.
- **Trade-off accepted**: None functional — `dbt debug --target prod` passes identically either way;
  the only cost was the time to rewrite and re-verify the grant script.
- **Risk**: If a future need arises for this role to read from a separately-owned raw/source schema
  (e.g. data landed by a different ingestion identity), an explicit `GRANT SELECT ON FUTURE TABLES`
  would need to be added then — deliberately not pre-granted now since no such schema exists yet.

### Decision: Beta ingestion — full 136,038-row bulk zip, not the 1,000-row openFDA API stub
- **Code reference**: `scripts/ingest_beta_ndc.py`; `DECISION_LOG.md` row 2
- **Why chosen**: More product coverage directly raises crosswalk match odds against Gamma's free-text
  drug names — validated empirically before committing (estimated ~51% exact-name overlap on the full
  set vs. a much smaller, untested overlap on a 1k-row arbitrary slice).
- **Alternative rejected**: Keep the 1,000-row stub as originally scaffolded — rejected because the
  brief itself defines Beta as the full openFDA NDC directory; the 1k-row page was an unfinished stub,
  not a locked scope line (`@scope-guardian` confirmed this was fixing a stub to match its own spec,
  not scope creep).
- **Trade-off accepted**: 136x more bronze rows to process — flagged as a capacity-planning note for
  future phases, not a blocker, since DuckDB handled it without incident.
- **Risk**: None realized; reversible (re-running with the old 1k-row logic would require reverting
  the script, but no downstream consumer depends on the smaller slice).

### Decision: Hash surrogate keys (`dbt_utils.generate_surrogate_key`, VARCHAR) instead of BIGINT sequence
- **Code reference**: `dbt/models/marts/core/dim_drug.sql`, `dim_condition.sql`, `fact_sales.sql`,
  `fact_review.sql`; `DECISION_LOG.md` row 3
- **Why chosen**: `dim_drug` unions two independently-generated row sources (NDC snapshot rows keyed
  on `(product_ndc, dbt_valid_from)`, plus 8 synthetic ATC-category rows keyed on `(atc_code)`) — a
  BIGINT sequence would require coordinating numbering across both branches on every rebuild; a hash
  key is collision-free by construction and idempotent across reruns. `@data-architect` checked the
  key composition and confirmed the two domains are disjoint.
- **Alternative rejected**: BIGINT via `row_number()`/sequence (the original Phase 3 physical-model
  stub) — rejected because it doesn't survive a UNION of two independently-built row sets without
  extra coordination logic.
- **Trade-off accepted**: Wider key (32-char VARCHAR vs 8-byte BIGINT) — negligible at this row volume
  (~134k); documented as a deviation from the Phase 3 stub per `@data-architect`'s request.
- **Risk**: Would require a backfill/remap if changed later, but no downstream consumers exist yet, so
  the risk is currently theoretical.

### Decision: `drug_member_type` discriminator split out of `match_confidence`
- **Code reference**: `dbt/models/marts/core/dim_drug.sql`; `dbt/tests/dim_drug_category_row_count.sql`
- **Why chosen**: The original build overloaded `match_confidence` with a literal `'category_seed'`
  value to mark the 8 synthetic ATC-category rows. `@data-architect` flagged that this corrupts the
  crosswalk coverage KPI denominator — anyone grouping by `match_confidence` would get 8 phantom rows
  mixed into a metric that's supposed to measure NDC-product match quality.
- **Alternative rejected**: Leave `match_confidence` overloaded — rejected as a structural integrity
  problem, not a style preference, because it silently changes what the coverage KPI counts.
- **Trade-off accepted**: One more column; `match_confidence` is now `null` (not a 5th pseudo-value)
  for category rows, enforced via a `config.where`-scoped `not_null` test.
- **Risk**: None identified — a singular test now asserts exactly 8 category rows exist, closing the
  loop @data-architect's condition required.

### Decision: Why a star-schema core + a denormalized OBT serving layer, not just one or the other?
- **Code reference**: `docs/ADR/ADR-001-star-core-obt-serving.md`; `dbt/models/marts/serving/`
- **Why chosen**: The star (`dim_drug`/`dim_date`/`dim_condition` + `fact_sales`/`fact_review`) is the
  system of record for governance — conformed dimensions, SCD2 history, auditable lineage. The OBT
  tables (`obt_sales_wide`, `obt_review_wide`) are derived/rebuilt from the star purely for 7AM BI
  query performance, with no independent transformation logic of their own.
- **Alternative rejected**: OBT-only (no star) — would lose conformed-dimension governance and SCD2
  history, the actual JD-weighted deliverable (40% STTM governance, 20% model governance per
  `PROJECT_BRIEF.md`). Star-only (no OBT) — would push join cost onto every BI query against the 7AM
  SLA the brief explicitly tests for (DAG Group D, 10% weight), with no precomputed denormalized layer
  to skip that join cost.
- **Trade-off accepted**: Storage/compute duplication (every fact ends up materialized twice, once
  normalized, once denormalized) in exchange for clean separation of "what's true" from "what's fast."
- **Risk**: OBT can drift from the star if someone edits it directly instead of rebuilding — mitigated
  by treating OBT as derived-only, never hand-edited, in ADR-001.

---

## 6. Common Interview Q&A

### Q: "Tell me about yourself" (90-second pitch)
I've been building a data-engineering portfolio project modeled on a real job description for a
pharma commercial-analytics governance role — not a generic ETL exercise. The premise: three
real-world pharma datasets (point-of-sale pharmacy sales from Kaggle, the FDA's openFDA NDC product
directory, and a UCI patient-drug-review dataset) each describe "a drug" in an incompatible way — ATC
category code, NDC code plus pharmacologic class, and free-text drug name, with no shared key. The
job I modeled this on is 40% source-to-target-mapping governance, 30% documentation governance, 20%
data-model governance, and only 10% actual DAG/pipeline work — so I deliberately kept the three
source pipelines thin and put my real effort into consolidating them: a conformed `dim_drug`
dimension with an explicit, tiered, honestly-partial crosswalk; a single STTM document with
column-level lineage for every target field; and a governance review process modeled as a "cabinet"
of reviewer personas with real veto authority. Right now I'm at the end of the build phase — local
DuckDB target, 50 dbt tests passing, the crosswalk hardened after a real governance review caught a
couple of issues — and the next phase is wiring the Airflow DAG and running one bounded Snowflake
cloud artifact.

### Q: "Walk me through your pipeline architecture"
Four tiers: Landing holds immutable raw files per source (`data/landing/{alpha,beta,gamma}/`, dated
folders, replay/audit-able). Bronze loads those into DuckDB with zero cleaning, just `+load_ts` and
`+source_file` audit columns. Enrich (staging + one intermediate model) is where each source gets
cleaned independently — Alpha's 8 wide ATC sales columns get unpivoted into one row per code per day,
Beta's NDC records get deduped on `product_ndc` and have their array-typed `pharm_class` flattened,
Gamma's reviews get a normalized drug-name match key and a `dq_flag`/`dq_reason` pair for traceability
when a value gets scrubbed. `int_drug_crosswalk` lives here too — it's the tiered ATC-to-NDC match
that feeds `dim_drug`. Gold is where the three sources actually converge: a conformed `dim_drug` (SCD2
via a real `dbt snapshot`, plus 8 synthetic ATC-category rows so `fact_sales` always has a join
target), `dim_date`, `dim_condition`, and two fact tables (`fact_sales` at ATC-category-by-day grain,
`fact_review` at one-row-per-review grain). On top of that star sits a small OBT serving layer
(`obt_sales_wide`, `obt_review_wide`) — pure denormalized joins, no new logic, rebuilt from the star
for BI query performance. Tools: Python ingestion scripts, DuckDB for dev compute, dbt Core for all
transformation logic (same SQL targets both DuckDB dev and Snowflake prod via dialect-dispatch
macros), Great Expectations for the distributional checks dbt's generic tests don't cover well, and
Airflow (local runner today, MWAA for the cloud artifact) for orchestration — the DAG is wired for
real now (every task shells out to the actual script/dbt command), though it hasn't been run against
a live scheduler yet, and a cabinet review just flagged an Airflow-version mismatch to fix before any
MWAA spike.

### Q: "What was the hardest technical problem?"
The crosswalk hardening — see Story 3 in Section 2. The hard part wasn't writing the match logic, it
was recognizing that a higher match-rate isn't automatically better if some of those matches are
confidently wrong. A combination drug like "ibuprofen and famotidine" matching on the substring
"ibuprofen" and getting silently tagged with ibuprofen's ATC code is worse than leaving it unmatched,
because nothing downstream knows to distrust that row. Fixing it meant adding guardrails (word
boundaries, minimum length, an explicit combination-product flag) that *reduced* the headline match
count — 419 fuzzy matches dropped to 322 — which felt like a regression until I framed it correctly:
the right metric isn't "how many matched" but "how many of the matches are defensible."

### Q: "How do you ensure data quality?"
Two layers, deliberately not redundant. dbt schema tests (50 total: not_null, unique, relationships,
accepted_range, accepted_values, plus one singular row-count test) run on every build and act as the
hard gate — `severity: error` actually fails the `dbt test` step. Great Expectations covers what
schema tests don't do well: row-count drift detection and the coverage-rate SLAs themselves (e.g.
`fact_review.drug_sk` resolution ≥65%, currently 71.9%). Severity is tiered — CRITICAL blocks,
HIGH quarantines-and-continues (currently null-in-place with a `dq_flag`/`dq_reason` pair rather than
a separate quarantine table, accepted as the minimum-viable option for a single known defect type),
MEDIUM flags-and-logs. The one documented `warn` downgrade we have (`generic_name` not_null, 3 rows
out of 136,038) went through an actual investigation — confirmed legitimate brand-only OTC products,
documented in STTM.md's exceptions table — rather than being silenced to make the pass rate look
better.

### Q: "How would you scale this to 100x data volume?"
Honestly — I haven't hit a performance wall yet, because the largest table here is 215k rows and the
full `dbt build` runs in seconds on DuckDB. What I'd actually profile first at 10x: the crosswalk's
fuzzy-match join (string comparison against an 8-row seed, but over a much larger NDC catalog), and
the `min(drug_sk)` collapse in `fact_review` that resolves many same-named NDC products down to one
representative key — that's currently an inline subquery, and at higher volume I'd materialize it as
its own lookup table so it's not recomputed on every fact build. On the serving side, the OBT tables
are already designed to be derived/rebuilt rather than hand-maintained, so the scaling lever there is
warehouse sizing and the `cluster_by` hints already specified for the Snowflake target (currently a
no-op on DuckDB, since DuckDB doesn't have that concept).

### Q: "Why did you choose <X> over <Y>?"
See Section 5 — five concrete decisions with the alternative actually considered and why it lost,
including one (reactive Snowflake provisioning) that I'm honest didn't go the way it should have and
got caught by a governance review after the fact, not before.

### Q: "What's a mistake you made and how did you handle it?"
The Snowflake RBAC over-grant (Story 1) and the missing Phase-4 cabinet review (Story 2) are both real
mistakes, not manufactured humility for an interview answer. The over-grant shipped because nothing
forced a second pair of eyes on a grant script before it touched a live account; the missing review
happened because I treated a documented process as optional under momentum. Both were caught by
actually invoking the review process this project is built around, and both were fixed the same
session they were found, with the fix and the reasoning recorded in `ADR-004` and
`docs/DEBATE_LOG_phase_4.md` rather than just quietly corrected.

---

## 7. Resume Bullet Drafts

**Honesty checked by @business-analyst.**

Variant A (metrics-forward):
> Consolidated 3 divergent pharma data sources (134k+ NDC products, 215k+ patient reviews, 2,100+
> daily sales records) into one governed Kimball-star + OBT data mart using dbt Core and DuckDB,
> backed by 50 automated data-quality tests and 3 Great Expectations suites; built a tiered
> fuzzy-match crosswalk resolving free-text drug names to a conformed dimension at measured
> 71.9%/98.9% coverage against defined SLAs.

Variant B (architecture-forward):
> Designed and built a 4-tier medallion pipeline (Landing -> Bronze -> Enrich -> Gold) with a
> conformed SCD2 `dim_drug` crosswalk reconciling 3 incompatible drug-identification schemes (ATC
> code, NDC + pharmacologic class, free-text name) with no native shared key, using hash-based
> surrogate keys to safely union independently-sourced row sets; implemented a hybrid star-schema +
> one-big-table serving layer (ADR-driven) to balance governance with BI query performance.

Variant C (impact-forward / process-forward):
> Ran a structured multi-persona governance review process on a completed data pipeline build,
> surfacing and resolving 2 hard architectural vetoes (a Snowflake RBAC over-grant; an undocumented
> reactive cloud-provisioning decision) and 2 soft data-quality vetoes (crosswalk match-rule
> robustness; missing data-quality documentation) in a single remediation session — then fixed the
> process gap that allowed the issues to ship unreviewed in the first place.

---

## 8. Questions to Ask the Interviewer

1. "What does your current data pipeline look like — batch, streaming, or both?"
2. "How does the team handle data quality failures in production — who gets alerted, and is there a
   formal severity/quarantine policy, or is it closer to ad hoc?"
3. "When two teams define the same business entity differently — like 'a drug' or 'a customer' —
   what's the actual process for reconciling that, and who has sign-off authority on the resolution?"
4. "How do you decide when to rebuild vs refactor a pipeline?"
5. "What does the on-call rotation look like for the data platform team, and how often does a
   governance or RBAC issue actually get caught before it ships versus after?"
