# <PROJECT_NAME> — AI Context

> Auto-loaded by Claude Code every session.
> Do NOT commit this file to GitHub.

## Project Overview
**Domain**: <domain>
**Dataset**: <dataset name> — <source URL>
**Problem**: <one-sentence what pipeline solves>
**Modelling**: <Kimball / OBT / Hybrid> — <one-line justification>
**Purpose**: Data Engineering portfolio practice

## Current Status
→ See `PROJECT_STATUS.md` for latest progress
→ See `SIGN_OFF_LOG.md` for phase sign-offs
→ See `COST_LOG.md` for spend tracking
→ See `JOURNEY_LOG.md` for decisions + learning
→ See `DEBUG_CHECKPOINT.md` for active debugging state

## Token Discipline (WAJIB — semua agents & main session)
1. **Checkpoint first**: baca `PROJECT_STATUS.md` (dan `DEBUG_CHECKPOINT.md`
   kalau sedang debug, `LEARNING_LOG.md` kalau sesi cikgu) SEBELUM baca code.
   Kalau checkpoint dah jawab soalan, JANGAN scan codebase.
2. **Scope**: baca hanya files dalam module yang sedang dikerjakan.
   Max ~3 files per turn melainkan task explicitly perlukan lebih.
3. **Jangan re-read** files yang dah disenaraikan "Confirmed Clean" dalam
   `DEBUG_CHECKPOINT.md`.
4. **Search guna Explore subagent**: bila perlu cari "kat mana X
   defined/dipanggil", spawn Explore subagent (return kesimpulan sahaja) —
   jangan baca berbelas fail dalam main thread.
5. **Update checkpoint sebelum tamat turn**: debugging → `DEBUG_CHECKPOINT.md`;
   execution → `PROJECT_STATUS.md` "Next Step When Resuming".
6. **Jangan baca log besar** (troubleshooting/debate logs penuh) melainkan
   topik semasa memang pasal log tu.

## Stack (locked — HYBRID redefined by ADR-005: STORAGE = cloud-only S3; COMPUTE = DuckDB, hybrid host)
| Layer | Storage (S3 canonical) | Compute / engine | Constraint |
|-------|------------------------|------------------|-----------|
| Ingestion | writes raw → `s3://<bucket>/landing/...` | Python (Kaggle CLI + openFDA API) | Alpha=CSV, Beta=NDC API, Gamma=CSV |
| Landing | `s3://<bucket>/landing/{alpha,beta,gamma}/<date>/` | — (immutable, versioned, write-once) | replay/audit (ADR-002 + ADR-005) |
| Bronze | `s3://<bucket>/bronze/` (parquet + `load_ts`/`source_file`) | DuckDB via httpfs, **ephemeral catalog** | per-`<date>` overwrite, idempotent |
| Silver / Gold | `s3://<bucket>/{silver,gold}/` | dbt-duckdb **`external`** materialization | Gold = `gold/<run_id>/` + pointer swap |
| Serving (veneer) | reads Gold S3 files | Snowflake **external tables** (short window) | read-only BI demo, "warehouse over lakehouse" |
| Orchestration | — | **aws-mwaa-local-runner** (localhost:8080) → **AWS MWAA** | same DuckDB ELT both hosts; MWAA spike ≈ $3–5, teardown after run |
| Quality | — | Great Expectations | Suite per layer + dim_drug crosswalk match-rate |
| Modeling | — | dbdiagram.io (Erwin clone) | Enrich / Data Mart / RRD |
| Publish | — | Markdown → Confluence (publish_to_confluence.py) | only after @data-architect approval |

⚠️ Stack boundary = HARD LIMIT. Do not suggest tools outside this list. (Glue/Lambda REJECTED, ADR-005.)
⚠️ S3 is now ALWAYS-ON canonical storage (≈ <$1/mo, low-GB) — NOT torn down. The "short window
   teardown" premise now applies ONLY to MWAA + Snowflake serving. @finops-agent: cross-region
   egress is the real risk — region lock mechanical + version lifecycle (ADR-005 FinOps conditions).
