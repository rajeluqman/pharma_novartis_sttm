# Airflow Optimization Library — `pharma_sttm_pipeline`
> Reusable pattern catalog (100 techniques).
> Each project = one *instantiation* of these patterns (OOP-style reuse). This file is
> the first instantiation, mapped to the Helvetia Pharma enVision pipeline.
>
> **RULE:** every `✅ DONE` card MUST cite a real
> `file:line`. Every `🟡 APPLICABLE` card MUST name where it would go + the tradeoff.
> No empty definitions. If you can't point at code, it's not "done" — it's a soundbite.

## How to use this in an interview
1. **Lead with the executive summary** (`Business one-liner`) — what it buys the business.
2. **Then the step / mechanism** (`How / Justification`) — why this technique, the tradeoff.
3. **Close with evidence** (`Evidence` file:line) — proves you *did* it, not read it.
4. For "what would you do next?" → pull from the `🟡 APPLICABLE` bucket.
5. For "why didn't you do X?" → pull from `⚪ N/A` bucket (maturity signal: right-sizing).

## Legend
| Bucket | Meaning |
|--------|---------|
| ✅ **DONE** | In the code now — has `file:line` proof |
| 🟡 **APPLICABLE** | Sensible next optimization for this project (the "ruang optimization") |
| ⚪ **N/A** | Not relevant to a single-DAG / DuckDB / managed-MWAA lab — *know why* |
| ★ | Interview-headline technique (full card below) |

---

## Master classification — all 100

### 1. DAG & Task Design Architecture
| # | Technique | Bucket | Evidence / Note |
|---|-----------|--------|-----------------|
| T001 | Lean DAG parsing (no heavy work at top level) | ✅ | only imports + 2 helpers at top; all work inside tasks via subprocess |
| T002 ★ | TaskGroups, never SubDAG | ✅ | `dag.py:47,59,71` (alpha/beta/gamma groups) |
| T003 | Single Responsibility per task | ✅ | `land()` vs `bronze()` split per source `dag.py:49,53` |
| T004 | Dynamic DAG from JSON/YAML (cached) | ⚪ | single static DAG; no generator needed |
| T005 | Right-size `schedule_interval` | ✅ | `0 3 * * *` daily = matches 7AM BI need `dag.py:40` |
| T006 ★ | `catchup=False` | ✅ | `dag.py:42` |
| T007 ★ | Static `start_date` | ✅ | `START = pendulum.datetime(2026,6,1)` `dag.py:20,41` |
| T008 ★ | Split long pipelines (Dataset / TriggerDagRun) | 🟡 | one monolith DAG; could split ingest vs transform on Datasets |
| T009 ★ | Decouple orchestration from execution | ✅ | `subprocess.run(...)` `dag.py:28-31` — "conductor not worker" |
| T010 ★ | Idempotency | ✅ | per-`<date>` deterministic overwrite `load_bronze.py:9` |

### 2. Scheduler & Parsing
| # | Technique | Bucket | Evidence / Note |
|---|-----------|--------|-----------------|
| T011 | `min_file_process_interval` | ⚪ | MWAA-managed; know the knob, don't tune in lab |
| T012 | `dag_dir_list_interval` | ⚪ | MWAA-managed |
| T013 ★ | `.airflowignore` | 🟡 | add `tests/`, `.venv/`, `dbt/target/` — easy parse-time win |
| T014 | Reduce top-level imports | ✅ | only `os/pathlib/subprocess/pendulum` at top `dag.py:13-18` |
| T015 | No Variables/Connections at top level | ✅ | none fetched at parse time |
| T016 | Jinja for dynamic values | ✅ | `ds` injected per-run into tasks `dag.py:51,55` |
| T017 | Monitor `total_parse_time` | 🟡 | ADR-005 parse gate exists; add metric assertion |
| T018 | Flat DAG folder | ✅ | single file in `airflow/dags/` |
| T019 | No global DB connection | ✅ | DuckDB conn opened inside scripts, not in DAG |
| T020 | Fast-parsing patterns | ✅ | helpers are funcs; bodies run only inside tasks |

