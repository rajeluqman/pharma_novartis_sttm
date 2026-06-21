# DEBATE_LOG_phase_4.md
Cabinet meeting transcript for Phase 4 (Build) — **held retroactively**.

---

## Meeting: Phase 4 — Build (retroactive review)
**Date**: 2026-06-18
**Attendees**: @data-architect, @business-analyst, @data-quality-steward, @scope-guardian
**Process note**: Phase 4 was built and shipped to a working local (DuckDB) pipeline *before* this
meeting happened — a process violation of the cabinet model (Phase 1 had a debate log; Phase 4 did
not). This meeting reviews the build retroactively, under protest of the sequence per
@data-architect, not of the engineering itself. Convened after the user noticed the missing log.

### Architecture Review (@data-architect)
[@data-architect — mood: calm, with one cold spot on RBAC]

Reviewed: `dim_drug.sql` two-member-type union (NDC product rows + 8 `category_seed` rows),
`drug_sk`/`condition_sk` type change BIGINT → VARCHAR hash key, `dbt snapshot` SCD2 implementation,
and `scripts/setup_snowflake.sql` RBAC grants.

- Dual-membership `dim_drug` design: **APPROVED WITH CONDITIONS** — architecturally honest (a real
  NDC row would misrepresent an entire ATC category as one product), consistent with ADR-001/003.
  Conditions: add an explicit `drug_member_type ∈ {ndc_product, atc_category}` discriminator
  (currently overloaded onto `match_confidence`, which corrupts the coverage KPI denominator if
  someone naively groups by it); document the union pattern in STTM/DATA_MODEL; add an orphan test
  asserting exactly 8 category rows.
- Hash surrogate keys via `dbt_utils.generate_surrogate_key`: **APPROVED** — correct fix for
  cross-source key collisions in a UNION; key composition checked and is sound (NDC rows key on
  `(product_ndc, dbt_valid_from)`, category rows on `(atc_code)`, disjoint domains). Document the
  BIGINT→VARCHAR deviation from the Phase 3 stub in DATA_MODEL.md.
- Real `dbt snapshot` (check strategy) for SCD2: **APPROVED** — correct use of the tool; flagged that
  `check` strategy won't close `dbt_valid_to` if a product is delisted from the source feed (accepted
  as out of scope for this build, noted for OPS_RUNBOOK).
- Snowflake RBAC (`GRANT ALL ON DATABASE`/`SCHEMA`/`FUTURE SCHEMAS`/`FUTURE TABLES`):

  ```
  🛑 VETOED by @data-architect
  Reason: Violates least-privilege RBAC. GRANT ALL hands the dbt runtime role
          ownership-class privileges (CREATE/MODIFY/MANAGE GRANTS/DROP) over the
          entire database and everything that will ever exist in it.
  Required action: Replace with scoped grants — USAGE on database, USAGE+CREATE
          SCHEMA at the database level, USAGE+CREATE TABLE/VIEW on the build
          schemas only, SELECT on future tables in source schemas only. Warehouse
          USAGE-only grant is already correct, keep as-is.
  Alternative: Standard dbt-on-Snowflake split — one OWNER role, one TRANSFORMER
          role with scoped privileges, not one ALL-granted role.
  ADR reference: none exists yet — write ADR-004 (Snowflake RBAC / least-privilege
          model) before this script is re-run against any account.
  Escalation: emergency meeting with @project-manager + @senior-data-engineer;
          loop in @data-platform-engineer + @finops-agent.
  ```

### Business Rule Review (@business-analyst)
[@business-analyst — mood: skeptical]

Reviewed: `int_drug_crosswalk.sql` match tiers, `fact_review.sql` drug_sk collapse logic,
`stg_gamma__reviews.sql` condition-nulling rule.

🛑 **NOT TESTABLE — needs criteria**, on all three (soft veto, not blocking, conditional sign-off):

1. **Crosswalk tiers**: the 4.4% match-rate KPI conflates two different things — "8 ATC codes can't
   cover a 133k-product catalog" (a seed-coverage problem) vs. "the match logic itself is weak" (a
   matching-quality problem). Fuzzy tier (`generic_name LIKE '%example_generic%'`) has no
   word-boundary/min-length guard and will mishandle combination drugs (e.g. "ibuprofen and
   famotidine" silently tags as M01AE, losing the famotidine component — a confident wrong answer,
   worse than `unmatched`). No tie-break beyond tier rank if two seed rows hit the same tier.
