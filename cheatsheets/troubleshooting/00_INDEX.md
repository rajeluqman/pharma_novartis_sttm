# DE Incident-Response / Troubleshooting Library — Index

> Failure-path catalog for the Helvetia Pharma pipeline (S3 + DuckDB + dbt-duckdb +
> Snowflake external-table veneer + MWAA). Owned by **@incident-responder**.
> Failure-path twin of `cheatsheets/optimization/` (agent #19). Governed by **ADR-006**.
>
> **Purpose:** turn real on-call diagnosis on THIS stack into interview ammunition —
> every failure mode paired with the **junior mistake** made during the incident and
> proven at a `file:line` (where the code already guards it) or placed (where it should).

## How to use this in an interview ("how did you troubleshoot?")
1. **Executive summary first** — lead with blast radius + business impact, not the bug.
2. **Walk the checklist** — triage → logs → ingestion → transform → load → validation →
   CI/CD → post-mortem. Name where you'd look, not just what was wrong.
3. **Prove it** — cite the `file:line` of the guard (or the reconciliation query).
   Close with the one-line `Soundbite`.
4. Drill the **Top Junior Mistakes** table the morning of the interview.

## Card format (every entry)
```
### <CARD-ID> — <failure mode>  [✅ HARDENED | 🟡 APPLICABLE | ⚪ N/A]
- Symptom         : what the alert / log / count shows
- Diagnosis       : where to look + the exact command/query (reconciliation)
- Root cause      : ranked candidates
- Fix / Recovery  : the action (+ backfill / catchup rerun if relevant)
- Evidence        : file:line (HARDENED) | placement + tradeoff (APPLICABLE) | why + flip (N/A)
- ⚠️ Junior mistake : the naive wrong move during the incident
- 🎤 Soundbite      : executive-summary interview line
```

## Legend
✅ HARDENED = code already guards it (`file:line`) · 🟡 APPLICABLE = guard not there yet,
placement + tradeoff named · ⚪ N/A = can't happen on this stack (+ what would flip it) · ★ = headline

## ⚠️ Numbering note (read this — DA condition, ADR-006)
Troubleshooting file numbers `01–08` are the **incident-response phase order** (the
on-call checklist), **NOT** the data-layer map. They do **not** line up with the
optimization library's layer numbers (where `01=Ingestion, 03=Silver, 05=Gold`).
Example: here `03_ingestion_s3` is *checklist step 3*, not "layer 3". Cross-reference by
**layer name**, never by number.

## Phase map (incident-response checklist order)

| # | Phase | File | Status | Cards |
|---|-------|------|--------|-------|
| 01 | Triage & blast radius | [01_triage_blast_radius.md](01_triage_blast_radius.md) | ✅ **DRILL-READY** (C3) | 7 |
| 02 | Run logs / stack trace | [02_orchestration_airflow.md](02_orchestration_airflow.md) | ✅ **DRILL-READY** (C3) | 7 |
| 03 | Ingestion (S3) | [03_ingestion_s3.md](03_ingestion_s3.md) | ✅ **PILOT** | 6 |
| 04 | Transformation (DuckDB/dbt) | [04_transformation.md](04_transformation.md) | ✅ **DRILL-READY** (C3) | 6 |
| 05 | Load (Snowflake external table) | [05_load_snowflake.md](05_load_snowflake.md) | ✅ **DRILL-READY, 1 caveat** (C3) | 5 |
| 06 | Data validation (Great Expectations) | [06_data_validation.md](06_data_validation.md) | ✅ **DRILL-READY** (C3) | 5 |
| 07 | CI/CD audit (GitHub / parse gate) | [07_cicd_github.md](07_cicd_github.md) | ✅ **DRILL-READY** (C3) | 6 |
| 08 | Post-mortem & recovery | [08_postmortem_recovery.md](08_postmortem_recovery.md) | ✅ **DRILL-READY** (C3) | 7 |

**51 cards live across all 8 phases — all 8 phases now DRILL-READY (C3).** 2026-06-19:
layers 04/05/06 cleared DA's C3 condition first (seed→bronze→dbt build→publish_gold→GE
against local MinIO `gym-lake`, independently re-verified by @senior-data-engineer). L-SNO-03
(Snowflake `REFRESH` metadata caching) stays 🟡 APPLICABLE permanently — real Snowflake
server-side behavior the incubator deliberately never exercises (ADR-006-A1 never touches
live Snowflake). **2026-06-20: phases 01/02/07/08 cleared C3** via real `gym-lake` MinIO reps
— and the reps surfaced two genuinely new findings that citation-reading alone had missed:

- ★ **`O-AIR-07`** (`02_orchestration_airflow.md`) — `pharma_sttm_pipeline_v1` cannot complete
  an orchestrated run AT ALL: every `dbt(...)` call is a separate `subprocess` against an
  intentionally-ephemeral `:memory:` DuckDB catalog (ADR-005 Condition C), so Silver (`view`)
  and the SCD2 snapshot never survive a task boundary — only Gold (`external`) does. 100%
  reproducible, proven live. This **supersedes and corrects** the prior headline finding
  (`O-AIR-01`, below) — the DAG never gets far enough to hit that gap; it fails one step
  earlier, on the very first orchestrated run, every time. Also forced a root-cause correction
  to `O-AIR-03`. Confirmed live that even the real MWAA `DagBag` parse gate (`O-AIR-06`/
  `C-CICD-02`) stays green regardless — no gate at any tier executes a task body.