### 3. Concurrency & Resource Management
| # | Technique | Bucket | Evidence / Note |
|---|-----------|--------|-----------------|
| T021 | `max_active_runs` | 🟡 | add `=1` (daily snapshot, no overlap wanted) |
| T022 | `max_active_tasks` | 🟡 | cap fan-out if MWAA workers small |
| T023 | `max_active_tis_per_dag` | 🟡 | for heavy bronze load task |
| T024 ★ | Pools | 🟡 | beta NDC = openFDA API → put in a rate-limit pool |
| T025 | `priority_weight` | 🟡 | prioritize critical-path (marts.core) |
| T026 | `weight_rule` | 🟡 | `downstream` to prioritize whole chain |
| T027 | `worker_concurrency` (Celery) | ⚪ | MWAA-managed |
| T028 | KubernetesExecutor for spiky load | ⚪ | MWAA; single daily run |
| T029 | Global `parallelism` | ⚪ | MWAA-managed |
| T030 | Don't over-provision pools | 🟡 | applies once T024 pool exists |

### 4. XCom / Data Passing
| # | Technique | Bucket | Evidence / Note |
|---|-----------|--------|-----------------|
| T031 | Never pass large data via XCom | ✅ | data flows through S3; tasks pass nothing big |
| T032 | Custom XCom backend (S3) | ⚪ | not passing big payloads — unnecessary |
| T033 | Pass references not data | ✅ | S3 URIs + `LAND_DATE` env, not DataFrames `dag.py:51` |
| T034 ★ | `do_xcom_push=False` | 🟡 | tasks return `None` already; set explicit when adding returns |
| T035 ★ | Clear old XCom (maintenance DAG) | 🟡 | add `airflow db clean` maintenance DAG |
| T036 ★ | `template_fields` for metadata passing | 🟡 | use `ti.xcom_pull` templating if cross-task refs added |
| T037 | Compress custom XCom | ⚪ | no custom backend |
| T038 | Cleanup local task files | 🟡 | bronze stages to S3; add temp cleanup if local scratch used |
| T039 ★ | TaskFlow API | ✅ | `@dag/@task/@task_group` `dag.py:18,38,47` |
| T040 | Short/uniform XCom keys | ✅ | minimal XCom surface |

### 5. Sensors / Intelligent Waiting
| # | Technique | Bucket | Evidence / Note |
|---|-----------|--------|-----------------|
| T041 | Avoid `poke` for long sensors | 🟡 | no sensors yet — arrives at curriculum L9 |
| T042 | `reschedule` mode | 🟡 | L9 |
| T043 | Sensor timeout | 🟡 | L9 |
| T044 | Tune `poke_interval` | 🟡 | L9 |
| T045 | Deferrable operators / Triggers | 🟡 | L10 hardening |
| T046 ★ | Event-driven (S3 event → trigger) | 🟡 | replace future landing-sensor with S3 notification |
| T047 | Combine sensor checks | 🟡 | one task checks all 3 source files |
| T048 | Optimized SQL sensors | ⚪ | no SQL sensor in design |
| T049 | `ExternalTaskSensor` date match | 🟡 | if T008 split into multiple DAGs |
| T050 | Sensor `exponential_backoff` | 🟡 | L9 |

### 6. Retries / Timeouts / Errors
| # | Technique | Bucket | Evidence / Note |
|---|-----------|--------|-----------------|
| T051 ★ | `execution_timeout` on ALL tasks | ✅ | 30-min guardrail in `default_args` `dag.py:45` |
| T052 ★ | Reasonable `retries` (2–3) | ✅ | `retries=2` `dag.py:46` |
| T053 ★ | `retry_delay` | ✅ | `5min` `dag.py:47` |
| T054 ★ | `retry_exponential_backoff` | ✅ | beta API task decorator `dag.py:66` |
| T055 ★ | SLA configured | ✅ | `default_args={"sla": SLA}` `dag.py:21,43` |
| T056 ★ | `on_failure_callback` cleanup | 🟡 | terminate/clean partial S3 run on fail |
| T057 ★ | `trigger_rule` precise | 🟡 | DQ task → consider `all_done` vs `all_success` |
| T058 | `AirflowSkipException` | 🟡 | graceful skip when a source has no new file |
| T059 ★ | Fail-fast validation at START | 🟡 | DQ runs at **tail** `dag.py:98-100`; add lightweight head check |
| T060 | Monitor SLA misses | 🟡 | wire SLA-miss page → SLA_ANALYSIS log |