⚠️ DuckDB catalog is EPHEMERAL (in-memory + httpfs) — no persistent `warehouse.duckdb` as truth.
⚠️ Provisioning (S3 bucket / Snowflake stage / MWAA) stays OWNER-GATED — confirm before any AWS create.

## Data Model (locked at Phase 3 sign-off — see docs/ADR/)
**Paradigm**: **Hybrid** — Kimball star = system of record; OBT = derived serving (ADR-001)
**Fact tables**: `fact_sales` (grain: 1 ATC category × 1 day) · `fact_review` (grain: 1 review event)
**Dimensions**: `dim_drug` SCD2 (conformed crosswalk, ADR-003) · `dim_date` SCD0 · `dim_condition` SCD1
**Source pattern**: Alpha=snapshot CSV · Beta=daily snapshot→SCD2 · Gamma=append log
**Storage vs compute trade-off**: star governs + OBT materialized for 7AM BI perf (rebuilt from star)
**Crosswalk**: `dim_drug` reconciles ATC ↔ pharm_class ↔ free-text name; coverage = DQD KPI, not 100%

## Cabinet (20 agents)
See `.claude/agents/` — each with model assignment + personality.

**Veto holders**:
- @data-architect (Opus) — architecture + governance; also approval gate on
  AH.md/STTM.md before Confluence publish
- @scope-guardian (Sonnet) — scope creep prevention (veto kekal; rule-check tak perlukan Opus)

**Strategic (Sonnet)**:
@product-owner, @business-analyst, @senior-data-engineer, @data-platform-engineer,
@data-quality-steward, @project-manager, @finops-agent, @cikgu,
@cheatsheet-generator, @infra-reality-agent, @documentation-sherpa,
@optimization-librarian, @incident-responder

**Executors (Haiku)**:
@data-engineer, @analytics-engineer, @qa-engineer, @devops-orchestrator

**Training Adversary (Sonnet, Track B only)**:
@bottleneck-saboteur — injects realistic SLA-breaking bottlenecks (S-track) AND
failure/data-corruption incidents (I-track, ADR-006); never appears in Track A's
5-phase build flow.

## Phase Flow — Track A (build)
- Phase 1: Discovery → BRD.md + DRD.md + DEBATE_LOG_phase_1.md
- Phase 2: Exploration → DATA_DICTIONARY.md + DRD.md complete
- Phase 3: Design → DATA_MODEL.md + ARCHITECTURE.md + PIPELINE_SPEC.md + ADRs
- Phase 4: Build → code (bronze/silver/gold) + cheatsheets/
- Phase 5: Quality → DQD.md + OPS_RUNBOOK.md + README.md + INTERVIEW_GUIDE.md

## Track B — SLA Troubleshooting Gym (after Track A pipeline works)
Build DAGs up the ladder (`learning/CURRICULUM.md`, L1→L10). @bottleneck-saboteur
injects one realistic flaw per level (symptom only, root cause sealed); diagnose
with @cikgu (critical path, Gantt, logs); fix; log before/after runtime in
`docs/sla/SLA_ANALYSIS.md`. Starter: `SLA_GYM_PROMPT.md`.

## Track I — Incident-Response Gym (failure, not slowness — ADR-006)
@bottleneck-saboteur injects a FAILURE/data-corruption incident (I-track I1-I10:
0-byte/truncated file, schema drift, type mismatch, silent drop, bad join, CI/CD break).
@incident-responder works the 8-step checklist, logs the drill in `docs/incidents/`,
and distills a card into `cheatsheets/troubleshooting/` (mirror of the optimization
library). @cikgu teaches from the symptom + card (never the sealed cause).
- **Log of record:** symptom registry = `docs/sla/SABOTAGE_LOG.md` (both S- and I-track);
  detailed walkthroughs = `docs/incidents/INCIDENT_<id>.md`.
