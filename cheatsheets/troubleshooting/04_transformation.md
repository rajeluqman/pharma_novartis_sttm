# Phase 04 — Transformation (DuckDB / dbt) — Incident Cards  [DRILL-READY]

> Checklist step 4 of 8 (see `00_INDEX.md` numbering note). Stack-honest: NO Spark — skew→
> "cardinality blowup", shuffle→`temp_directory` spill (see translation table in `00_INDEX.md`).
> Scope: `scripts/load_bronze.py`, `dbt/models/staging/*`, `dbt/models/intermediate/int_drug_crosswalk.sql`.
> Diagnostic backbone: row-count reconciliation landing→bronze→silver (`load_bronze.py:80-83`).
> **C3 cleared 2026-06-19** — full `dbt build` (PASS=63/WARN=1/ERROR=0) ran against local MinIO
> `gym-lake`; `dim_drug`=133654 landed through this exact model. @senior-data-engineer
> independently re-verified the T-XFM-02/03 citations against this run. **Drill-ready up to L10.**
> Owned by @incident-responder · Governed by ADR-006 / ADR-006-A1.

---

### T-XFM-01 — `UNION ALL` aligns by POSITION, not name (silent column swap)  ★  [🟡 APPLICABLE]
- Symptom         : bronze `drug_reviews` row count looks fine, but a column holds wrong values / downstream nulls.
- Diagnosis       : compare the column ORDER of the two gamma files, not just the count; `DESCRIBE SELECT * FROM read_csv_auto('<train>')` vs test.
- Root cause      : `UNION ALL` matches columns by position; if train/test drift in order (same count), data lands in the wrong column silently.
- Fix / Recovery  : project explicit, named column lists on each side before the `UNION ALL`; re-run bronze for `<date>`.
- Evidence        : `scripts/load_bronze.py:65-72` — train + test combined by positional `UNION ALL`, no named projection. Guard: name the columns. Tradeoff: more verbose SQL, removes a silent-corruption class.
- ⚠️ Junior mistake : assuming `UNION ALL` matches by column NAME — it's positional; a reordered source corrupts silently.
- 🎤 Soundbite      : "I never positional-`UNION ALL` two sources I don't control — I project named columns, because a reordered upstream file aligns silently into the wrong column."

---

### T-XFM-02 — Crosswalk `cross join` cardinality blowup → DuckDB OOM  ★  [🟡 APPLICABLE]
- Symptom         : silver build hangs or DuckDB OOMs / spills; one step balloons memory.
- Diagnosis       : estimate rows = NDC count (~133k) × ATC seed rows; this is the #1 OOM on a single-process `:memory:` engine. Check `memory_limit` / `temp_directory`.
- Root cause      : `cross join` is N×M; on DuckDB's single-process ephemeral catalog there is no cluster to absorb it (NOT "skew" — there are no executors here).
- Fix / Recovery  : pre-filter ATC candidates, or set a `memory_limit` + `temp_directory` to spill; bound the seed growth.
- Evidence        : `dbt/models/intermediate/int_drug_crosswalk.sql:36-57` (`cross join atc`) materialized through the ephemeral catalog `scripts/load_bronze.py:37` (`duckdb.connect(":memory:")`). Tradeoff: pre-filtering adds logic but caps the blowup.
- ⚠️ Junior mistake : "it's just a join" — a `cross join` is a cartesian product; on single-node DuckDB that's the first thing that OOMs.
- 🎤 Soundbite      : "On a single-process DuckDB engine the failure isn't skew, it's cardinality — a cross join against a growing seed is the OOM I watch for, not a shuffle."

---

### T-XFM-03 — Silent data drop on an inner join (use LEFT + coalesce)  ★  [✅ HARDENED]
- Symptom         : (prevented) — unmatched products would vanish and the coverage KPI become uncomputable.
- Diagnosis       : reconcile NDC input count vs crosswalk output count; they MUST match (unmatched are kept, not dropped).
- Root cause      : N/A — documents the guard that turns "silent loss" into "measured coverage".
- Fix / Recovery  : keep the `left join` + `coalesce(...,'unmatched')` pattern; coverage is a DQD KPI (ADR-003), not 100%.
- Evidence        : `dbt/models/intermediate/int_drug_crosswalk.sql:88` (`left join ranked`) + `:86` (`coalesce(ranked.match_confidence,'unmatched')`). ✅ HARDENED.
- ⚠️ Junior mistake : `inner join` here — every unmatched product disappears with NO error, and you can't even measure the coverage you lost.
- 🎤 Soundbite      : "I left-join the crosswalk and label the misses 'unmatched' — an inner join would silently drop coverage, and you can't fix a number you've already deleted."