### 7. Cloud / Infra / Operators
| # | Technique | Bucket | Evidence / Note |
|---|-----------|--------|-----------------|
| T061 ★ | Specialized operators (S3ToSnowflake…) | ⚪ | **deliberate** subprocess choice (ADR, `dag.py:9`) — explain tradeoff |
| T062 | KubernetesPodOperator isolation | ⚪ | no dependency conflicts; DuckDB in-proc |
| T063 ★ | Native bulk-load (`COPY INTO`) | ✅ | DuckDB `COPY ... TO ... (FORMAT PARQUET)` `load_bronze.py:42-45` |
| T064 ★ | Managed Airflow (MWAA) | ✅ | ADR-005; `requirements/requirements-mwaa.txt` pinned 2.10.3 |
| T065 | Avoid LocalExecutor in prod | ⚪ | MWAA = Celery under the hood |
| T066 | Clean worker storage | ⚪ | MWAA-managed |
| T067 | Celery prefetch tuning | ⚪ | MWAA-managed |
| T068 ★ | dbt broken up (selectors, not Cosmos) | ✅ | `-s staging / marts.core / marts.serving` `dag.py:85,90,94`; Cosmos rejected `dag.py:9` |
| T069 | Keep connections updated | 🟡 | prune dead Airflow connections |
| T070 | Connection pooling in target DB | ⚪ | DuckDB ephemeral; no pool |

### 8. Maintainability / Clean Code
| # | Technique | Bucket | Evidence / Note |
|---|-----------|--------|-----------------|
| T071 ★ | Group configs into one Variable JSON | 🟡 | currently `.env`; consolidate to one JSON Variable |
| T072 | TaskFlow API (boilerplate cut) | ✅ | `dag.py:38,47` |
| T073 | Lint (Ruff/Flake8) | 🟡 | add to CI to block heavy top-level logic |
| T074 ★ | Helper logic in separate modules | ✅ | `scripts/*.py`, `scripts/s3_env.py` — DAG is structure only |
| T075 | No hardcoded values | ✅ | paths via `s3_env` + env vars |
| T076 ★ | Unit-test DAG parsing (dagbag) | 🟡 | ADR-005 parse gate exists; formalize as `tests/unit/test_dag_parse.py` |
| T077 | No cyclic dependencies | ✅ | clean fan-out → linear tail `dag.py:102` |
| T078 | `doc_md` descriptions | ✅ | module docstring `dag.py:1-9` (add per-DAG `doc_md` = 🟡) |
| T079 | Naming conventions | ✅ | `dag_id="pharma_sttm_pipeline"`, tags `dag.py:39,44` |
| T080 ★ | Semantic versioning in DAG id | ✅ | `dag_id="pharma_sttm_pipeline_v1"` `dag.py:39` |

### 9. Logging / Monitoring / DB Maintenance
| # | Technique | Bucket | Evidence / Note |
|---|-----------|--------|-----------------|
| T081 | Offload logs to cloud | ✅ | MWAA → CloudWatch by default |
| T082 | Log levels INFO/WARNING | 🟡 | set prod level explicitly |
| T083 | Metadata DB purge (`db clean`) | 🟡 | add to T035 maintenance DAG |
| T084 | Index metadata DB | ⚪ | MWAA-managed |
| T085 | StatsD/Prometheus metrics | ⚪ | prod add-on; out of lab scope |
| T086 | Cleanup temp files (context mgr) | 🟡 | `NamedTemporaryFile` if local scratch added |
| T087 | OpenLineage | 🟡 | nice-to-have lineage; pairs with STTM |
| T088 | Mute noisy loggers | 🟡 | quiet boto3/duckdb chatter |
| T089 | Sentry | ⚪ | prod alerting; out of lab scope |
| T090 ★ | Profile task runtimes (Gantt) | ✅ | diagnosis method `docs/sla/SLA_ANALYSIS.md` (Gantt → critical path) |

