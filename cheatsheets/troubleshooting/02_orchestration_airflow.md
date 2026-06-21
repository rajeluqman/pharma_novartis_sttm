# Phase 02 — Run Logs / Stack Trace (Airflow/MWAA) — Incident Cards  [DRILL-READY]

> Checklist step 2 of 8 (see `00_INDEX.md`). **Stack-honest (DA condition, ADR-006/A1):
> no Spark UI on managed MWAA.** The real "stack trace" on this stack is the **Airflow task
> log (CloudWatch in the cloud, container log locally) PLUS the underlying Python/dbt
> traceback** that `subprocess.run(..., check=True)` propagates as a task FAILED state —
> never look for a Spark UI or a Spark stage graph; it doesn't exist on this stack.
> Scope: `airflow/dags/pharma_sttm_pipeline.py`, `scripts/parse_test_mwaa.sh`,
> `docs/OPS_RUNBOOK.md` Monitoring Endpoints + Playbook Scenarios.
> **DRILL-READY (C3, ADR-006-A1) — cleared 2026-06-20.** Exercised against a real `gym-lake`
> MinIO loop, reproducing every `dbt(...)` call site as its own separate `subprocess` exactly
> as the DAG does (not just citation-read). The rep surfaced a real bug the prior
> STRUCTURE-ONLY (C2) pass missed because it never actually executed the task bodies — see
> ★ O-AIR-07 below — which also forced a correction to O-AIR-03's root cause.
> Owned by @incident-responder · Governed by ADR-006 / ADR-006-A1.

---

### O-AIR-01 — DAG never promotes Gold to `_current` (constant `run_id`, no publish task)  [🟡 APPLICABLE — premise superseded, see ★ O-AIR-07]
- ⚠️ **2026-06-20 update**: this card's symptom assumes the DAG *reaches* `dq_checks()` green. The MinIO rep proved it never does — `dbt_marts()` fails before `dq_checks()` ever runs (★ O-AIR-07). This card's diagnosis (no `run_id` threading, no publish task) remains a real, independent gap that will surface the DAY O-AIR-07 is fixed — keep it, but don't present it as today's *first* symptom; O-AIR-07 is.
- Symptom         : (becomes live once O-AIR-07 is fixed) `pharma_sttm_pipeline_v1` runs end-to-end green, `dq_checks()` prints GE `OVERALL: PASS` — but the Snowflake veneer / dashboards never reflect that day's data.
- Diagnosis       : (1) grep the DAG for any call to `publish_gold.py` — there is none. (2) grep every `dbt(...)` call site in the DAG for `--vars`/`run_id` — none pass it. (3) check what `run_ge_validation.py` actually reads.
- Root cause      : compound, three facts that combine into a real gap:
  1. The DAG's `dbt()` helper never passes `--vars '{"run_id": ...}'`, so every dbt-orchestrated run uses the **default** `run_id: "dev"` (`dbt/dbt_project.yml:18`), writing every Gold model to the SAME fixed `gold/dev/<model>/` location (`dbt/macros/s3_paths.sql:25-26`) instead of a unique per-run dir.
  2. No task in the DAG calls `scripts/publish_gold.py` — the only place that script is invoked anywhere in the repo is `scripts/run_pipeline_aws.sh:34-35`, a separate manual shell runner the DAG never triggers.
  3. `dq_checks()`'s own GE step reads `gold/_current/` (`scripts/run_ge_validation.py:35`), which is NOT `gold/dev/` — so `dq_checks()` validates whatever was last published by a *manual* `run_pipeline_aws.sh` run, never this DAG run's own output.
