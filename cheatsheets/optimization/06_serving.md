# Layer 06 — Serving / OBT Optimization
> dbt marts: `obt_sales_wide.sql`, `obt_review_wide.sql` — One Big Table, derived from the star
> for BI read performance (ADR-001). NOT a source of truth. See [00_INDEX.md](00_INDEX.md).

---

### SRV-01 ★ — Target-aware materialization (warehouse vs lakehouse) in one model  [✅ DONE]
- **Junior mistake:** One `config(materialized=...)` for every environment.
- **Why it bites:** A single config can't be right for both — `external` parquet is correct on DuckDB/S3 but invalid on Snowflake, and a Snowflake `table` with `cluster_by` is meaningless on DuckDB.
- **Optimized (this repo):** a `{% if target.type == 'snowflake' %}` branch picks `table + cluster_by` for the warehouse and `external` (S3 parquet) for the lakehouse — same model, right physical layout per engine. `obt_sales_wide.sql:4-8`, `obt_review_wide.sql:5-9`
- **Business one-liner:** "The same serving model is laid out optimally for whichever platform reads it — no second copy to maintain."
- **Soundbite:** *"One model, two physical strategies. The config adapts to the engine; the logic doesn't move."*
- **Related:** INF-03, INF-06, GLD-08 (portability thread)

### SRV-02 — Cluster on the columns BI actually filters by  [✅ DONE]
- **Junior mistake:** No clustering, or clustering on a high-cardinality key like a surrogate id.
- **Why it bites:** Dashboards that filter by period/category then scan the whole table — slow queries and higher warehouse cost.
- **Optimized (this repo):** `cluster_by=['year','atc_code']` for sales, `['year']` for reviews — the dimensions the dashboards slice on. `obt_sales_wide.sql:5`, `obt_review_wide.sql:6`
- **Business one-liner:** "Dashboards read only the slices they ask for, so reports are fast and the warehouse bill stays low."
- **Soundbite:** *"Cluster by how the data is queried, not by how it's keyed."*

### SRV-03 — OBT is derived from the star, explicitly not a source of truth  [✅ DONE]
- **Junior mistake:** Let the convenient wide table become where people write fixes and build new logic.
- **Why it bites:** You end up with two sources of truth (star and OBT) that drift, and nobody knows which number is right.
- **Optimized (this repo):** both OBTs are headed "derived from the star… NOT a source of truth" and are rebuilt from the facts/dims every run. `obt_sales_wide.sql:1`, `obt_review_wide.sql:1`
- **Business one-liner:** "The wide reporting table is always rebuilt from the governed star, so there's exactly one version of the truth."
- **Soundbite:** *"The OBT is a projection of the star, never a parallel universe."*

### SRV-04 — Pre-join the star into a wide table for read speed  [✅ DONE]
- **Junior mistake:** Leave facts and dims normalized and make the BI tool join them at query time.
- **Why it bites:** Every dashboard re-pays the star-join cost on every refresh, and non-technical users get joins wrong.
- **Optimized (this repo):** the OBT pre-joins fact + dims into a flat, query-ready shape so BI just filters and aggregates. `obt_sales_wide.sql:10-22`, `obt_review_wide.sql:11-25`
- **Business one-liner:** "Reporting reads one ready-made wide table instead of re-joining the model on every dashboard load."
- **Soundbite:** *"Pay the join once at build time, not on every dashboard refresh."*

### SRV-05 ★ — Join type chosen by whether the key can be null — and documented  [✅ DONE]
- **Junior mistake:** Use the same join type (usually `INNER`) for every fact→dim join in serving.
- **Why it bites:** A blanket inner join silently drops every review whose `drug_sk` is null under the partial-match policy — quietly undercounting the patient-voice metrics.
- **Optimized (this repo):** `obt_sales_wide` uses `JOIN` because `fact_sales.drug_sk` *always* resolves to a category seed (documented), while `obt_review_wide` uses `LEFT JOIN` on drug/condition because those can be null by design. `obt_sales_wide.sql:2,20-22` vs `obt_review_wide.sql:2-3,24-25`
- **Business one-liner:** "We keep every review even when a drug couldn't be matched, so patient-voice numbers stay complete and honest."
- **Soundbite:** *"Inner vs left isn't a style choice — it's a statement about whether a missing key is allowed."*
- **Related:** GLD-07, GLD-09, XWK-06 (honest-coverage thread)