### 10. Advanced Scalability / Next-Gen
| # | Technique | Bucket | Evidence / Note |
|---|-----------|--------|-----------------|
| T091 ★★ | Dynamic Task Mapping (`.expand()`) | 🟡 | **headline** — alpha/beta/gamma are 3 near-identical groups `dag.py:47-81` → collapse to one mapped task |
| T092 ★ | Dataset-based orchestration | 🟡 | trigger marts only when bronze Dataset updates |
| T093 | Async Triggers (cross-team) | 🟡 | `TriggerDagRunOperator` if T008 split |
| T094 | `PythonVirtualenvOperator` isolation | ⚪ | no conflicting deps; subprocess already isolates |
| T095 | DAG processor isolation | ⚪ | MWAA-managed |
| T096 | Avoid nested Jinja loops | ✅ | simple `{{ ds }}` only |
| T097 | Limit `on_execute_callback` | ✅ | none heavy |
| T098 | Balance worker sizing | ⚪ | MWAA-managed |
| T099 | PgBouncer | ⚪ | MWAA-managed metadata DB |
| T100 ★ | Keep Airflow up to date | ✅ | pinned MWAA **2.10.3**, parse-validated (ADR-005 P5) `requirements/requirements-mwaa.txt` |

**Tally:** ✅ DONE ≈ 35 · 🟡 APPLICABLE ≈ 35 · ⚪ N/A ≈ 30.
The N/A column is your *maturity proof* — you right-sized instead of cargo-culting.

> ⚠️ **Version drift (real finding, 2026-06-19):** local `.venv` runs Airflow **3.2.2**
> while the deploy target is MWAA **2.10.3** (`requirements-mwaa.txt`). DagBag parse
> passes on both, but the **SLA feature (T055) is removed in Airflow 3.0** (→ Deadline
> Alerts in 3.1+). So `default_args["sla"]` is valid on the 2.10.3 target but a no-op
> on the local 3.x venv. The authoritative parse gate is **aws-mwaa-local-runner @ 2.10.3**
> (ADR-005 P5), not this venv. Migration to Airflow 3 = a tracked 🟡 (SLA → Deadline Alerts).

---

# Full cards

> Format per card: **Business one-liner** (exec summary) → **How / Justification**
> (the step + why + tradeoff) → **Evidence** → **Interview soundbite**.

## ✅ DONE — proven in code

### T100 ★ — Keep Airflow up to date  [✅ DONE]
- **Business one-liner:** Running a current, pinned engine version means faster scheduling and fewer surprise outages — the platform gets cheaper and more reliable for free, just by staying patched.
- **How / Justification:** Pinned **MWAA 2.10.3** in `requirements/requirements-mwaa.txt` and gated the DAG through a parse-validation step (ADR-005 P5) so an upgrade can't silently break parsing. Major Airflow releases have cut scheduling/parse latency by up to ~50%; pinning (not floating) means upgrades are *deliberate and tested*, never accidental.
- **Tradeoff:** (+) perf + security for free · (−) must re-validate parse on each bump (which is exactly why the parse gate exists).
- **Live proof of the discipline:** the local `.venv` drifted to Airflow **3.2.2** while the target stays pinned at **2.10.3** — and the parse check is precisely what surfaces that the SLA feature behaves differently across the two. Pinning + a gate caught a silent semantic change. That's the technique earning its keep.
- **Evidence:** `requirements/requirements-mwaa.txt`; parse gate per ADR-005 P5.
- **Soundbite:** *"I treat the runtime as a dependency: pinned, version-controlled, and parse-validated before it ships. An upgrade is a tested decision, not a hope."*

