# Layer 03 — Silver (Enrich) Optimization
> dbt staging models: `stg_alpha__sales.sql`, `stg_beta__ndc.sql`, `stg_gamma__reviews.sql`.
> Job of this layer: clean + conform divergent sources into one shape, cheaply and reproducibly.
> See [00_INDEX.md](00_INDEX.md) for card format and the cross-layer junior-mistakes table.

---

### SIL-01 ★ — Dedupe with a window function, not `DISTINCT`/`GROUP BY`  [✅ DONE]
- **Junior mistake:** `SELECT DISTINCT ...` or `GROUP BY` every column to "remove duplicates".
- **Why it bites:** `DISTINCT` can't express *which* row to keep — you want the **latest** per key, not any row. `GROUP BY all columns` silently breaks the moment a new column with varying values is added, and can't pick a representative.
- **Optimized (this repo):** `row_number() over (partition by product_ndc order by marketing_start_date desc)`, keep `rn = 1` → exactly one row per NDC, deterministically the most recent. `dbt/models/staging/beta/stg_beta__ndc.sql:20-23,40`
- **Business one-liner:** "We always carry the *current* version of each product — not a random one — so the master data downstream is trustworthy."
- **Soundbite:** *"DISTINCT removes duplicates; a window function chooses the survivor. I needed to choose."*

### SIL-02 ★ — Staging as `view`, not `table`  [✅ DONE]
- **Junior mistake:** Materialize every staging model as a `table` because "tables are faster".
- **Why it bites:** Pays storage for data that's a thin transform of Bronze, and goes **stale** the moment Bronze changes — you're now maintaining a copy. Slower full rebuilds for no query benefit at this layer.
- **Optimized (this repo):** all three staging models are `materialized='view'` — always reflect current Bronze, zero storage, the engine pushes predicates straight through to the parquet read. `stg_beta__ndc.sql:6`, `stg_alpha__sales.sql:4`, `stg_gamma__reviews.sql:13`
- **Business one-liner:** "The clean layer is always live and costs nothing to store — no stale copies to babysit."
- **Soundbite:** *"Materialize where a query pays for it. Staging is a lens, not a copy."*

### SIL-03 — Filter junk at the earliest boundary  [✅ DONE]
- **Junior mistake:** Carry null-key / unusable rows downstream and filter them "later, in the mart".
- **Why it bites:** Every downstream model then re-pays to scan and re-filter the same garbage, and the bad rows leak into joins before someone remembers to exclude them.
- **Optimized (this repo):** `where product_ndc is not null` (beta `:25`), `where "drugName" is not null` (gamma `:27`) — drop unusable rows at the staging gate.
- **Business one-liner:** "Bad rows are stopped at the door, not chased through the whole pipeline."
- **Soundbite:** *"Filter at the boundary closest to the source. Garbage shouldn't get a passport."*

### SIL-04 ★ — Flatten nested API arrays at the boundary  [✅ DONE]
- **Junior mistake:** Keep the raw nested arrays openFDA returns (`pharm_class[]`, `route[]`) in the model and "deal with it downstream".
- **Why it bites:** Nested types don't port across engines (DuckDB ↔ Snowflake), and every downstream match/join has to special-case array logic — the crosswalk string-match becomes engine-specific and brittle.
- **Optimized (this repo):** `array_to_string(pharm_class, '; ')`, `route[1]` → one portable delimited string, so the crosswalk match is a plain string op everywhere. `stg_beta__ndc.sql:3-4,32-33`
- **Business one-liner:** "Source quirks are normalized once, at entry — every later step works the same on any engine."
- **Soundbite:** *"Absorb the source's shape at the edge so the core stays portable."*

### SIL-05 ★ — Scrub-and-flag, never silently drop  [✅ DONE]
- **Junior mistake:** `DELETE`/filter out rows whose `condition` is a scrape artifact (`"74</span> users found..."`), or leave the HTML garbage in.
- **Why it bites:** Dropping the row throws away the *valid* signal it still carries (the rating and drug are fine); leaving the garbage poisons `dim_condition`. Either way there's no audit trail of what was changed.
- **Optimized (this repo):** null only the defective field, keep the row, and stamp `dq_flag` + `dq_reason` so the scrub is traceable downstream — "scrubbed garbage" is distinguishable from "source genuinely had no condition". `stg_gamma__reviews.sql:19-21` (carried into `fact_review.sql:7-9,48-49`)
- **Business one-liner:** "We fix the bad cell without losing the good data in the same row — and every fix is auditable."
- **Soundbite:** *"Don't delete the patient because one test result is corrupt. Null the cell, flag it, keep the rest."*
- **Related:** GLD-07, DQ-04, DQ-05 (honest-coverage thread)

### SIL-06 ★ — Profile the whole column before writing a cleaning rule  [✅ DONE]
- **Junior mistake:** See one bad value, write a regex for that exact shape, assume the defect is handled.
- **Why it bites:** Other anomaly shapes (HTML entities, numeric-only, empty) slip through uncounted; you've "cleaned" a problem you never sized.
- **Optimized (this repo):** profiled the full 215,063-row `condition` column for *all* anomaly shapes → confirmed the HTML-tag signature is the **complete** 1,171-row defect (no entities, no numeric-only, no empties beyond it). The fix is scoped to a measured population, not one example. `stg_gamma__reviews.sql:3-11`
- **Business one-liner:** "We quantified the data defect before fixing it, so we know the fix is complete — not just covering the first symptom we saw."
- **Soundbite:** *"'1,171 rows, full stop' beats 'rows matching the regex I happened to write.'"*

### SIL-07 — Apply business rules at the layer that owns them  [✅ DONE]
- **Junior mistake:** Let negative `units_sold` flow into facts, or "fix" it in the BI tool.
- **Why it bites:** Every consumer re-implements the rule (inconsistently), and the fact table reports nonsense until they do.
- **Optimized (this repo):** `case when units_sold < 0 then 0 else units_sold end` clamped at Silver, once, for everyone. `stg_alpha__sales.sql:36`
- **Business one-liner:** "A business rule is enforced once, centrally — not re-invented in every dashboard."
- **Soundbite:** *"Fix it once at the source of truth, not N times at the points of consumption."*

### SIL-08 — Unpivot wide→long at staging  [✅ DONE]
- **Junior mistake:** Keep Alpha's 8 ATC columns wide and model facts per-column (8 near-identical models).
- **Why it bites:** Adding a 9th ATC category means editing every downstream model; the grain is implicit in column names instead of being a real `atc_code` dimension key.
- **Optimized (this repo):** unpivot the 8 columns into `(sale_date, atc_code, units_sold)` long form at staging, so the fact grain is explicit and extensible. `stg_alpha__sales.sql:15-31`
- **Business one-liner:** "Adding a new product category is a data change, not a code change across eight places."
- **Soundbite:** *"Long-and-keyed beats wide-and-positional every time you expect the source to grow."*
