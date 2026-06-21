# Layer 09 — Shared Infra / Portability Optimization
> Cross-cutting code that every layer depends on: `scripts/s3_env.py`, dbt macros
> (`s3_paths.sql`, `parse_date.sql`, `regexp_replace_all.sql`, `snapshot_s3_roundtrip.sql`).
> Theme: **portability + DRY** — make environment and engine differences a config concern,
> not a code concern. See [00_INDEX.md](00_INDEX.md) for card format.

---

### INF-01 ★ — One env-driven httpfs contract for every script  [✅ DONE]
- **Junior mistake:** Each script configures its own S3/DuckDB connection with its own hardcoded endpoint, region, and URL style.
- **Why it bites:** Moving from local MinIO to real AWS becomes a hunt-and-edit across every file; one script gets missed and fails in a different environment.
- **Optimized (this repo):** a single `configure_httpfs(con)` reads the **same** env-var contract (`S3_ENDPOINT`, `S3_URL_STYLE`, `S3_USE_SSL`, region, keys) everywhere, so MinIO→AWS is a pure env change — never a code change. `scripts/s3_env.py:1-17,34-47`
- **Business one-liner:** "We promote the exact same code from local to cloud — switching environments is a settings change, with nothing to re-test in the code."
- **Soundbite:** *"Environment differences belong in env vars, not in `if env == 'prod'` branches scattered across scripts."*

### INF-02 ★ — `credential_chain` on real AWS; explicit keys only for MinIO  [✅ DONE]
- **Junior mistake:** Hardcode AWS access keys in the script (or commit them in `.env`) so "it just works everywhere".
- **Why it bites:** Keys in code/repo are a security incident waiting to happen, and they don't rotate with the platform's IAM.
- **Optimized (this repo):** on real AWS the code creates a DuckDB secret with `PROVIDER credential_chain` (env / instance-profile / SSO resolve creds); explicit keys are used **only** for MinIO, which has no chain. `scripts/s3_env.py:14-16,49-57`
- **Business one-liner:** "Production credentials come from the cloud's own identity system, so there are no long-lived secrets sitting in our code."
- **Soundbite:** *"The best place to store a secret is nowhere — let the credential chain resolve it."*

### INF-03 ★ — Cross-dialect macros: one model, two engines  [✅ DONE]
- **Junior mistake:** Write DuckDB-only SQL in models (e.g. `strptime`, `regexp_replace(..., 'g')`) and deal with Snowflake "later", or maintain two copies of every model.
- **Why it bites:** The models break on the Snowflake prod target, or you double your maintenance surface and the two copies drift.
- **Optimized (this repo):** dialect differences are isolated in macros — `parse_date(col, duckdb_fmt, snowflake_fmt)` and `regexp_replace_all(...)` emit the right SQL per `target.type`, so models stay engine-agnostic. `dbt/macros/parse_date.sql`, `dbt/macros/regexp_replace_all.sql` (used in `stg_gamma__reviews.sql:18,24`, `fact_review.sql:23,29`)
- **Business one-liner:** "The same transformation logic runs on the dev engine and the production warehouse — no rewrite, no drift."
- **Soundbite:** *"Quarantine dialect quirks in a macro so the models never have to know which engine they're on."*
- **Related:** SRV-01, GLD-08, INF-06 (portability thread)

### INF-04 — Centralized S3 path macros, not inline string-concat  [✅ DONE]
- **Junior mistake:** Build `s3://bucket/bronze/.../x.parquet` by string concatenation inline in every model and script.
- **Why it bites:** The lake layout is now duplicated in dozens of places — a typo or a layout change means editing all of them, and they silently diverge.
- **Optimized (this repo):** `bronze_parquet()`, `gold_run_location()`, `snapshot_location()`, `s3_bucket()` own path construction in one place. `dbt/macros/s3_paths.sql`
- **Business one-liner:** "The lake's folder structure is defined once — we can reorganize storage without touching every model."
- **Soundbite:** *"A path built in fifty places is fifty chances to be wrong. Build it once."*

### INF-05 — Parametrize runs via `--vars` with safe dev defaults  [✅ DONE]
- **Junior mistake:** Hardcode the load date / run id, or read them only from the environment.
- **Why it bites:** You can't cleanly backfill a specific date or isolate a run's Gold output; ad-hoc local runs become awkward.
- **Optimized (this repo):** `load_date` and `run_id` come from dbt `--vars` (the DAG passes them per run) but default to `today` / `'dev'` for friction-free local work. `dbt/macros/s3_paths.sql:11,25`
- **Business one-liner:** "We can rebuild any specific date or isolate any run's output on demand, while local development stays one command."
- **Soundbite:** *"Parametrize for production, default for the developer. Both at once."*

### INF-06 — Fail loud on an unsupported dialect  [✅ DONE]
- **Junior mistake:** Let the cross-dialect macro fall through a silent `else` to some default SQL.
- **Why it bites:** An unsupported target emits wrong-but-runnable SQL that's only caught much later, at runtime, in production.
- **Optimized (this repo):** `parse_date` raises `exceptions.raise_compiler_error(...)` for any target that isn't duckdb/snowflake — the build fails at compile time, immediately. `dbt/macros/parse_date.sql:7-9`
- **Business one-liner:** "An unsupported setup fails instantly and loudly at build time, instead of producing subtly wrong data in production."
- **Soundbite:** *"Fail at compile, not in the warehouse. A loud early error is a feature."*

### INF-07 ★ — Document the deviation when the tool has no native hook  [✅ DONE]
- **Junior mistake:** Either abandon the S3-persistence requirement because dbt's `snapshot` has no `external`/`location` option, or hack a workaround without understanding dbt's relation cache (so the loaded table silently collides with the snapshot's initial-build branch).
- **Why it bites:** The naive workaround creates a relation via raw `run_query()`, which dbt's adapter cache never sees → dbt takes the initial-build path and its `create table` collides with the one you just made. Silent, confusing failure.
- **Optimized (this repo):** on-run-start loads prior SCD2 state from S3 and registers it with `adapter.cache_added()` (dbt's blessed mechanism for relations created outside materialization), on-run-end exports the new state back to S3 — all in the same ephemeral session, with the *why* documented in the macro. `dbt/macros/snapshot_s3_roundtrip.sql:1-5,20-31`
- **Business one-liner:** "Where the tool didn't natively support our cloud-storage design, we bridged it correctly and wrote down exactly why — so the next engineer doesn't 'fix' it back into a bug."
- **Soundbite:** *"Knowing the tool's internals — like dbt's relation cache — is the difference between a workaround that holds and one that detonates on the next run."*
