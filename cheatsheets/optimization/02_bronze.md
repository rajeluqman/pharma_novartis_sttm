# Layer 02 — Bronze (Load) Optimization
> Script: `scripts/load_bronze.py` — Landing → Bronze, DuckDB via httpfs, parquet on S3.
> Job of this layer: land raw source into a typed, columnar, queryable format with lineage —
> and nothing else (no business cleaning). See [00_INDEX.md](00_INDEX.md) for card format.

---

### BRZ-01 ★ — Set-based `COPY`, not a pandas read + INSERT loop  [✅ DONE]
- **Junior mistake:** `pd.read_csv(...)` then `to_sql` / row-by-row `INSERT` to load Bronze.
- **Why it bites:** Pulls the whole file into Python memory and inserts row-by-row — slow, memory-bound, and it falls over as volume grows.
- **Optimized (this repo):** `COPY (SELECT * FROM read_csv_auto(...)) TO '...parquet'` — DuckDB reads the source and writes parquet in one vectorized, set-based operation; Python never holds the data. `scripts/load_bronze.py:41-46`
- **Business one-liner:** "Loading is a single bulk engine operation, so it stays fast and memory-safe as data grows."
- **Soundbite:** *"Let the engine move the data. Python should hand it the SQL, not carry the rows."*
- **Related:** orchestration T063 (same `COPY`, seen at DAG altitude)

### BRZ-02 — Bronze does NO cleaning — raw as-is, typing deferred to staging  [✅ DONE]
- **Junior mistake:** Cast types, rename columns, fix values during the Bronze load.
- **Why it bites:** Mixes "land" and "clean" concerns, so a cleaning bug means re-ingesting, and you lose the faithful raw copy that makes replay trustworthy.
- **Optimized (this repo):** Bronze copies raw columns as-is and only *adds* load metadata; all cleaning/typing lives in dbt staging. `scripts/load_bronze.py:4-5,43`
- **Business one-liner:** "Bronze is a faithful copy, not an opinion — fixes happen in a later layer we can re-run freely."
- **Soundbite:** *"Bronze stores what arrived; Silver decides what it means."*

### BRZ-03 — Stamp lineage columns (`load_ts`, `source_file`) at load  [✅ DONE]
- **Junior mistake:** Load bare data with no provenance.
- **Why it bites:** When a number looks wrong, there's no way to trace a row back to the file or run it came from — debugging becomes guesswork.
- **Optimized (this repo):** every Bronze row carries `current_timestamp AS load_ts` and a literal `source_file`, riding through staging into the facts. `scripts/load_bronze.py:43,49,57,67,70`
- **Business one-liner:** "Every record knows which file and run it came from, so any data question is traceable to its origin."
- **Soundbite:** *"Lineage columns cost two literals at load and save hours at 3am."*

### BRZ-04 — Per-date deterministic overwrite = idempotent  [✅ DONE]
- **Junior mistake:** Append to a growing Bronze table on every run.
- **Why it bites:** Re-running a day duplicates its data; the load isn't replay-safe, so a retry corrupts the layer.
- **Optimized (this repo):** Bronze writes to a fixed `bronze/<src>/<date>/<table>.parquet` path — re-running the same date overwrites with identical content. `scripts/load_bronze.py:9,32-33`
- **Business one-liner:** "Re-running any day is always safe — it reproduces the same result instead of piling up duplicates."
- **Soundbite:** *"Overwrite a deterministic path and 'did this run twice?' stops being a question."*
- **Related:** ING-05, GLD-05, PUB-02 · orchestration T010 (idempotency thread)

### BRZ-05 — Ephemeral in-memory catalog, no local `warehouse.duckdb` truth  [✅ DONE]
- **Junior mistake:** Persist a local `.duckdb` file as "the warehouse" and treat it as the source of truth.
- **Why it bites:** State lives on one worker's disk — not replay-safe, not shareable, and lost when a cold/stateless worker runs the job.
- **Optimized (this repo):** `duckdb.connect(":memory:")` with httpfs; the catalog is discarded at process exit and S3 parquet is the only persistent truth (ADR-005 Condition C). `scripts/load_bronze.py:7,37`
- **Business one-liner:** "Compute is disposable and storage is the cloud — any worker can run any step with no local state to manage."
- **Soundbite:** *"The truth is in S3, not on the worker. Treat the engine as cattle, not a pet."*
- **Related:** ING-05, BRZ-04 · orchestration T009 (decouple orchestration from execution)

### BRZ-06 — Verify by reading the data back, not by "COPY didn't error"  [✅ DONE]
- **Junior mistake:** Assume the load worked because no exception was raised.
- **Why it bites:** A `COPY` can succeed while producing an empty or unreadable parquet (bad source glob, partial write) — the failure ships silently.
- **Optimized (this repo):** after writing, the script `read_parquet(...)` round-trips each table and prints the row count — a real proof it's readable and non-empty. `scripts/load_bronze.py:75-83`
- **Business one-liner:** "We confirm the loaded data is actually readable and non-empty before declaring success."
- **Soundbite:** *"'No error' is not 'it worked.' Read it back and count it."*

### BRZ-07 — Explicit CSV quote/escape for messy free-text source  [✅ DONE]
- **Junior mistake:** Parse the Gamma review CSV with default settings.
- **Why it bites:** Reviews contain embedded quotes and commas; default parsing shifts columns and corrupts rows that look fine until they reach the dashboard.
- **Optimized (this repo):** `read_csv_auto(..., quote='"', escape='"')` so quoted fields with delimiters parse correctly. `scripts/load_bronze.py:68,71`
- **Business one-liner:** "Free-text patient reviews load without column-shift corruption, even when they contain quotes and commas."
- **Soundbite:** *"Free text will always contain your delimiter. Tell the parser how to handle it."*
