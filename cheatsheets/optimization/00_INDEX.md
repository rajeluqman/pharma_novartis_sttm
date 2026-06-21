# DE Optimization Library — Index
> Per-layer optimization catalog for the Helvetia Pharma enVision pipeline.
> Owned by **@optimization-librarian**. Companion to the orchestration catalog
> `cheatsheets/performance/airflow_optimization_library.md`.
>
> **Purpose:** turn the real, already-optimized code in this repo into interview ammunition —
> every technique paired with the **junior mistake** it avoids, proven at a `file:line`.
> These junior mistakes are not invented: most are the actual Phase-4 review findings
> (see the `DEBATE_LOG_phase_4.md` references inside the model comments) that hardened the code.

## How to use this in an interview
1. **Executive summary first** — lead with the `Business one-liner` (what it buys the business).
2. **Contrast** — "a junior would do X; that bites because Y; here's what I did" (`Junior mistake` → `Why it bites` → `Optimized`).
3. **Prove it** — cite the `file:line`. Close with the one-line `Soundbite`.
4. For breadth, drill the **Top Junior Mistakes** table below the morning of the interview.

## Card format (every entry)
```
### <CARD-ID> — <technique>  [✅ DONE | 🟡 APPLICABLE]
- Junior mistake : the naive/common wrong way
- Why it bites   : the concrete failure mode
- Optimized      : what this repo does + file:line
- Business       : executive-summary one-liner
- Soundbite      : one quotable interview line
```

## Legend
✅ DONE = in the code now (file:line) · 🟡 APPLICABLE = sensible next step · ★ = headline card

---

## Layer map (pipeline order)

| # | Layer | File | Status | Cards | Headline technique |
|---|-------|------|--------|-------|--------------------|
| 01 | Ingestion | [01_ingestion.md](01_ingestion.md) | ✅ | 6 | immutable write-once landing; hard API timeout; stream zip in-memory |
| 02 | Bronze (load) | [02_bronze.md](02_bronze.md) | ✅ | 7 | set-based `COPY`, per-date overwrite, `load_ts`/`source_file` lineage |
| 03 | Silver (Enrich) | [03_silver.md](03_silver.md) | ✅ | 8 | dedupe via window fn; `view` not table; traceable DQ scrub |
| 04 | Crosswalk (Intermediate) | [04_crosswalk.md](04_crosswalk.md) | ✅ | 7 | exclude combos from fuzzy (confident-wrong > unmatched); deterministic tie-break |
| 05 | Gold / Star | [05_gold_star.md](05_gold_star.md) | ✅ | 9 | content-hash SK; SCD2 `check` strategy; full deterministic rebuild on S3 |
| 06 | Serving / OBT | [06_serving.md](06_serving.md) | ✅ | 5 | target-aware config (`cluster_by` Snowflake vs `external` DuckDB) |
| 07 | Publish / Pointer-swap | [07_publish.md](07_publish.md) | ✅ | 5 | verify-then-swap atomic `_current` pointer |
| 08 | Data Quality | [08_dq.md](08_dq.md) | ✅ | 8 | coverage as a KPI distribution, not a 100% gate |
| 09 | Shared infra / Portability | [09_shared_infra.md](09_shared_infra.md) | ✅ | 7 | one env-driven httpfs contract; cross-dialect macros; credential_chain |
| 11 | Orchestration (Airflow) | [../performance/airflow_optimization_library.md](../performance/airflow_optimization_library.md) | ✅ | 100 | decouple orchestration from execution; idempotency; SLA |

**Layer cards total: 62** across layers 01–09 (+ 100 orchestration techniques). All ✅ cite a verified `file:line`.

### Relationship to the orchestration library (intentional overlap, not duplication)
A few principles appear in **both** this layer catalog and `airflow_optimization_library.md`,
deliberately — that is the OOP-reuse thesis: one principle, re-instantiated per altitude.
They are cross-referenced, never re-counted:

| Principle | Orchestration (DAG altitude) | Layer (code altitude) |
|-----------|------------------------------|------------------------|
| Idempotency / safe re-run | T010 (per-date overwrite contract) | BRZ-04, ING-05, GLD-05 |
| Set-based bulk load | T063 (native `COPY`) | BRZ-01 |
| Decouple orchestration from execution | T009 (subprocess) | BRZ-05 (ephemeral compute) |
| Timeout / fail-fast | T051 (`execution_timeout`) | ING-03 (network timeout) |
| dbt split by layer | T068 (selectors) | the 03/04/05/06 layer split itself |

When the @optimization-librarian counts coverage, a code-altitude card and its DAG-altitude
twin are **one technique seen twice**, not two techniques.

---

## Top Junior Mistakes — 5-minute drill (across all layers)