### T009 ★ — Decouple orchestration from execution  [✅ DONE]
- **Business one-liner:** Airflow is the *conductor*, not the *worker*. When data volume grows 10×, we scale the cheap compute engine — we don't rewrite the pipeline.
- **How / Justification:** Every task shells out via `subprocess.run(...)` to a real script or `dbt` selector; no heavy transform runs inside a PythonOperator. This keeps Airflow workers light and makes the compute engine swappable (DuckDB today, Spark tomorrow) without touching the DAG.
- **Tradeoff:** (+) light, portable, swappable · (−) must capture subprocess logs deliberately.
- **Evidence:** `airflow/dags/pharma_sttm_pipeline.py:28-31`; rationale `dag.py:9`.
- **Soundbite:** *"Airflow orchestrates; it doesn't compute. That single boundary is why scaling is a config change, not a refactor."*

### T010 ★ — Idempotency  [✅ DONE]
- **Business one-liner:** Re-running a failed day produces the *same* clean result — no duplicates, no manual cleanup, no 3am panic.
- **How / Justification:** Bronze is a per-`<date>` deterministic *overwrite* to a fixed S3 path, never an append/INSERT loop. Rerun the same date → identical output. This is what makes retries (T052) safe.
- **Tradeoff:** (+) safe retries/backfill · (−) overwrite means no in-place history (mitigated by versioned landing).
- **Evidence:** `scripts/load_bronze.py:9` (deterministic overwrite), `:42-45` (COPY).
- **Soundbite:** *"Every task is safe to run twice. Idempotency is what turns a 3am failure into a one-click rerun."*

### T002 ★ — TaskGroups, never SubDAG  [✅ DONE]
- **Business one-liner:** The pipeline reads as three clean lanes in the UI — anyone can see at a glance where a source is stuck — with zero scheduler penalty.
- **How / Justification:** alpha/beta/gamma use `@task_group`. SubDAGs are deprecated and serialize on a single slot (a known performance trap); TaskGroups are pure visual grouping.
- **Evidence:** `airflow/dags/pharma_sttm_pipeline.py:47,59,71`.
- **Soundbite:** *"TaskGroups for clarity, never SubDAGs — same readability, none of the scheduler lock."*

### T006/T007 ★ — `catchup=False` + static `start_date`  [✅ DONE]
- **Business one-liner:** Turning the pipeline on doesn't accidentally launch dozens of historical runs that hammer the cluster and the cloud bill.
- **How / Justification:** `catchup=False` stops backfill-on-unpause; a *static* `start_date` (not `datetime.now()`) gives deterministic scheduling. Together they make "unpause" a safe, predictable action.
- **Evidence:** `dag.py:42` (catchup), `:20,41` (static start).
- **Soundbite:** *"Unpausing a DAG should be boring. Static start_date plus catchup=False guarantees exactly one run, exactly when expected."*

### T055 ★ — SLA configured  [✅ DONE]
- **Business one-liner:** The business promised dashboards by 7AM; the pipeline *knows* that deadline and raises an alarm the moment it's at risk — without stopping the run.
- **How / Justification:** `default_args={"sla": 240min}` against an 03:00 start encodes the 07:00 contract. SLA alerts (vs hard timeout) flag lateness without killing in-flight work.
- **Evidence:** `dag.py:21,44`.
- **Caveat (version-aware):** SLA is valid on the MWAA **2.10.3** target; it's **removed in Airflow 3.x** (local venv) in favour of Deadline Alerts. Know this in interview — it shows you track the engine, not just the syntax.
- **Soundbite:** *"The 7AM deadline isn't tribal knowledge — it's in the DAG. On 2.10.3 that's an SLA; on Airflow 3 I'd port it to a Deadline Alert. Same contract, version-aware."*

### T063 ★ — Native bulk-load (`COPY INTO`)  [✅ DONE]
- **Business one-liner:** Data lands in one set-based bulk operation instead of row-by-row loops — minutes, not hours, and far cheaper compute.
- **How / Justification:** Bronze uses DuckDB `COPY (SELECT … FROM read_csv_auto(...)) TO '...parquet'`, pushing the load to the engine's vectorized path rather than iterating in Python.
- **Evidence:** `scripts/load_bronze.py:42-45`.
- **Soundbite:** *"No INSERT loops. The engine does the bulk move set-based; Python just hands it the instruction."*