- Fix / Recovery  : add a `publish_gold` task as the new terminal step (`dq_checks() >> publish_gold()`, GE must gate BEFORE publish, not validate after — see `06_data_validation.md` `V-DQ-04`), and thread a real unique `run_id` (e.g. Airflow's `run_id`/`ds`) through every `dbt(...)` call via `--vars`.
- Evidence        : `airflow/dags/pharma_sttm_pipeline.py:34-35` (`dbt()` helper, no `--vars`), `:90,94-95,99,103` (every call site, none pass `run_id`), `:101-107` (`dq_checks()` is the DAG's terminal task; full topology at `:107`) + `dbt/dbt_project.yml:18` (`run_id: "dev"` default) + `dbt/macros/s3_paths.sql:25-26` (`var('run_id', 'dev')` builds the path) + `scripts/run_ge_validation.py:35` (`gold/_current/` read path) + `scripts/run_pipeline_aws.sh:34-38` (the only place `publish_gold.py` + correct step order actually exist, and it's outside the DAG entirely). 🟡 APPLICABLE — guard not there yet; this is a real, previously-undocumented gap (not present in `docs/OPS_RUNBOOK.md`), not a hypothetical.
- ⚠️ Junior mistake : reading a green `dq_checks()` task as proof the day's pipeline reached serving — on this DAG as currently wired, it never reads or writes anything `dq_checks()` itself just produced; it's validating someone else's last manual run.
- 🎤 Soundbite      : "I traced the DAG's own dbt calls and found none of them pass a `run_id`, and nothing in the DAG calls the publish script — so a green orchestrated run today only ever writes to a fixed `gold/dev/` directory that the Snowflake veneer never reads. The fix is one task: thread a real run_id and add a gated publish step."

---

### O-AIR-02 — Where the "stack trace" actually lives (CloudWatch log + Python traceback, no Spark UI)  [✅ HARDENED]
- Symptom         : a task shows FAILED in the Airflow Grid view; the instinct trained on other stacks is to go look for a Spark UI / stage DAG.
- Diagnosis       : open the task's log in the Airflow UI (`http://localhost:8080` locally; CloudWatch Logs once on MWAA) — every task body is a thin wrapper that shells out, so the log contains the REAL underlying Python/dbt traceback, not an Airflow-internal error.
- Root cause      : N/A — documents where the evidence actually is on this stack.
- Fix / Recovery  : read the task log top-to-bottom for the `subprocess`-raised `CalledProcessError` and the command's own stderr above it — that's the equivalent of a Spark executor stack trace here.
- Evidence        : `airflow/dags/pharma_sttm_pipeline.py:28-31` (`run()` helper: `subprocess.run(cmd, ..., check=True)` — `check=True` is what turns a script's non-zero exit into a task FAILED, and the script's own stdout/stderr streams INTO the task log, not a separate system) + `docs/OPS_RUNBOOK.md:9` (Monitoring Endpoints: Airflow UI is "DAG runs, task logs"). ✅ HARDENED — this is the literal subprocess-to-task-log mechanism, not a convention.
- ⚠️ Junior mistake : searching for a Spark UI / executor log on a managed MWAA environment that has neither — this stack's "stack trace" is one click into the Airflow task log, every time.
- 🎤 Soundbite      : "There's no Spark UI on this stack — every task here is a `subprocess.run` wrapper, so the task log IS the stack trace, complete with the underlying script's own traceback."

---

### O-AIR-03 — `dbt_marts()` ordering dependency: snapshot must succeed before `marts.core` runs  [✅ HARDENED, root cause CORRECTED 2026-06-20 — see ★ O-AIR-07]
- Symptom         : `dbt_marts()` task FAILED with a missing-relation error on `dim_drug` (which reads from `snap_beta_ndc`).
- Diagnosis       : open the task log and find which of the TWO sequential commands inside `dbt_marts()` actually ran — `dbt snapshot` or `dbt run -s marts.core`. They're in the same task body, not separate tasks.
- Root cause      : originally written as "IF `dbt snapshot` fails first (for some unrelated reason), `check=True` aborts before `marts.core` runs." **The real MinIO rep proved this understates it: `dbt snapshot` does not fail occasionally here, it fails on literally every real run**, and for the exact same structural reason documented in ★ O-AIR-07 below (`stg_beta__ndc` lives in a separate subprocess's ephemeral `:memory:` catalog that no longer exists by the time `dbt snapshot` starts). This card's symptom/diagnosis steps are still correct and worth keeping — they're what a triager actually sees — but read them together with O-AIR-07 for the true root cause; this card alone would lead a triager to debug the wrong thing ("why did snapshot fail this one time") instead of the right thing ("snapshot can never succeed across a task boundary as this DAG is wired").
- Fix / Recovery  : scroll to the FIRST failing command in the task log, not the last error line — still correct triage advice. The actual fix is O-AIR-07's, not a `dim_drug.sql`/snapshot-config fix.
- Evidence        : `airflow/dags/pharma_sttm_pipeline.py:92-95` (`dbt_marts()`: `dbt("snapshot")` then `dbt("run", "-s", "marts.core")`, two sequential calls in one task body, i.e. two separate `subprocess.run()` calls). ✅ HARDENED as a triage/diagnosis pattern; 🔧 root cause superseded by O-AIR-07.
- ⚠️ Junior mistake : jumping straight into `dim_drug.sql` or `snap_beta_ndc.sql` to debug a "missing relation" error, when the actual failure is structural (no dbt invocation here can ever see a prior invocation's non-`external` relations) — the error surfaces at the consumer, not the producer, and no per-model fix will resolve it.
- 🎤 Soundbite      : "Two dbt commands live inside one task body here — when `dbt_marts()` fails, I check which of the two actually ran. But I learned from actually running this end-to-end that it's not a flaky ordering risk — `dbt snapshot` fails 100% of the time here, because of how the DuckDB catalog is scoped, which is a much bigger finding than 'check the first error.'"

---

### O-AIR-04 — A task "up_for_retry" is not yet an incident  [✅ HARDENED]
- Symptom         : `beta.land` shows a non-green state shortly after a failure.
- Diagnosis       : check the task's actual state in the Grid view — `up_for_retry` is a DIFFERENT state from `failed`, and this DAG is configured to retry automatically before declaring defeat.
- Root cause      : N/A — documents the retry budget that exists by design.
- Fix / Recovery  : let the configured retry budget play out (2 retries, 5-min delay DAG-wide; `beta.land` additionally backs off exponentially) before escalating — only escalate once the task is in a genuine `failed` (retries exhausted) state.
- Evidence        : `airflow/dags/pharma_sttm_pipeline.py:43-48` (`default_args`: `retries: 2`, `retry_delay: 5 min`, DAG-wide) + `:66` (`@task(retry_exponential_backoff=True)` on `beta.land` specifically, "don't hammer a struggling openFDA API on retry"). ✅ HARDENED.
- ⚠️ Junior mistake : escalating CRITICAL on the FIRST `beta.land` attempt failing, without checking whether it's still inside its 2-retry budget and might self-heal in minutes against a flaky external API.
- 🎤 Soundbite      : "Before I escalate a task failure, I check whether it's actually exhausted its retry budget — this DAG is built to absorb transient blips on its own, especially on the openFDA call, which backs off exponentially by design."

---

### O-AIR-05 — `execution_timeout` kills a hung task; the 240-min `sla` is informational only  [✅ HARDENED]
- Symptom         : confusion about why a task that's "only" run for 35 minutes got killed, versus why an SLA-miss banner appeared but nothing got killed at all.
- Diagnosis       : these are two DIFFERENT mechanisms with different consequences — `execution_timeout` is per-task and terminates the task; `sla` is DAG-wide and only fires an alert/banner, it does not stop anything.
- Root cause      : N/A — documents the distinct semantics of the two `default_args` keys.
- Fix / Recovery  : for a killed task, check if it ran past 30 minutes (the real kill threshold); for an SLA-miss banner with no killed task, treat it as informational — "let the DAG finish; investigate root cause for next run" (no rerun action is implied by the banner itself).
- Evidence        : `airflow/dags/pharma_sttm_pipeline.py:44-45` (`"execution_timeout": pendulum.duration(minutes=30)` — kills the task; `"sla": SLA` = 240 min — alerts only) + `docs/OPS_RUNBOOK.md:65` ("Rerun: N/A for the SLA banner itself (it's informational once the threshold is crossed) — let the DAG finish"). ✅ HARDENED.
- ⚠️ Junior mistake : trying to "fix" an SLA-miss banner by killing/rerunning the DAG mid-flight — the banner doesn't mean anything is broken yet; killing a healthy in-flight run to react to it is the actual mistake.
- 🎤 Soundbite      : "The SLA is a 240-minute alert, not a kill switch — only `execution_timeout` (30 min, per task) actually terminates anything here, so an SLA banner by itself isn't a signal to intervene."

---

### O-AIR-06 — A DAG that imports fine locally can still fail to PARSE on real MWAA  [✅ HARDENED]
- Symptom         : the dev `.venv` happily imports `pharma_sttm_pipeline.py` with zero errors, giving false confidence ahead of an MWAA spike.
- Diagnosis       : run the MWAA-faithful parse gate, not the local venv import — they target different, sometimes API-incompatible Airflow versions.
- Root cause      : the dev `.venv` deliberately runs an unpinned, newer Airflow than MWAA actually ships (e.g. `default_args={"sla": ...}` was removed in Airflow 3.0) — a local-only "it imports fine" check can be a false signal for what AWS MWAA will actually accept.
- Fix / Recovery  : `bash scripts/parse_test_mwaa.sh` — a one-shot, read-only `DagBag` import against the pinned Airflow 2.10.3 image (`aws-mwaa-local-runner`), $0, no AWS creds mounted; PASS/FAIL is explicit (`IMPORT_ERRORS`, exit code).
- Evidence        : `scripts/parse_test_mwaa.sh:6-10` (states exactly why the local `.venv` is the wrong target) + `:98-112` (one-shot `DagBag("/usr/local/airflow/dags", include_examples=False)`, read-only mount, no creds env) + `docs/OPS_RUNBOOK.md:79` (Session Start Checklist records this gate CLOSED 2026-06-19, reproducible on demand). ✅ HARDENED.
- ⚠️ Junior mistake : treating "my local Python imports the DAG file with no exception" as proof it'll parse on MWAA — different Airflow major version, different accepted kwargs, different result.
- 🎤 Soundbite      : "Before any MWAA spike I run the parse gate against the actual pinned Airflow version MWAA ships, not my local venv — they're different majors, and a kwarg this DAG uses was removed in the newer one."

---

### O-AIR-07 — `pharma_sttm_pipeline_v1` cannot complete past `dbt_enrich()` on ANY real run — every `dbt(...)` call is a separate process, and the DuckDB catalog is `:memory:`  ★  [✅ HARDENED]
- Symptom         : the very first orchestrated run of the day fails inside `dbt_marts()` with `Catalog Error: Table with name "main_enrich.stg_beta__ndc" does not exist because schema "main_enrich" does not exist` (or the equivalent for `stg_gamma__reviews` against `dim_condition`). This is NOT intermittent — it reproduces on every single attempt, with fresh data, with nothing else wrong.
- Diagnosis       : (1) `dbt/profiles.yml` dev target is `path: ":memory:"` (ADR-005 Condition C — deliberately ephemeral, no `warehouse.duckdb` file). (2) the DAG's `dbt()` helper (`airflow/dags/pharma_sttm_pipeline.py:34-35`) shells out via `subprocess.run(["dbt", ...])` for EVERY individual dbt command. (3) `staging` models materialize as `view` (`dbt/dbt_project.yml:36`) and `snap_beta_ndc` materializes as a default DuckDB **table** (`dbt/snapshots/snap_beta_ndc.sql:6-15`, no `external`) — neither is written to S3; both live only inside that one subprocess's throwaway in-memory catalog. (4) the moment that subprocess exits, the catalog — and every view/table in it — is gone. The NEXT `dbt(...)` call (a new task, or even the next call within the *same* task body) starts a brand-new empty `:memory:` catalog that has never heard of `main_enrich.*` or `snapshots.snap_beta_ndc`.
- Root cause      : architectural mismatch between ADR-005's "ephemeral DuckDB, parquet-on-S3 is the only persistent truth" design and the DAG's "one dbt CLI subprocess per command" execution model. Only `marts.core`/`marts.serving` (materialized `external`, writing real parquet to `gold/<run_id>/...` via `dbt/macros/s3_paths.sql:25-26`) actually survive a process boundary — `staging` (Silver-equivalent) and the SCD2 `snapshot` do not, and the DAG's task topology depends on them surviving at least one task→task handoff (`alpha()/beta()/gamma() → dbt_enrich() → dbt_marts()`) and even one call→call handoff inside `dbt_marts()` itself (`dbt("snapshot")` then `dbt("run", "-s", "marts.core")`, ★ O-AIR-03). The codebase already anticipated half the fix: `dbt/macros/s3_paths.sql:18-20` defines `silver_location()` for exactly this, with a comment admitting "not used while staging stays view." It was never wired up, and nothing before this rep ever ran the DAG's actual per-task subprocess sequence to notice — `scripts/run_pipeline_aws.sh` (and every previous MinIO/AWS pipeline validation, including earlier in this same session) runs staging+snapshot+marts+serving inside ONE `dbt build` process, which never crosses this boundary at all. The MWAA parse gate (`scripts/parse_test_mwaa.sh`, O-AIR-06) only imports the DAG file — `DagBag` import never executes a task body, so it stays green regardless (reproduced live this session: parse gate PASS, `IMPORT_ERRORS: {}`, with this bug fully present).
- Fix / Recovery  : two real options, not a one-liner — (a) flip `staging` to `+materialized: external` using the already-present `silver_location()` macro (and give `snap_beta_ndc` an external/S3 target too) so every stage persists to S3 and the next subprocess reads it back via `read_parquet()`/sources instead of an in-memory `ref()`; or (b) stop splitting the pipeline across separate `dbt` CLI subprocess invocations — collapse `dbt_enrich()` + `dbt_marts()` + `dbt_serving()` into one task that runs one `dbt build` (mirrors what `run_pipeline_aws.sh` already does safely), trading task-level Airflow observability for correctness. **Today's actual recovery if this bites in prod is NOT "retry the DAG"** — retries reproduce the identical failure every time (it's deterministic, not transient) — it's "fall back to the manual `scripts/run_pipeline_aws.sh` single-process runner," which is also why nobody noticed: the manual runner has been the only thing that ever actually worked.
- Evidence        : `dbt/profiles.yml` (`path: ":memory:"`, dev target) + `airflow/dags/pharma_sttm_pipeline.py:28-35` (`run()`/`dbt()` helpers — `subprocess.run` per call) + `:88-99` (`dbt_enrich()`, `dbt_marts()`, `dbt_serving()` — 4 separate `dbt(...)` calls across 3 tasks, none share a process) + `dbt/dbt_project.yml:35-37` (`staging: +materialized: view`) + `dbt/snapshots/snap_beta_ndc.sql:6-9` (no `external`, default DuckDB table target) + `dbt/macros/s3_paths.sql:18-20` (`silver_location()`, defined but unused) + live reproduction this session (two separate `dbt` subprocess invocations, `gym-lake`, `LAND_DATE=2026-06-18`): `dbt run -s staging` → `PASS=5`, then in a **new** process `dbt snapshot` → `Catalog Error: ... main_enrich.stg_beta__ndc ... does not exist`, then `dbt run -s marts.core` → `Catalog Error: ... snapshots.snap_beta_ndc ... does not exist` + `Catalog Error: ... main_enrich.stg_gamma__reviews ... does not exist` (`PASS=3 ERROR=2 SKIP=2`) — then confirmed `bash scripts/parse_test_mwaa.sh` stays `PASS`/`IMPORT_ERRORS: {}` despite this. ✅ HARDENED — 100% reproducible, not a hypothetical, not a one-off flake.
- ⚠️ Junior mistake : assuming a clean MWAA parse-gate PASS plus "the pipeline definitely worked before when I ran it by hand" means the *orchestrated* DAG is sound — parse-clean only proves the Python imports; it says nothing about whether dbt state actually survives between tasks, and the manual single-process runner masks this completely.
- 🎤 Soundbite      : "I didn't just read the DAG — I ran its actual per-task subprocess sequence against a real MinIO bucket, and `dbt_marts()` failed on the very first attempt, every time, because the dev DuckDB target is intentionally `:memory:` and each Airflow task shells out to a brand-new `dbt` process. Silver and the SCD2 snapshot never survive a task boundary; only Gold does, because it's the only thing that's `external`-materialized to S3. That's a bigger finding than the Gold-publish gap I'd already documented — it means the DAG has never actually completed an orchestrated run, full stop."

---

## Phase tally
✅ HARDENED: 6 · 🟡 APPLICABLE: 1 · ⚪ N/A: 0 — **7 cards** (drill-ready, C3, cleared 2026-06-20).