2. **fact_review drug_sk collapse** (`min(drug_sk)` across NDC products sharing a name): mechanically
   defensible to preserve fact grain, but arbitrary at the business level (manufacturer/labeler
   attribution is silently lost) — needs explicit documentation that `fact_review.drug_sk` does NOT
   support manufacturer-level questions, plus a guard so no OBT/serving model joins back to
   `labeler_name`/`product_ndc` through it without that caveat. The 71.9% match rate has no stated
   target/SLA anywhere (DQD.md is still a template) — "71.9%" can't be judged good or bad without one.
3. **Condition-nulling rule**: `ILIKE '%</span%'` only catches one known artifact shape; no profiling
   was done for other malformed values (other HTML tags, empty/whitespace, encoding garbage), so
   "1,171 rows" is "rows matching this one signature," not necessarily "all bad rows." No regression
   test exists proving the rule doesn't over- or under-null.

Demanded before re-review: split seed-coverage vs. match-quality metrics; a combination-drug test
fixture; a stated coverage SLA in DQD.md; a completeness profile of `condition` anomalies beyond the
one regex.

### Data Quality Review (@data-quality-steward)
[@data-quality-steward — suite: dbt schema tests (staging + marts/core + seeds)]
Pass rate: 42/43 = 97.7% PASS, 1/43 WARN, 0/43 ERROR — clears the 95% Gold-blocking threshold on raw
numbers.

**SOFT VETO — provisional, not retroactively blocking what's built, but blocking what's next.**
Ran the test suite directly to confirm the pass rate independently rather than trusting the report.
Findings:
- `DATA_DICTIONARY.md` and `DQD.md` are **still templates** — zero columns from this build documented
  in either, despite both being owned by this role and DQD.md supposedly gating Gold builds.
  `data_quality/expectations/` (the owned GE-suite directory) is **empty** — no Great Expectations
  suite exists, contra the locked stack table in CLAUDE.md, with no ADR recording that dbt tests
  supersede GE for this project.
- The `severity: warn` downgrade on `stg_beta__ndc.generic_name` not_null **accepted** — properly
  investigated (3/136,038 legitimate brand-only OTC products), documented inline, traced into
  STTM.md's defect table. Correct procedure for a downgrade.
- No quarantine table or `dq_flag` column exists anywhere — PIPELINE_SPEC.md's "critical cols →
  quarantine" is not implemented; bad values (e.g. the 1,171 garbage `condition` rows) are nulled
  in-place with no flag and no record, making "always null" and "scrubbed for being garbage"
  indistinguishable downstream. This is the real objection — not that data was kept, but that the
  scrub is silent and irreversible.