### T068 ★ — dbt broken into selectors (Cosmos rejected)  [✅ DONE]
- **Business one-liner:** Transforms run in clean, restartable stages (staging → core → serving) so a failure in one layer doesn't force re-running everything.
- **How / Justification:** Instead of one giant `dbt run`, the DAG calls `-s staging`, `-s marts.core`, `-s marts.serving` as separate tasks. Cosmos was *deliberately rejected* to avoid an extra orchestration dependency — selectors give the same staging with zero added packages.
- **Tradeoff:** (+) restartable layers, no new dep · (−) dependency order maintained by hand in the DAG.
- **Evidence:** `dag.py:85,90,94`; Cosmos rejection `dag.py:9`.
- **Soundbite:** *"I split dbt by layer for restartability — and skipped Cosmos on purpose. Don't add an orchestration package to do what a `-s` selector already does."*

### T074 ★ — Helper logic in separate modules  [✅ DONE]
- **Business one-liner:** The DAG file shows *what* runs and in what order; the *how* lives in tested, reusable scripts — easy to read, easy to test, easy to reuse.
- **How / Justification:** All real logic is in `scripts/*.py` (+ shared `scripts/s3_env.py`); the DAG holds only structure and two thin shell-out helpers.
- **Evidence:** `scripts/` modules; `dag.py:28-35` (thin helpers only).
- **Soundbite:** *"The DAG is a table of contents, not a textbook. Logic lives in modules I can unit-test without spinning up Airflow."*

### T039 ★ — TaskFlow API  [✅ DONE]
- **Business one-liner:** Less boilerplate, dependencies that read like plain English — faster to write, harder to get wrong.
- **How / Justification:** `@dag/@task/@task_group` with `>>` wiring; XCom handled implicitly so there's less manual plumbing to break.
- **Evidence:** `dag.py:18,38,47,102`.
- **Soundbite:** *"TaskFlow makes the dependency graph obvious from the code — the structure is the documentation."*

### T090 ★ — Profile task runtimes via Gantt  [✅ DONE]
- **Business one-liner:** When a deadline slips, we find the real bottleneck from evidence in minutes — not by guessing.
- **How / Justification:** Documented diagnosis method: open Grid+Gantt → longest bar/chain = critical path → confirm in logs → fix ONE thing → measure. Captured as the standing method in the SLA log.
- **Evidence:** `docs/sla/SLA_ANALYSIS.md` (Method section).
- **Soundbite:** *"Every perf fix starts at the Gantt chart and ends with a measured before/after. No 'feels faster.'"*

---

## 🟡 APPLICABLE — the optimization runway ("ruang optimization")

### T091 ★★ — Dynamic Task Mapping (`.expand()`)  [🟡 APPLICABLE — headline]
- **Business one-liner:** Adding a fourth or tenth data source becomes a one-line config change, not a copy-paste of a whole pipeline branch — less code, fewer bugs, faster onboarding of new feeds.
- **How / Justification (step-by-step exec summary):**
  1. **Observe:** alpha/beta/gamma are three near-identical land→bronze groups (`dag.py:47-81`) — classic copy-paste.
  2. **Refactor:** define one mapped task and `.expand()` over a `[{source, ingest_cmd}, ...]` list. One definition, N runtime instances.
  3. **Result:** new source = append one dict. This is literally the OOP reuse idea — one "class," many instances.