| # | A junior does… | Why it bites | This repo does instead | Card |
|---|----------------|--------------|------------------------|------|
| 1 | INT/identity surrogate key | reload yields different keys → fact joins rot, not idempotent | content-hash `generate_surrogate_key([...])` | GLD-01 |
| 2 | Fuzzy-match combos to one ATC code to lift coverage % | a confident WRONG answer, worse than unmatched; corrupts KPI | combos → `combination_unverified`, never `fuzzy` | XWK-02 |
| 3 | `LIKE '%name%'` substring match | false-positive inside longer words | word-boundary regex `\b...\b` | XWK-03 |
| 4 | `SELECT DISTINCT` / `GROUP BY all` to dedupe | can't pick the *latest*; fragile to new columns | `row_number()` partition + order, keep `rn=1` | SIL-01 |
| 5 | Materialize staging as a table | storage cost + stale data + slow rebuilds | staging = `view` (always fresh, zero storage) | SIL-02 |
| 6 | `DELETE`/`DROP` garbage rows silently | lose audit trail + lose valid signal in the row | null the bad field + `dq_flag`/`dq_reason` | SIL-05 |
| 7 | Write a cleaning regex for the one bad row you saw | other anomaly shapes slip through uncounted | profile the whole column first, prove the defect count | SIL-06 |
| 8 | `incremental` materialization everywhere | non-atomic on object storage; reads `{{this}}` that may not exist | full deterministic rebuild (facts are small + hashed) | GLD-05 |
| 9 | Two columns/meanings in one (`match_confidence` = provenance + quality) | corrupts the coverage-KPI denominator | separate `drug_member_type` from `match_confidence` | GLD-02 |
| 10 | `timestamp` SCD2 strategy on a field with no reliable updated_at | missed changes / false history | `check` strategy diffing business columns | GLD-04 |
| 11 | INNER JOIN fact → dim | silently drops fact rows when a lookup misses | LEFT JOIN, null FK tracked as a KPI | GLD-09 / GLD-07 |
| 12 | Join `fact_review` on drug name directly | many products share a name → fan-out past grain | collapse to ONE representative `drug_sk` | GLD-06 |
| 13 | Hardcode S3 endpoint/keys per script | can't move MinIO↔AWS; secrets in repo | one env-driven httpfs contract + `credential_chain` | INF-01 / INF-02 |
| 14 | DuckDB-only SQL in models | breaks on Snowflake prod, or two copies of every model | cross-dialect macros (`parse_date`, `regexp_replace_all`) | INF-03 |
| 15 | String-concat S3 paths inline in every model | drift, typos, can't change lake layout | centralized path macros | INF-04 |
| 16 | Keep nested arrays from the API in the model | breaks cross-engine; complicates joins | flatten to delimited string at the staging boundary | SIL-04 |
| 17 | `pd.read_csv` + row-by-row `INSERT` to load | memory-bound, slow, falls over as volume grows | set-based `COPY (SELECT … read_csv_auto) TO parquet` | BRZ-01 |
| 18 | Assume `COPY`/load worked because no exception | empty/corrupt parquet ships silently | read it back + count rows (round-trip proof) | BRZ-06 |
| 19 | `urlopen(url)` with no timeout | a hung API stalls the run forever, eats the SLA | hard `timeout=180` → fail fast + retry | ING-03 |
| 20 | Clean/transform during ingestion | can't replay true raw; a cleaning bug corrupts the only copy | land raw write-once; transform later | ING-05 |
| 21 | "Move"/rename a folder onto the serving path | object storage has no atomic rename → torn reads | verify-then-copy into a stable `_current` pointer | PUB-02 |
| 22 | Overwrite previous Gold once new run is live | no rollback path, no lineage | keep `gold/<run_id>/`; rollback = re-publish older id | PUB-03 |
| 23 | `ExpectTableRowCountToEqual(N)` on an SCD2 dim | green once, red on every run after the 2nd | row-count *band* (floor + sane ceiling) | DQ-03 |
| 24 | Hard-`error` on every null everywhere | build blocked by legitimate source quirks; alerts ignored | `warn` for known-harmless, `error` for real defects | DQ-04 |
| 25 | One `materialized=` config for all targets | invalid `external` on Snowflake / useless `cluster_by` on DuckDB | target-aware `{% if target.type %}` branch | SRV-01 |

> **The meta-point for interview:** "A junior optimizes the *metric*; a senior optimizes *what the
> metric protects*." Most cards here are that lesson applied to one layer.

---

## Cross-Layer Threads (interview narrative arcs)
Five principles recur across layers. Each is a ready-made "I apply this consistently everywhere"
story — walk the thread end-to-end and you sound like someone with a *system*, not a checklist.

1. **Idempotency / replay-safety** — raw kept write-once (ING-05) → Bronze per-date overwrite
   (BRZ-04) → ephemeral compute, S3 is the only truth (BRZ-05) → content-hash keys (GLD-01) →
   full deterministic rebuild (GLD-05) → atomic publish + rollback (PUB-02, PUB-03) ‖ DAG: T010.
   *"Any day, any run, any worker — same result. That property is engineered at every layer, not hoped for."*

2. **Honest coverage over vanity 100%** — combos excluded from fuzzy (XWK-02) → coverage is a KPI
   not a target (XWK-06) → partial match keeps the row with a null FK + reason (SIL-05, GLD-07) →
   DQ asserts a *floor*, not equality (DQ-02).
   *"I never fake completeness. I measure the gap, protect a floor, and keep the data honest."*

3. **Portability / no environment lock-in** — one env-driven httpfs contract (INF-01) →
   `credential_chain` not hardcoded keys (INF-02) → cross-dialect macros (INF-03) →
   target-aware materialization (SRV-01) → cross-dialect `dim_date`/date parsing (GLD-08, INF-03).
   *"The same code runs on local MinIO and production AWS/Snowflake. Environment is config, never code."*

4. **Atomicity on object storage (no atomic rename)** — full rebuild not incremental (GLD-05) →
   verify-then-publish (PUB-01) → copy into a stable pointer (PUB-02) → readers see only `_current`
   (PUB-05).
   *"S3 has no atomic rename, so I designed the publish around that constraint instead of pretending."*

5. **Fail loud, fail early** — strict bash (ING-01) → hard API timeout (ING-03) → read-back
   verify (BRZ-06) → compile-time error on bad dialect (INF-06) → publish aborts on bad verify
   (PUB-04) → DQ severity tuned so real failures still mean something (DQ-04).
   *"Errors surface at the cheapest point to fix them — build time, not in a dashboard."*