- **Guardrail (now MECHANICAL — ADR-006-A1):** drills run in the INCUBATOR only —
  `source gym.env` (bucket=`gym-lake`, local MinIO, fake creds) + green `scripts/gym_guard.py`
  (fail-closed: aborts unless GYM_MODE=1 + gym-lake + local endpoint + fake creds). Closes the
  `s3_env.py` fail-open hole. Per-drill git branch `gym/round-NN`; `main`/live cloud never touched.
  Protocol: `docs/gym/INCUBATOR.md`.
- **Fidelity (ADR-006-A1):** symptom presented FAR from root (business/observability signal) →
  trace backward; observability-first; **hypothesis log before running** (evidence-gated);
  **grade the METHOD + recovery, NOT MTTR** (MTTR displayed only); severity/alert theatre L7+ only;
  user WRITES the post-mortem, diffs vs a **sealed RUBRIC** at `docs/incidents/.solutions/`
  (gitignored; acceptable paths + must-not-do list, not one answer). Difficulty ladder =
  `learning/DIFFICULTY_LADDER.md` (separate from the I1-I12 failure catalogue).
- **CI:** `.github/workflows/ci.yml` static gates (py_compile + ruff + GE-JSON + dbt parse +
  sealed-key-untracked), scoped PR→main (gym branches opt-in via `gym/regression-**`); $0.
- **NO separate optimization gym** — the SLA gym (S-track) already is it; optimization library
  stays a static catalog fed by SLA 🟡→✅.
