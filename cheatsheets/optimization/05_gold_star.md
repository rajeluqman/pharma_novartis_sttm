# Layer 05 — Gold / Star Schema Optimization
> dbt marts: `dim_drug.sql` (SCD2 conformed), `dim_date.sql` (SCD0), `dim_condition.sql` (SCD1),
> `fact_sales.sql`, `fact_review.sql`, and the SCD2 source `snapshots/snap_beta_ndc.sql`.
> Kimball star = system of record (ADR-001). See [00_INDEX.md](00_INDEX.md) for card format.

---

### GLD-01 ★ — Content-hash surrogate key, not an INT sequence  [✅ DONE]
- **Junior mistake:** `IDENTITY` / sequence / `row_number()` integer surrogate keys on dims and facts.
- **Why it bites:** A sequence is **non-deterministic** — reload the same data and every key changes, so facts built on a prior run no longer join. It also can't be generated in parallel and leaks load order. It quietly breaks idempotency (the whole point of full rebuilds, GLD-05).
- **Optimized (this repo):** `dbt_utils.generate_surrogate_key([...])` hashes the natural business key → deterministic, reproducible, parallel-safe. `dim_drug.sql:30,51`, `fact_sales.sql:24`, `fact_review.sql:42`
- **Business one-liner:** "Rebuild any day from scratch and every key is identical — historical joins never silently break."
- **Soundbite:** *"A hash key is a function of the data; a sequence is a function of when you happened to load it."*
- **Related:** BRZ-04, GLD-05, PUB-02 · orchestration T010 (idempotency thread)

### GLD-02 ★ — Don't overload one column with two meanings  [✅ DONE]
- **Junior mistake:** Reuse `match_confidence` to also signal "this is a seed/category row" (e.g. confidence = `'seed'`).
- **Why it bites:** The coverage KPI is computed over `match_confidence` — mixing row *provenance* into a *quality* column corrupts the KPI denominator and forces every consumer to add a `WHERE` filter to get an honest number.
- **Optimized (this repo):** provenance lives in `drug_member_type` (`ndc_product` vs `atc_category`); `match_confidence` is NULL for seed rows, so the KPI ("where match_confidence is not null") is correct by construction. `dim_drug.sql:2-11,31,52,61`
- **Business one-liner:** "Each column means exactly one thing, so the quality metric is right without anyone having to remember a filter."
- **Soundbite:** *"One column, one meaning. The moment a field means two things, every query is a trap."*

### GLD-03 — Conformed dimension serving two grains  [✅ DONE]
- **Junior mistake:** Build two separate dims (`dim_ndc_product` + `dim_atc_category`) because the sources differ.
- **Why it bites:** Facts at different grains can't conform to a shared dimension, so BI can't roll product-level and category-level analytics into one view.
- **Optimized (this repo):** one `dim_drug` with both member types via `UNION ALL`, distinguished by `drug_member_type`; Alpha's category-grain `fact_sales` and Beta/Gamma's product-grain facts both find an honest join target. `dim_drug.sql:28-71`
- **Business one-liner:** "Sales-by-category and reviews-by-product share one drug dimension, so the business sees one consistent picture."
- **Soundbite:** *"Conform the dimension once; let every fact, at every grain, hang off it."*

### GLD-04 ★ — SCD2 `check` strategy when there's no reliable `updated_at`  [✅ DONE]
- **Junior mistake:** Use dbt snapshot `strategy='timestamp'` on an `updated_at`-style field.
- **Why it bites:** openFDA has no reliable update timestamp — a timestamp strategy either misses real changes or fabricates history from a field that doesn't move.
- **Optimized (this repo):** `strategy='check'` diffing the actual business columns (`generic_name`, `pharm_class`, `marketing_*`, …) — history is created only when content truly changes. `dbt/snapshots/snap_beta_ndc.sql:9-13`
- **Business one-liner:** "Product-history tracking reacts to real changes in the data, not to a timestamp the source doesn't maintain."
- **Soundbite:** *"Pick the SCD strategy the source can actually honor — `check` when there's no trustworthy clock."*