- ★ **`P-PMR-07`** (`08_postmortem_recovery.md`) — re-running the SAME day twice is NOT
  idempotent: `stg_beta__ndc.sql`'s dedup has no secondary tie-break key (the same bug class
  `T-XFM-05` already guards against in `int_drug_crosswalk.sql`, just missed here), and real
  data has 1,317 tie groups. Live-reproduced: two back-to-back identical-input pipeline runs
  produced `dim_drug` = 133,654 then 133,758 rows.

Prior headline (`O-AIR-01` — DAG never calls `publish_gold.py`/threads `run_id`) remains true
and documented but is now understood as "the next bug you'd hit after fixing O-AIR-07," not
today's first symptom. Disclosed in `docs/OPS_RUNBOOK.md` Known Gaps (both new findings, ahead
of the superseded one). Target ~100 cards across all phases; next growth is depth (more cards
per phase), not new phases.

## Spark→DuckDB translation table (binding — @senior-data-engineer, ADR-006)
The source checklist assumed Spark. **This stack has no Spark.** Use these mappings;
do NOT publish a card whose symptom is dead on this stack.

| Video failure mode (Spark) | This project's equivalent | Status |
|---|---|---|
| Data skew (uneven executor partitions) | Single fat `GROUP BY`/window in dbt silver blowing one process's memory → call it **"aggregation / cardinality blowup"**, not "skew" | 🟡 REFRAME |
| Broadcast join (threshold tuning) | DuckDB picks hash build/probe side automatically; no user threshold, no shuffle to trade | ⚪ N/A — flips only if joins move to Snowflake compute (ADR-005 forbids) |
| OOM / executor memory | **#1 real failure.** DuckDB OOM on the 136k-row NDC unnest / big `read_json_auto` / unbounded silver join, under MWAA worker limits. `memory_limit` / `temp_directory` spill / worker class | 🟢 KEEP ★ "process memory / OOM (DuckDB + MWAA worker)" |
| Shuffle (network stage movement) | No distributed shuffle; analog = DuckDB out-of-core **spill to `temp_directory`** | ⚪ N/A as "shuffle" → 🟡 reframe "spill to disk" |
| Small-file explosion | **Real.** Gold `gold/<run_id>/` + per-`<date>` bronze parquet → many small files → slow `read_parquet` globs + Snowflake external-table scan cost | 🟢 KEEP |
| Silent data drops / filtering bugs | **Real, most dangerous.** `read_csv_auto` type-sniff dropping rows, bad `UNION ALL` schema mismatch, inner join culling crosswalk rows. Diagnose via row-count reconciliation landing→bronze→silver | 🟢 KEEP ★ |
| Partition pruning | Not a tunable; partitioning = **date-prefix path convention** (`landing/<src>/<date>/`). Failure = "glob hits wrong/too many date prefixes" | 🟡 REFRAME "date-prefix scoping" |

### Checklist steps that DON'T map cleanly (rewrite, don't copy)
- **Run logs / stack trace** — no Spark UI on managed MWAA. Use **CloudWatch task log +
  DuckDB Python traceback**.
- **Snowflake load → copy history / COPY INTO** — ⚪ mostly N/A. We use **external tables
  over Gold parquet**, no `COPY INTO`, no copy history. Real failure = external-table
  **schema/type mismatch** + **stale/missing `gold/<run_id>/` pointer** after teardown.
- **Schema/nullable on load** — surfaces at external-table **definition time** + dbt
  **contracts**, not at a COPY.
- Triage/blast-radius, post-mortem/recovery (backfill, catchup), CI/CD audit → map
  cleanly (MWAA-native; DAG parse gate already exists).

## Top Junior Mistakes (cross-phase — drill these)
| # | Junior mistake | Phase | Card |
|---|----------------|-------|------|
| 1 | "COPY didn't error so the load is fine" — never reconciles row counts | Transform/Load | I-ING-03 |
| 2 | Treats a 0-byte/short file as success because the upload exited 0 | Ingestion | I-ING-01 |
| 3 | `urlopen` with no status/length/checksum check → truncated source lands silently | Ingestion | I-ING-02 |
| 4 | Re-runs by timestamping filenames → breaks idempotent replay | Ingestion | I-ING-06 |
| 5 | Writes a "broadcast join / Spark UI" answer for a stack with no Spark | Transform | (see translation table) |
| 6 | Runs failure injection against the live veneer instead of a throwaway run_id | (gym hygiene) | ADR-006 guardrail |
| 7 | Reads "DAG green" as "Gold published" — this pipeline's DAG never calls `publish_gold.py` (true, but never even gets there — see #11) | Triage / Orchestration | T-TRI-05 / O-AIR-01 |
| 8 | Trusts a plausible bronze row count as proof of a FRESH load (the seed step silently falls back to yesterday's local dir) | Triage | T-TRI-02 |
| 9 | Treats "all CI checks passed" as proof a DAG will parse on real MWAA — `py_compile` never imports Airflow | CI/CD | C-CICD-02 |
| 10 | "Fixes" a stale Gold by re-pointing the Snowflake external table instead of re-running `publish_gold.py` | Post-mortem | P-PMR-03 |
| 11 | ★ Debugs the model named in `dbt_marts()`'s error instead of checking WHICH task failed first — this DAG cannot survive a task boundary at all (ephemeral `:memory:` catalog + one subprocess per `dbt` call), so the real first move is "which task," not "which model" | Triage / Orchestration | T-TRI-07 / O-AIR-07 |
| 12 | Assumes a rerun of an already-published day is a harmless no-op — `stg_beta__ndc`'s missing tie-break can silently inflate `dim_drug`'s SCD2 history on replay | Post-mortem | P-PMR-07 |