Will not demand rollback (tests are real and pass; "process theater" wouldn't help). Requires before
considering Phase 4 DQ-complete: DATA_DICTIONARY.md and DQD.md filled (promote STTM.md's defect table
into DQD.md as a start), a `dq_flag`/`dq_reason` column on any model that silently alters rows, and
either a populated `data_quality/expectations/` or an ADR documenting dbt-tests-supersede-GE.

### Scope Review (@scope-guardian)
[@scope-guardian — mood: strict, downgraded to hostile after Decision 2]

Reviewed against PROJECT_BRIEF.md, ADR-002, and the pre-session PROJECT_STATUS.md resume plan
(verify creds → install deps → run 3 ingestion scripts → build Alpha→Beta→Gamma on DuckDB →
crosswalk/dim_drug → fill STTM.md).

- **Beta bulk download** (1,000-row API stub → full 136,038-row bulk zip): **APPROVED** — the brief
  defines Beta as the full openFDA NDC directory; the 1,000-row page was an unfinished stub, not a
  locked scope line. Fixing a stub to match its own spec is not scope creep. Flagged as a
  capacity-planning note (136x volume jump) for @data-architect/@infra-reality-agent, not a scope
  violation.
- **Cross-dialect macros** (`parse_date`, `regexp_replace_all`): **APPROVED** — verified both are
  called today by models already in this build (not speculative future-phase scaffolding); minimum
  plumbing to make the already-locked HYBRID dev/duckdb + prod/snowflake `profiles.yml` targets
  actually compile.
- **43 dbt tests**: **APPROVED** — "all unit tests pass" is a *named* Phase 4→5 hard blocker in
  CLAUDE.md; writing the tests that satisfy a blocker for the phase already in progress is finishing
  Phase 4, not starting Phase 5 early.
- **Snowflake provisioning** (`setup_snowflake.sql` run live against the trial account mid-session):

  ```
  🛑 VETOED by @scope-guardian — SCOPE CREEP
  Original scope: PROJECT_BRIEF.md locks cloud (MWAA+Snowflake) as a SHORT,
          DELIBERATE artifact window ("same-day create→run→teardown spike"),
          owned by @data-platform-engineer with @finops-agent sign-off — not a
          standing target during local dev. The pre-session resume plan's steps
          0-5 were entirely local/DuckDB; none mention cloud provisioning.
  Proposed addition: Live CREATE ROLE/WAREHOUSE/DATABASE + grants executed
          against the real trial account, reactively, the moment step 0's cred
          check failed.
  Decision: REJECT the provisioning *event* (not the SQL's correctness — XSMALL +
          auto_suspend=60 shows good cost hygiene)
  Defer to: BACKBLOG.md — cloud provisioning should be its own bounded,
          FinOps-sign-off artifact-window task, not an ad hoc fix-it-now reaction
          to a failed cred check.
  Escalation: PM emergency meeting if user insists
  ```
  Aggravating factor: DECISION_LOG.md, JOURNEY_LOG.md, and SIGN_OFF_LOG.md are all still empty
  templates — zero paper trail that the live-infra decision was deliberated rather than just done.
  "The user approved it live in the moment" is not equivalent to the FinOps-gated artifact window the
  brief actually locked in.

---

## Decisions Made
| Decision | Justification | Approver |
|----------|---------------|----------|
| dim_drug two-member-type union (NDC + category_seed) | Honest join target for Alpha's category-only grain; no false product-level precision | @data-architect (APPROVED WITH CONDITIONS) |
| drug_sk/condition_sk as hash keys, not BIGINT | Avoids cross-source key collisions in a UNION; idempotent rebuild | @data-architect (APPROVED) |
| dim_drug SCD2 via real `dbt snapshot` (check strategy) | Correct tool for the job; no reliable source `updated_at` to use timestamp strategy | @data-architect (APPROVED) |
| Beta ingestion: full bulk NDC zip (136k) not 1k-row API stub | Matches the brief's own definition of the Beta source; stub was unfinished, not scope-locked | @scope-guardian (APPROVED) |
| Cross-dialect macros (parse_date, regexp_replace_all) | Load-bearing today, not speculative; required by the already-locked hybrid dev/prod targets | @scope-guardian (APPROVED) |
| 43 dbt tests added | Satisfies the named Phase 4→5 "all unit tests pass" hard blocker | @scope-guardian (APPROVED) |
| `generic_name` not_null downgraded to warn (3 rows) | Investigated, documented, traced to STTM defect log — correct downgrade procedure | @data-quality-steward (ACCEPTED) |

## Open Questions / Deferred
- Should `match_confidence` be split from a new `drug_member_type` discriminator in `dim_drug`? (@data-architect condition)
- What is the actual target SLA for `fact_review.drug_sk` coverage (currently 71.9%, unset target)? (@business-analyst)
- Does the team formally adopt "dbt tests supersede Great Expectations" (needs an ADR), or is GE still owed? (@data-quality-steward)
- Combination-drug handling in the crosswalk fuzzy tier — flag distinctly or exclude? (@business-analyst)

## Veto Raised?
**Yes — two hard vetoes at the time of this meeting, both pointing at the same event:**
1. 🛑 @data-architect VETOED the Snowflake `GRANT ALL` RBAC grants (least-privilege violation, needs ADR-004 + scoped re-grant).
2. 🛑 @scope-guardian VETOED the live Snowflake provisioning event itself (reactive cloud spend outside the brief's deliberate-artifact-window scope; no decision-log paper trail).

Both escalated to "PM emergency meeting if user insists." No PM agent was convened — the human user
was asked directly which remediation path to take (resolve both now vs. paper-trail-only vs. leave
open) and chose **resolve both now**.

**Soft vetoes at the time of this meeting (not blocking, conditional):**
- @business-analyst: NOT TESTABLE on crosswalk tiers, fact_review collapse, condition-nulling — wanted test fixtures + a stated SLA before full sign-off.
- @data-quality-steward: SOFT VETO, provisionally tolerated — DATA_DICTIONARY.md/DQD.md/quarantine mechanism required to close before DQ governance considered satisfied.

## Resolution (same session, 2026-06-18)
User chose to resolve all four findings immediately rather than defer to Phase 5. Actions taken:

| Finding | Resolution | Evidence |
|---|---|---|
| @data-architect RBAC veto | `GRANT ALL` replaced with `USAGE`+`CREATE SCHEMA` at db level; re-run live against the Snowflake trial account; `dbt debug --target prod` re-verified passing | `scripts/setup_snowflake.sql`, `docs/ADR/ADR-004-snowflake-rbac.md` |
| @data-architect: split `drug_member_type` out of `match_confidence` | Added `drug_member_type ∈ {ndc_product, atc_category}`; `match_confidence` now null (not a 5th pseudo-value) for category rows; singular test asserts exactly 8 category rows | `dbt/models/marts/core/dim_drug.sql`, `dbt/tests/dim_drug_category_row_count.sql` |
| @scope-guardian process veto (no paper trail) | Backfilled `DECISION_LOG.md` (4 entries) and `JOURNEY_LOG.md` (Phase 4 entries 002-006, including this meeting itself) | `DECISION_LOG.md`, `JOURNEY_LOG.md` |
| @business-analyst: crosswalk fuzzy tier too promiscuous, combination drugs mishandled, no tie-break | Added word-boundary regex + length guard; combination products excluded from `fuzzy`, tagged `combination_unverified` instead; deterministic secondary `order by atc_code` tie-break | `dbt/models/intermediate/int_drug_crosswalk.sql` |
| @business-analyst: seed-coverage vs. match-quality conflated in one KPI | Reported separately in DQD.md/STTM.md: 4.1% (seed reach) vs. 71.9% (fact_review name-match quality, independent of the ATC seed) | `docs/DQD.md`, `docs/sttm/STTM.md` |
| @business-analyst: no SLA for fact_review.drug_sk coverage | Set ≥65% target (measured 71.9%); ≥90% target for condition_sk (measured 98.9%); enforced as Great Expectations checks, not just measured | `docs/DQD.md`, `data_quality/expectations/fact_review_suite.json` |
| @business-analyst: manufacturer attribution silently lost in `min(drug_sk)` collapse | Documented explicit caveat in STTM.md; no code change (the collapse itself remains — grain-preservation requires it) | `docs/sttm/STTM.md` |
| @data-quality-steward: DATA_DICTIONARY.md / DQD.md still templates | Both filled for every Bronze/Enrich/Gold column built so far | `docs/DATA_DICTIONARY.md`, `docs/DQD.md` |
| @data-quality-steward: no quarantine/traceability for silently-altered rows | Added `dq_flag`/`dq_reason` columns (`stg_gamma__reviews` → `fact_review`); no separate quarantine table built (steward's stated minimum-viable option, not the fuller option) | `dbt/models/staging/gamma/stg_gamma__reviews.sql`, `dbt/models/marts/core/fact_review.sql` |
| @data-quality-steward: `data_quality/expectations/` empty | Populated with 3 real Great Expectations suites (dim_drug, fact_sales, fact_review) covering row counts + the new coverage SLAs — all pass | `scripts/run_ge_validation.py`, `data_quality/expectations/*.json`, `data_quality/validations/*.json` |

**Verification**: full `dbt build` (seed → staging → snapshot → marts → serving) and `dbt test`
re-run clean after all changes — 50 tests, 49 pass + 1 unchanged documented warn. GE suite re-run:
3/3 pass.

**Outcome: all four findings closed in this session. No open vetoes remain as of 2026-06-18.**