### GLD-05 ★ — Full deterministic rebuild over `incremental` on object storage  [✅ DONE]
- **Junior mistake:** Cargo-cult `materialized='incremental'` onto facts because "incremental is the performant default".
- **Why it bites:** On an `external` S3 location there's **no atomic rename**, so dbt-duckdb's incremental read-modify-write can't be made atomic or replay-safe; it must read `{{ this }}`'s prior state, which isn't guaranteed to exist on a cold ephemeral worker. You get non-atomic, non-reproducible facts.
- **Optimized (this repo):** facts are small and surrogate keys are content-hashed, so a **full deterministic rebuild** is cheap, atomic, and idempotent — the right call for this storage model. `fact_sales.sql:4-9`, `fact_review.sql:10-11`
- **Business one-liner:** "We chose the rebuild strategy that's safe on cloud storage — every run is atomic and reproducible, not a fragile patch-in-place."
- **Soundbite:** *"Incremental is an optimization, not a religion. On object storage with hashed keys, the full rebuild is both simpler and safer."*
- **Related:** GLD-01, BRZ-04, PUB-01, PUB-02 · orchestration T010 (idempotency + atomicity threads)

### GLD-06 ★ — Collapse many names to ONE drug_sk to protect grain  [✅ DONE]
- **Junior mistake:** Join `fact_review` to the drug dimension directly on drug name.
- **Why it bites:** Many NDC products share one generic/brand name (different labelers/packages) → the join **fans out** and the fact explodes past its declared "1 row = 1 review" grain, double-counting reviews.
- **Optimized (this repo):** build a `name_norm → min(drug_sk)` map (one representative SK per normalized name) and join through it, so each review resolves to exactly one drug_sk. `fact_review.sql:3-5,20-39,52`
- **Business one-liner:** "Review counts stay correct even though one drug name maps to many product records — no accidental double-counting."
- **Soundbite:** *"Protect the grain at the join. A fan-out is silent inflation of every metric above it."*

### GLD-07 — Honest partial match: null FK, tracked, traceable  [✅ DONE]
- **Junior mistake:** Drop reviews whose drug/condition can't be matched, or assign a default "Unknown" key.
- **Why it bites:** Dropping loses real signal (rating is still valid); a fake default pollutes analytics and hides the gap.
- **Optimized (this repo):** unmatched → `drug_sk`/`condition_sk` NULL, retained, with `dq_flag`/`dq_reason` so a null condition is traceable to "scrubbed garbage" vs "source had none" — coverage tracked as a KPI, not hidden. `fact_review.sql:5-9,44-49`
- **Business one-liner:** "Reviews we can't fully classify are kept and counted honestly, not deleted or faked."
- **Soundbite:** *"Null with a reason beats a confident default. Keep the row, track the gap."*
- **Related:** XWK-06, SIL-05, GLD-09, DQ-02 (honest-coverage thread)

### GLD-08 — `date_spine` for dim_date, not hand-typed or per-run dates  [✅ DONE]
- **Junior mistake:** Generate the date dimension with a Python loop, hardcode rows, or recompute it per run.
- **Why it bites:** Error-prone, hard to extend the range, and inconsistent across engines.
- **Optimized (this repo):** `dbt_utils.date_spine(...)` generates the conformed range declaratively (2008–2019, covering both fact sources), SCD0 static. `dim_date.sql:6-12`
- **Business one-liner:** "The calendar dimension is generated declaratively and consistently — extend the range by changing two dates."
- **Soundbite:** *"Don't hand-roll a calendar. Declare its bounds and let the macro build it."*

### GLD-09 — LEFT JOIN facts to dims; never silently drop a fact  [✅ DONE]
- **Junior mistake:** `INNER JOIN` facts to dimensions for "clean" keys.
- **Why it bites:** Any fact whose dimension lookup misses is silently dropped — measures (units sold, reviews) vanish and totals are quietly wrong.
- **Optimized (this repo):** facts `left join` dims, leaving a NULL FK when a lookup misses, so the measure is preserved and the gap is visible. `fact_sales.sql:30-31`, `fact_review.sql:52-54`
- **Business one-liner:** "We never lose a sale or a review just because a lookup didn't resolve — totals stay complete."
- **Soundbite:** *"Facts are sacred. Keep every measure; let the missing key be a null, not a deletion."*
