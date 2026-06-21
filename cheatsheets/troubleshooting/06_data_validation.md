# Phase 06 — Data Validation (Great Expectations) — Incident Cards  [DRILL-READY]

> Checklist step 6 of 8 (see `00_INDEX.md`). This is the LAYER THAT SHOULD CATCH the silent
> failures from ingestion/transform (the "KPI -12%" incident). Scope: `scripts/run_ge_validation.py`,
> `data_quality/expectations/*.json`.
> **C3 cleared 2026-06-19** — `run_ge_validation.py` ran against `gold/_current/` on local MinIO
> `gym-lake` straight after a real `publish_gold.py` run: `OVERALL: PASS` (dim_drug_suite,
> fact_sales_suite, fact_review_suite). @senior-data-engineer independently re-ran the suite and
> confirmed it reads fresh `s3://` parquet every call (no cache to go stale). **Drill-ready up to L10.**
> Owned by @incident-responder · Governed by ADR-006 / ADR-006-A1.

---

### V-DQ-01 — Fixed `==` row count on an SCD2 dimension (green once, red forever)  ★  [✅ HARDENED]
- Symptom         : (prevented) — a `==` count on `dim_drug` would pass the first run then fail every run after a snapshot, a false alarm that trains you to ignore DQ.
- Diagnosis       : know which tables GROW (SCD2 history accumulates) vs are deterministic; pick the matching expectation.
- Root cause      : N/A — documents the correct expectation choice.
- Fix / Recovery  : use a floor+ceiling range for growing dims, not equality.
- Evidence        : `scripts/run_ge_validation.py:43-48` — `ExpectTableRowCountToBeBetween(133654, 200000)` with the comment explaining a fixed `==` is "wrong by construction" for SCD2. ✅ HARDENED.
- ⚠️ Junior mistake : `ExpectTableRowCountToEqual` on an SCD2 dim — passes once, then red forever as history grows; the team learns to mute the suite.
- 🎤 Soundbite      : "I match the expectation to the table's nature — an SCD2 dim grows, so I bound its row count between a floor and a ceiling; a fixed equality there is a false alarm by construction."

---

### V-DQ-02 — Resolution-rate SLA gate (the silent-drop catcher)  ★  [✅ HARDENED]
- Symptom         : (catches) — a coverage drop (e.g. crosswalk match-rate 72%→60%) that a not-null check would miss because the column is "mostly not null".
- Diagnosis       : gate on the PROPORTION of resolved FKs, not just presence; this is the gate that turns the "KPI -12%" incident from silent to loud.
- Root cause      : N/A — documents the distribution gate.
- Fix / Recovery  : keep proportion-non-null SLAs on `drug_sk`/`condition_sk`.
- Evidence        : `scripts/run_ge_validation.py:73-80` — `drug_sk >= 0.65`, `condition_sk >= 0.90` proportion-non-null (the DQD coverage SLAs). ✅ HARDENED.
- ⚠️ Junior mistake : only `not_null` (binary) on an FK — you miss a coverage DROP that's still "mostly populated"; the dashboard quietly degrades.
- 🎤 Soundbite      : "Not-null is binary; coverage is a distribution — I gate the FK resolution RATE, so a crosswalk that quietly drops from 72% to 60% trips the suite instead of the dashboard."

---

### V-DQ-03 — Exact-count gate on deterministic facts  [✅ HARDENED]
- Symptom         : (catches) — a silent row gain/loss in a full-rebuild fact.
- Diagnosis       : facts are deterministic full rebuilds (ADR-005), so `==` is CORRECT here — the opposite call from V-DQ-01.
- Root cause      : N/A — documents the correct expectation choice for deterministic tables.
- Fix / Recovery  : keep `==` on facts; keep range on growing dims.
- Evidence        : `scripts/run_ge_validation.py:59` (`fact_sales == 16848`), `:72` (`fact_review == 215063`). ✅ HARDENED.
- ⚠️ Junior mistake : applying ONE rule everywhere — `==` on a growing dim (V-DQ-01) OR a loose range on a deterministic fact (misses a real drift). Know which is which.
- 🎤 Soundbite      : "I use exact counts on deterministic full-rebuild facts and ranges on growing SCD2 dims — the same row-count test is right on one and wrong on the other."

---

### V-DQ-04 — GE runs but doesn't GATE the pipeline (validation theater)  [🟡 APPLICABLE]
- Symptom         : a suite FAILS but Gold still publishes / the veneer still serves bad data.
- Diagnosis       : check whether the DAG fails the run on `run_ge_validation.py`'s overall result, or just logs it.
- Root cause      : validation that doesn't block = theater; the failed check informs no one in time.
- Fix / Recovery  : wire GE as a hard gate BEFORE `publish_gold.py` in the DAG; non-zero exit must stop the publish.
- Evidence        : `scripts/run_ge_validation.py:127` prints `OVERALL: PASS|FAIL` and `:110` tracks `overall_pass` — but exit status / DAG dependency must enforce it. Placement: DAG task ordering GE→publish + fail-on-FAIL. Tradeoff: a flaky suite can block a good run — so the suite must be trustworthy first.
- ⚠️ Junior mistake : running GE and reading the report, but not failing the pipeline on it — bad data ships while a red report sits unread.
- 🎤 Soundbite      : "A validation suite that doesn't stop the publish is theater — GE gates the pipeline before the pointer swap, so a failed expectation blocks serving, not just logs."

---

### V-DQ-05 — Gold-only validation (ingestion incident slips past)  [🟡 APPLICABLE]
- Symptom         : an empty/0-byte source (the I1 incident) silently zeroes everything, and the FIRST check is at Gold — far too late to localize cheaply.
- Diagnosis       : where is the earliest expectation? Today GE is Gold-layer only.
- Root cause      : no landing/bronze pre-gate; a `row_count > 0` (≈136k for Beta) at bronze would fail fast at the source.
- Fix / Recovery  : add a bronze GE suite (row_count>0 + expected magnitude per source) upstream of transform.
- Evidence        : `scripts/run_ge_validation.py:2` (docstring: "Gold layer" suite only). Placement: a new bronze suite. Tradeoff: more suites to maintain vs catching source failures at the cheapest point.
- ⚠️ Junior mistake : validating only the final layer — an empty source craters every layer above it before the single Gold check ever runs.
- 🎤 Soundbite      : "Validate early AND late — a Gold-only suite catches the 0-byte source incident long after it's cheap to localize; a bronze row-count floor fails it at the door."

---

## Phase tally
✅ HARDENED: 3 · 🟡 APPLICABLE: 2 · ⚪ N/A: 0 — **5 cards** (drill-ready, C3 cleared).
V-DQ-02 + V-DQ-05 are the direct catchers for the Ingestion pilot incident (KPI -12% / 0-byte Beta).