---

### T-XFM-04 — Confident-wrong fuzzy match on combination products  [✅ HARDENED]
- Symptom         : (prevented) — a 2-ingredient drug tagged with ONE ingredient's ATC = a confident wrong answer (worse than unmatched).
- Diagnosis       : check `is_combination_product`; combos must fall to `combination_unverified`, never `fuzzy`.
- Root cause      : N/A — documents the exclusion guard.
- Fix / Recovery  : keep combination products out of the fuzzy tier.
- Evidence        : `dbt/models/intermediate/int_drug_crosswalk.sql:47-54` (combination excluded from fuzzy → `combination_unverified`). ✅ HARDENED.
- ⚠️ Junior mistake : fuzzy-matching a combination drug to one ingredient's ATC — a *confident wrong* label is worse than admitting "unmatched".
- 🎤 Soundbite      : "A confidently wrong match is worse than a blank — combination products are excluded from fuzzy matching so they're flagged unverified, not mislabelled."

---

### T-XFM-05 — Non-deterministic tie-break (crosswalk drifts run-to-run)  [✅ HARDENED for `int_drug_crosswalk`; ⚠️ same gap found UNGUARDED elsewhere 2026-06-20 — see `08_postmortem_recovery.md` `P-PMR-07`]
- Symptom         : (prevented, in THIS file) — identical inputs produce different crosswalk results across runs; breaks idempotency/reproducibility.
- Diagnosis       : run the build twice on the same input; the output must be byte-identical.
- Root cause      : N/A — documents the deterministic ordering guard.
- Fix / Recovery  : keep the secondary `order by atc_code` in the tie-break window.
- Evidence        : `dbt/models/intermediate/int_drug_crosswalk.sql:65-74` (`row_number() ... order by <tier>, atc_code`). ✅ HARDENED **for this one model**.
- ⚠️ Junior mistake : ranking with only the tier and no deterministic secondary key — two seed rows at the same tier flip between runs, so the "same" pipeline isn't reproducible. **2026-06-20: this exact mistake was found, live, in a sibling model** — `dbt/models/staging/beta/stg_beta__ndc.sql:20-23` dedupes with `row_number() over (partition by product_ndc order by marketing_start_date desc)` and NO secondary key. A live MinIO rep proved real `(product_ndc, marketing_start_date)` ties exist (1,317 groups / 2,972 rows in the actual Beta bronze data) and that re-running the identical pipeline twice produced two different `dim_drug` row counts (133,654 vs 133,758) because the tie-break flip cascades into the SCD2 snapshot reading a false "change." Don't assume this card's guard generalizes — it was checked for ONE model, not audited across the codebase. Full writeup: `08_postmortem_recovery.md` `P-PMR-07`.
- 🎤 Soundbite      : "Every tie-break needs a deterministic secondary key — without `order by atc_code` the crosswalk isn't reproducible, and a non-reproducible pipeline can't be idempotent. I've since found the same missing-tie-break pattern unguarded in `stg_beta__ndc` too — fixing one instance of a bug class doesn't mean you've fixed the class."

---

### T-XFM-06 — `read_json_auto` type inference drift  [🟡 APPLICABLE]
- Symptom         : downstream type error, OR a field silently changes type and breaks a cast later.
- Diagnosis       : reconcile bronze count + spot-check inferred schema vs an expected contract; localize via `load_bronze.py:80-83`.
- Root cause      : `read_json_auto` infers types per-run; an upstream NDC field change shifts the inferred schema with no contract to catch it.
- Fix / Recovery  : pin expected columns/types at the bronze read; quarantine on drift.
- Evidence        : `scripts/load_bronze.py:55-59` (`read_json_auto`, no schema assertion). Guard placement: explicit `columns=` / a contract check. Tradeoff: less "just works", but drift becomes loud.
- ⚠️ Junior mistake : trusting auto-inference as a contract — it's a convenience, not a guarantee.
- 🎤 Soundbite      : "Auto-inference is great for prototyping and dangerous as a contract — for an external source I pin the schema so drift fails loudly instead of casting wrong downstream."

---

## Phase tally
✅ HARDENED: 3 · 🟡 APPLICABLE: 3 · ⚪ N/A: 0 — **6 cards** (drill-ready, C3 cleared).
Reconciliation anchor: `scripts/load_bronze.py:80-83`. MinIO loop evidence: this dbt build.