- **Tradeoff:** (+) DRY, scalable, fewer files · (−) divergent per-source logic (beta's SCD2 snapshot) must stay parameterized, not branched — keep the truly different bits explicit.
- **Where:** replace the three `@task_group` blocks in `dag.py:47-81`.
- **Soundbite:** *"Three hand-written source lanes is the smell. The optimization is dynamic task mapping — define the lane once, expand it over a list. Adding a feed stops being an engineering task."*

### T051/T052/T053/T054 ★ — Timeouts + retries + backoff  [✅ DONE]
- **Business one-liner:** A frozen API call or a transient blip can't silently eat the whole 7AM window — tasks self-heal on transient failures and refuse to hang forever.
- **How / Justification:**
  1. `execution_timeout=30min` in `default_args` so no task hangs past its slice of the 240-min budget (T051).
  2. `retries=2` + `retry_delay=5min` so transient API/network blips recover automatically (T052/T053).
  3. `retry_exponential_backoff=True` on the beta API task so retries don't hammer a struggling openFDA (T054).
- **Tradeoff:** (+) resilient + bounded · (−) wrong timeout values can mask a real slowdown — tune from observed Gantt durations (T090).
- **Evidence:** `dag.py:45-47` (default_args), `dag.py:66` (beta backoff).
- **Soundbite:** *"Retries are safe here precisely because tasks are idempotent (T010). Timeouts protect the deadline; retries absorb the noise. Both live in default_args, not sprinkled per task."*

### T059 ★ — Fail-fast validation at the START  [🟡 APPLICABLE]
- **Business one-liner:** We catch bad/missing input in the first 30 seconds instead of paying for a full pipeline run that's doomed to fail at the end.
- **How / Justification:** Today DQ runs at the **tail** (`dag.py:98-100`) — great as a trust gate, but it lets expensive transforms run on garbage. Add a lightweight head check (files present, row counts > 0, schema sane) that fails fast *before* enrich/marts.
- **Tradeoff:** (+) saves compute + time on bad days · (−) a second DQ surface to maintain — keep the head check cheap.
- **Where:** new task before `dbt_enrich`, `dag.py:102` chain.
- **Soundbite:** *"DQ at the tail proves trust; DQ at the head saves money. I want both — a cheap gate up front, the full suite at the end."*

### T076 ★ — Unit-test DAG parsing (dagbag)  [🟡 APPLICABLE]
- **Business one-liner:** A broken DAG can never reach production — CI rejects the pull request before it can break the morning run.
- **How / Justification:** The ADR-005 parse gate already validates parsing manually; formalize it as `tests/unit/test_dag_parse.py` running `DagBag().import_errors == {}` in CI on every PR.
- **Where:** `tests/unit/`, wired into CI.
- **Soundbite:** *"The parse check already exists as a gate — promoting it to a CI unit test just makes 'it parses' a merge requirement, not a habit."*

### T024 ★ — Pools for the rate-limited source  [🟡 APPLICABLE]
- **Business one-liner:** The pipeline respects the external API's limits automatically, so we never get throttled or banned mid-run.
- **How / Justification:** beta ingests from the openFDA NDC API. Put that task in a small pool (e.g. 1–2 slots) so concurrency against the API is throttled centrally regardless of how many runs/tasks exist.
- **Tradeoff:** (+) protects against rate-limit bans · (−) under-sizing the pool serializes work — size to the API's real limit (T030).
- **Where:** `pool=` on beta's land task `dag.py:61`.
- **Soundbite:** *"External rate limits are an architecture constraint, not a per-task afterthought. A pool enforces it in one place."*

### T008 ★ / T092 ★ — Split pipeline on Datasets (event-driven)  [🟡 APPLICABLE]
- **Business one-liner:** Downstream transforms fire the moment fresh data lands — not on a fixed clock — so the marts are as fresh as possible and we stop running work when there's nothing new.
- **How / Justification:** Split the monolith into an ingest DAG and a transform DAG linked by an Airflow **Dataset**; marts run only when bronze updates. Combine with S3 event triggers (T046) for true event-driven freshness.
- **Tradeoff:** (+) freshness + no wasted runs · (−) more DAGs to reason about; cross-DAG lineage must stay clear.
- **Where:** factor `dag.py:102` chain across two DAGs.
- **Soundbite:** *"Time-based scheduling is a proxy for 'is the data ready?'. Datasets answer that question directly."*

### T056 ★ — `on_failure_callback` cleanup  [🟡 APPLICABLE]
- **Business one-liner:** A failed run cleans up after itself — no half-written outputs, no orphaned cost, no manual mopping.
- **How / Justification:** On failure, remove the partial `gold/<run_id>/` write so the atomic `_current` pointer swap (`publish_gold.py:58`) never sees an incomplete run.
- **Where:** `default_args` callback; ties to `publish_gold.py`.
- **Soundbite:** *"Failures should leave the system exactly as clean as they found it — the cleanup is part of the task contract."*

### T013 ★ — `.airflowignore`  [🟡 APPLICABLE]
- **Business one-liner:** The scheduler stops wasting cycles scanning files that aren't DAGs — faster, cheaper parsing.
- **How / Justification:** Add `.venv/`, `tests/`, `dbt/target/`, `scripts/` to `.airflowignore` so the file processor skips them.
- **Where:** new `airflow/dags/.airflowignore`.
- **Soundbite:** *"Parsing time is scheduler money. Tell it what to ignore."*

### T034/T035/T036 ★ — XCom hygiene  [🟡 APPLICABLE]
- **Business one-liner:** The Airflow metadata database stays lean and fast as run history grows into the thousands.
- **How / Justification:** Set `do_xcom_push=False` where returns aren't consumed (T034); add a maintenance DAG running `airflow db clean` for old XCom/log/task_instance rows (T035, T083); use `ti.xcom_pull` templating for any genuine cross-task metadata (T036).
- **Where:** task defs + new maintenance DAG.
- **Soundbite:** *"XCom is for pointers, not payloads — and even pointers need a cleanup job once history piles up."*

### T080 ★ — Semantic versioning in DAG id  [✅ DONE]
- **Business one-liner:** The DAG version is visible at a glance in the Airflow UI — structural changes are an explicit, searchable event, not a silent overwrite.
- **How / Justification:** `dag_id="pharma_sttm_pipeline_v1"` mirrors the existing STTM v2 / AH v2 governance convention; a breaking redesign ships as `_v2` so the old run history stays intact.
- **Evidence:** `dag.py:39`; OPS_RUNBOOK references updated.
- **Soundbite:** *"Versioned DAG ids — the same governance discipline I already apply to the published docs."*

### T071 ★ — Config consolidation  [🟡 APPLICABLE]
- **Business one-liner:** Settings live in one auditable place — easier ops, cleaner change history.
- **How / Justification:** Fold scattered `.env` keys into a single JSON Airflow Variable so config is one object, not 20 loose keys.
- **Where:** Airflow Variable + `s3_env.py` read.
- **Soundbite:** *"One config object instead of twenty knobs — fewer places for drift to hide."*

---

## ⚪ N/A — and *why* (maturity signals)

| # | Technique | Why N/A here | What would flip it to APPLICABLE |
|---|-----------|--------------|----------------------------------|
| T061 | Specialized operators (S3ToSnowflake) | Chose subprocess for portability + zero extra deps (ADR) | If team standardizes on provider operators for observability |
| T027–T029, T065–T067, T098 | Celery/Executor/worker tuning | MWAA-managed; single daily run | Self-hosted Airflow or high task volume |
| T032/T037 | Custom XCom backend | Not passing large payloads (data flows via S3) | If tasks ever returned DataFrames |
| T062/T094 | Pod / venv isolation | DuckDB in-process; no dep conflicts | Conflicting library versions per task |
| T084/T095/T099 | DB index / processor isolation / PgBouncer | MWAA-managed metadata DB | Self-managed Postgres backend at scale |
| T085/T089 | StatsD / Sentry | Out of lab scope; would add in prod | Production rollout with on-call |

> In interview: *"The N/A list is deliberate. I right-sized for one managed DAG on DuckDB — adding Celery tuning or PgBouncer here would be cargo-culting. Here's exactly what would make each one worth adding."*

---
## Related
- `cheatsheets/performance/_TEMPLATE.md` — per-issue deep-dive template
- `cheatsheets/DE_SKILLS_DICTIONARY.md` — skills index
- `docs/sla/SLA_ANALYSIS.md` — before/after runtime evidence (Track B gym)
- `learning/CURRICULUM.md` — L1–L10 ladder (where 🟡 sensor/pool techniques get built)