- **Status:** Ingestion (S3) PILOT done + retrofitted to ADR-006-A1 — `cheatsheets/troubleshooting/03_ingestion_s3.md`
  (6 cards) + worked example `docs/incidents/INCIDENT_2026-06-19_beta-zero-byte-landing.md`
  (far-from-root L5 symptom + hypothesis-trail) + sealed rubric. 2026-06-19: layers 04
  (transformation), 05 (load/Snowflake-veneer), 06 (data validation) cleared DA's C3 condition
  via a real MinIO `gym-lake` pipeline loop (seed→bronze→dbt build→publish_gold→GE, independently
  re-verified by @senior-data-engineer) — **04/06 drill-ready to L10; 05 drill-ready to L10 except
  L-SNO-03**, which stays capped below L5 permanently (Snowflake `REFRESH` stale-metadata caching
  can't be reproduced on MinIO/DuckDB — accepted substrate limit, ADR-006-A1 Consequences).
  **2026-06-20: phases 01 (triage), 02 (orchestration-logs), 07 (CI/CD audit), 08 (post-mortem)
  cleared DA's C3 condition too** via real `gym-lake` MinIO reps (independently re-verified by
  @senior-data-engineer) — **all 8 phases now DRILL-READY, 51 cards total, checklist both
  structurally complete and mechanism-proven.** The reps surfaced two new, real,
  previously-unknown production-pipeline defects (not gym-mechanism findings): ★ `O-AIR-07`
  (phase 02) — `pharma_sttm_pipeline_v1` cannot complete an orchestrated run AT ALL, 100%
  reproducible (every `dbt(...)` call is a separate subprocess against the intentionally-ephemeral
  `:memory:` DuckDB catalog, ADR-005 Condition C, so Silver/snapshot never survive a task
  boundary — only Gold does) — this **supersedes `O-AIR-01`** as today's actual first symptom
  (`O-AIR-01` remains true but only becomes live once `O-AIR-07` is fixed); confirmed live that
  even the real MWAA `DagBag` parse gate stays green regardless (no gate at any tier executes a
  task body). ★ `P-PMR-07` (phase 08) — `stg_beta__ndc`'s dedup has no secondary tie-break key
  (same bug class already hardened in `int_drug_crosswalk.sql`, just missed here), live-proven to
  inflate `dim_drug`'s SCD2 history on a same-day rerun (133,654→133,758 rows, zero real change).
  Both disclosed in `docs/OPS_RUNBOOK.md` Known Gaps per the same documentation-hygiene standard
  as `O-AIR-01` (no ADR amendment — DA ruled neither touches ADR-006-A1's mechanism/rubric).
  Fixing the DAG (`O-AIR-07`) and the dedup (`P-PMR-07`) are both separate, not-yet-proposed
  build decisions. Next: depth (more cards per phase, target ~100), or pick up either fix.

## Track S — Spark + Delta DEMONSTRATION track (ADR-007)
Fenced, non-production, additive-never-substitutive track admitted 2026-06-20 (`docs/ADR/
ADR-007-spark-delta-demonstration-track.md`) — `local[*]`-only PySpark + Delta Lake against the
SAME ADR-001 star, read read-only from `gold/_current/`, written to a separate Spark staging
bucket. Never managed/paid compute (Glue/EMR/Databricks stay rejected, ADR-005 reaffirmed not
amended); never becomes the governed model (DuckDB+S3 stays sole system of record, ADR-007 B8).
- **Status (2026-06-21):** gate-0 (B2 version pins + B3 `spark_gym_guard.py` fail-closed
  preflight) + B5 (`spark_delta_demo_v1` DAG, parse-test green) + B6 (CI gates for `spark/**`)
  + B8 (`reconcile.py` two-engine row-count/key-set check) + B9 (`spark/README.md`
  honesty-scoping) all **CLOSED, GREEN** — built, independently re-verified through DPE →
  senior-DE → DA, each re-deriving from source. See `SIGN_OFF_LOG.md` "ADR-007 gate-0 + B5/B6/B8/B9
  build closure". Run via `spark/README.md`'s documented commands or the new DAG.
- **2026-06-21: B4 + B7 closed.** B4 — `scripts/provision_s3_staging.sh` run (owner-confirmed)
  against real AWS: bucket `novartis-pharma-sttm-spark-staging` (ap-southeast-1), versioning ON,
  30d noncurrent lifecycle bucket-wide + 7d short-TTL on `delta/`, region-lock policy. **Not yet
  usable** by `spark_session_factory()` — `scripts/spark_gym_guard.py` still hard-rejects any
  non-MinIO endpoint/real-AWS creds with no demonstration-mode exception; that guard extension is
  a separate, deliberately-deferred follow-up requiring its own DPE/senior-DE/DA review (see below).
  B7 — owner supplied a real webhook URL into `.env` (`SLACK_WEBHOOK_URL`, gitignored); built
  `airflow/dags/slack_notify.py` (stdlib-only, flat-imported by both DAG files — `scripts/` isn't
  mounted by the MWAA parse gate, so the helper had to live inside `airflow/dags/` itself) wired as
  `on_failure_callback` on both DAGs, plus `sla_miss_callback` on `pharma_sttm_pipeline_v1` only
  (the BONUS half of B7 — makes the previously-decorative T055 `sla=SLA` budget actually alert).
  Re-verified for real: MWAA-faithful `scripts/parse_test_mwaa.sh` parsed both DAGs clean (zero
  import errors), then a live smoke-test POST through `notify_slack()` was owner-confirmed received
  in the real Slack channel.
- **2026-06-21: guard demonstration-mode extension built** (the B4 follow-up above). Owner
  explicitly decided the real demo reads the REAL `gold/_current/` (read-only by code
  discipline, not IAM) AND writes only to the real B4 bucket — not a MinIO-read/real-write
  hybrid. `scripts/spark_gym_guard.py` now branches on an explicit `SPARK_DEMO_MODE=1` flag
  (exact-match, mirrors `GYM_MODE`'s convention — a typo'd value falls through to drill rules
  and fails them, never silently passes): DEMO rules require `SPARK_S3_BUCKET` ==
  `novartis-pharma-sttm-spark-staging` exactly, `SPARK_READ_S3_BUCKET` ==
  `novartis-pharma-sttm-lake` exactly, `SPARK_S3_ENDPOINT` EMPTY (real creds + a non-empty
  endpoint, local or attacker-controlled, is rejected as an exfiltration vector), and
  AKID/secret MUST look real (inverted from drill mode). `spark/spark_session_factory.py` now
  branches its S3A config on whether `SPARK_S3_ENDPOINT` is set (MinIO: path-style + plain
  HTTP; demo: `fs.s3a.endpoint.region` + vhost-style + TLS) rather than hardcoding the MinIO
  shape unconditionally. New `scripts/run_spark_demo_aws.sh` sources `.env` + `.env.aws` (the
  same real-AWS overlay `run_pipeline_aws.sh` uses, so reconcile.py's DuckDB leg also reads the
  real bucket, defensively overriding any stale `gym.env` state in the same shell) and aliases
  the real creds onto the `SPARK_*` names. Verified locally: 31/31 `test_spark_gym_guard.py`
  checks pass (16 original drill checks unchanged + 15 new demo-mode checks), `py_compile` +
  `ruff` clean, and a full MinIO drill regression (`build_delta_slice.py` + `reconcile.py`, all
  5 star models row-count + key-set exact match) proves the factory refactor changed zero
  drill-mode behavior. Cabinet review (DPE/senior-DE/DA) of this guard extension is CLOSED,
  APPROVED, no findings of any severity — each persona independently re-ran the test suite,
  `py_compile`, and `ruff` themselves (not trusting the build's claim), traced both job scripts
  to confirm zero write calls against the read bucket, and added one adversarial check beyond
  the shipped suite. See `SIGN_OFF_LOG.md` "ADR-007 B4 guard demonstration-mode extension"
  entry. **Still not yet run for real** — `scripts/run_spark_demo_aws.sh` itself remains
  owner-gated; this review clears the guard mechanism only, not the real-AWS run, which needs
  its own separate explicit owner confirmation before execution.
- Side-effect of this build: `docs/ADR/ADR-006-A1-incubator-fidelity-amendment.md` gained an
  addendum downgrading the sealed-rubric "stays untracked" requirement (repo went private; owner
  deliberately tracked the rubric for cikgu-teaching durability) — `ci.yml`'s now-superseded
  untracked-check step was removed accordingly, owner-approved.

## Lead Deliverables (Architecture Handbook / Erwin ERD / STTM)
- `docs/architecture_handbook/AH.md` — consolidated architecture, owned by @data-architect
- `docs/erwin/ERD.md` — Erwin-style model (Enrich/Mart/RRD), owned by @data-architect
- `docs/sttm/STTM.md` — source-to-target mapping, approved by @data-architect
- Publish to Confluence: @data-platform-engineer runs `scripts/publish_to_confluence.py`
  only after @data-architect approval; @project-manager logs the event in SIGN_OFF_LOG.md
- Practical skills reference: `cheatsheets/DE_SKILLS_DICTIONARY.md`

## Hard Blockers
**Phase 2 → 3**:
- [ ] Grain defined per fact table
- [ ] DA + DPE sync confirmed
- [ ] Source pattern decided

**Phase 3 → 4**:
- [ ] DATA_MODEL.md signed off
- [ ] SCD type per dimension confirmed
- [ ] Storage vs compute trade-off documented

**Phase 4 → 5**:
- [ ] All unit tests pass
- [ ] QA sign-off local
- [ ] DPE confirm cloud readiness

## Cikgu Score
Current: <N>/100
Threshold breaks: 60 (force docs read), 40 (remedial), 0 (pair-prog with Senior DE)

## What NOT To Commit
CLAUDE.md, PROJECT_STATUS.md, COST_LOG.md, JOURNEY_LOG.md, LEARNING_LOG.md,
DEBUG_CHECKPOINT.md,
HINT_LOG.md, DECISION_LOG.md, DOCS_CONSULTED.md, INFRA_LIMITS_LOG.md,
SIGN_OFF_LOG.md, BLOCKER_LOG.md, DEBATE_LOG_phase_*.md, INTERVIEW_GUIDE.md,
.env*, data/, *.parquet, *.csv, *.xlsx

## How To Resume
1. Read `PROJECT_STATUS.md` → "Next Step When Resuming"
2. Prompt: "Sambung dari [phase]"
3. Execute — don't re-explain
