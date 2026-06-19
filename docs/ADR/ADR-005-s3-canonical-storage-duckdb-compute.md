# ADR-005: S3 as canonical storage; DuckDB as sole compute (compute stays hybrid)

**Status**: Accepted (conditional — guardrails + Conditions A–D below must hold before build)
**Date**: 2026-06-18
**Decider**: Data Architect (veto) — co-signed FinOps review + Senior Data Engineer + Data Platform Engineer (APPROVED-WITH-AMENDED-CONDITIONS — P1 tightened, P5 added; see below)
**Supersedes**: storage rows of ADR-002 (Landing/Bronze "Dev (local)" columns). ADR-002's
immutability/replay/lineage requirements are **preserved**, not removed.

## Context
ADR-002 placed Landing + Bronze as **local** files (DuckDB raw schema), with S3 only a
short "cloud artifact window" mirror torn down after the run. The project owner has
redefined "hybrid":
- **Storage = cloud-only.** All tiers (Landing, Bronze, Silver/Gold outputs) live as files
  in a single S3 bucket structure. S3 is the canonical source of truth — no local `data/`
  persistence as source of truth.
- **Compute = hybrid.** Dev: DuckDB runs locally but reads from / writes back to S3 (httpfs).
  Cloud: the *same* DuckDB ELT is orchestrated by MWAA. No new compute service introduced.

Glue/Lambda were evaluated and **rejected** — outside the locked stack hard-limit list.

## Decision
1. **S3 is canonical storage for every layer.** Logical prefixes:
   `s3://<bucket>/landing/{alpha,beta,gamma}/<date>/` ·
   `s3://<bucket>/bronze/...` · `s3://<bucket>/silver/...` · `s3://<bucket>/gold/...`
2. **DuckDB is the sole ELT/compute engine** across landing→bronze→silver→gold, reading and
   writing S3 via `httpfs`. dbt runs on the **dbt-duckdb** adapter. Same engine in dev (local)
   and cloud (MWAA-orchestrated) — only the orchestrator host changes, not the engine.
3. **Snowflake is demoted to a serving veneer.** It is *not* a storage/compute tier. During the
   short cloud window only, Snowflake reads Gold S3 files as **external tables** for a BI/serving
   demo. Real compute is DuckDB; Snowflake is read-only proof of "warehouse over lakehouse".
4. **Glue/Lambda dropped.** Deploy compute path stays MWAA + DuckDB + dbt (+ Snowflake serving).

| Layer | enVision | Storage (canonical) | Compute | Cloud serving |
|-------|----------|---------------------|---------|---------------|
| Landing | Landing | `s3://.../landing/` (immutable, versioned) | — (ingest writes raw) | — |
| Bronze | Bronze/Raw | `s3://.../bronze/` (+ `load_ts`, `source_file`) | DuckDB (httpfs) | — |
| Silver | Enrich | `s3://.../silver/` | dbt-duckdb | — |
| Gold | Data Mart + RRD | `s3://.../gold/` | dbt-duckdb | Snowflake external tables (short window) |

## Consequences
(+) One logical layout, one compute engine — truly hybrid (local engine ↔ cloud orchestrator).
(+) Immutable Landing is **stronger** in S3 (object versioning + write-once prefix) than a local folder.
(+) Near-zero permanent cost: S3 storage is cents/GB-mo; Snowflake only spun up for the window.
(−) **Finops premise changes**: S3 is now always-on, not torn down. The "short window teardown
    ≈ $3–5" line in ARCHITECTURE.md must be rewritten. Steady-state S3 = a new (small) COST_LOG item.
(−) Dev-loop egress/request risk: DuckDB re-pulling Landing on every rebuild. Mitigated below.
(−) One extra serving hop (Snowflake external tables) — accepted for the portfolio talking point.

## Guardrails (conditions of approval)
- **Immutability enforced technically**: S3 bucket versioning ON + write-once policy on `landing/`.
  Replay = re-run DuckDB against an immutable `landing/<date>/` snapshot.
- **Load metadata contract retained**: every bronze+ object carries `load_ts` / `source_file`.
- **Dev-loop cost guard**: same-region bucket only; local DuckDB read-cache so unchanged Landing
  is not re-pulled; COST_LOG line item for steady-state S3 (storage + GET/egress).
- **No cloud provisioning** (bucket create, Snowflake stage, MWAA) until FinOps review signs off
  and the owner explicitly confirms — provisioning is gated, not implied by this ADR.

## Alternatives Considered
1. **Glue/Lambda as cloud compute** — rejected: outside locked stack hard-limit; would need a
   separate stack-amendment debate, not a rider on a storage change.
2. **Drop Snowflake entirely (pure DuckDB lakehouse)** — viable and simpler, but loses the
   Snowflake portfolio keyword for the pharma/enterprise JD. Owner chose the serving veneer.
3. **Keep ADR-002 local-first storage** — rejected by owner: wanted cloud-only storage truth.

## Implementation Conditions (from Senior Data Engineer sign-off — non-negotiable before build)
- **A. Per-layer write/publish contract.** S3 has no atomic rename. Gold: write to `gold/<run_id>/`
  then flip a pointer (temp-prefix swap). Bronze/Silver: deterministic per-`<date>` partition
  overwrite. "DuckDB COPY TO S3" alone is NOT idempotent — replay safety comes from this contract.
- **B. dbt-duckdb `external` materialization** with explicit `location` for any model canonical in S3
  (Silver, Gold). Intermediate stays `ephemeral`. Verify the pinned dbt-duckdb version supports it.
- **C. Ephemeral DuckDB catalog.** In-memory + httpfs; parquet-on-S3 is the only source of truth.
  No persistent `warehouse.duckdb` as record (required for stateless MWAA workers too).
- **D. Migration ≈ 2 days.** This is a source-binding refactor of ALL staging models + sources.yml
  + `load_bronze.py` (relational `bronze.x` tables → `read_parquet('s3://...')`), not a path swap.
  Business logic (unpivot, crosswalk, marts) unaffected.

## FinOps Conditions (from FinOps review sign-off)
- Steady-state always-on S3 ≈ **<$1/mo** at low-GB scale — trivial. Real risk = **cross-region
  egress trap** (~$22+/mo if misconfigured). Mitigations made mechanical:
- **Region lock is mechanical** (bucket region == compute region; cross-region read fails loud).
- **S3 lifecycle policy**: expire noncurrent object versions after ~30 days (cap versioning cost).
- **Verify dev-loop read-cache**: a no-change `dbt run` must issue ~0 Landing GETs.
- **COST_LOG**: remove stale "$3–5 short-window teardown" line; add steady-state S3 + egress-watch.
- Note: Condition A's `gold/<run_id>/` publish multiplies object/LIST count — size into the guardrail.

## Platform / Provisioning Conditions (from Data Platform Engineer sign-off)
*Independent review performed 2026-06-18 — no debate-log entry existed for this ADR prior to this
review (unlike the real Phase 4 debate, `docs/DEBATE_LOG_phase_4.md`); P1–P4 below were pre-drafted
placeholders. This pass actually verified each against the current codebase. P1 amended, P5 added —
see rationale inline.*
- **P1 (amended).** Snowflake external tables bind to the published `gold/_current/<run_id>/` pointer —
  never a path DuckDB mutates in place. Single bucket, dual reader: DuckDB writer role + Snowflake
  read-only STORAGE INTEGRATION scoped to `gold/*` only. **Gap found in the original wording**: it
  named the roles but not what makes the *pointer swap itself* safe to read mid-flip. Closing that:
  the pointer object (`gold/_current/<run_id>` marker, e.g. a zero-byte key or small manifest) MUST be
  written via a single PUT (S3 PUTs are atomic at the object level — there is no partial-object read),
  and the external table's stage path must reference the pointer file's *resolved* `run_id`, not a
  mutable alias Snowflake re-resolves per query. Practically: either (a) the external table DDL is
  re-pointed (`ALTER EXTERNAL TABLE ... SET LOCATION`) by the same publish task that flips the pointer,
  atomically after the new `gold/<run_id>/` write completes and is verified, or (b) Snowflake always
  reads through a fixed `gold/_current/` prefix that itself contains only fully-written, immutable
  files (i.e. the "swap" copies/links objects into `_current/` only after the new run_id's write is
  100% complete, never updates an object in place). Pick one mechanism explicitly in the build PR —
  the ADR text alone under-specifies which, and the two have different blast-radius/rollback profiles.
- **P2.** `aws:RequestedRegion` Deny in the bucket policy **at create time** → cross-region = hard 403,
  not silent egress. Plus CI pre-flight region assertion (fail DAG red on mismatch).
- **P3.** Versioning ON + noncurrent-version expiry (30d) + `landing/` delete-deny ship in the **same
  create step** as the bucket (a versioned bucket with no lifecycle is the silent-cost footgun).
- **P4.** DuckDB httpfs pinned + **offline-loadable** on MWAA workers (bake into requirements/plugins;
  no runtime `INSTALL`). Creds via MWAA execution role (`credential_chain`), keys only in dev `.env`.
  Validate on MWAA-local-runner first. **Scope note**: P4 covers the DuckDB extension only — it does
  NOT cover the Airflow-core version risk. See P5.
- **P5 (new — real gap closed).** Local dev currently runs unpinned `apache-airflow==3.2.2` in
  `.venv`; AWS MWAA only supports the 2.10.x line (`docs/OPS_RUNBOOK.md` Session Start Checklist
  already flags this: "DAG has not yet been parse-tested against an MWAA-compatible Airflow version").
  This is independent of S3/DuckDB and would block an MWAA spike regardless of ADR-005, but ADR-005's
  Provisioning step (4) ("MWAA env, httpfs pinned [P4]") reads as if P4 alone clears MWAA for takeoff —
  it doesn't. Before any MWAA environment is created: (a) pin a 2.10.x Airflow version in a
  cloud-targeting requirements file (do not touch the dev `.venv`'s unpinned 3.x — keep dev/cloud
  requirements files separate, since `aws-mwaa-local-runner` and dev tooling may legitimately want
  different pins), (b) parse-test `pharma_sttm_pipeline.py` against that 2.10.x version via
  `aws-mwaa-local-runner` (TaskFlow `@dag`/`@task`/`@task_group` decorator surface is the most likely
  break point across major versions — confirm before assuming compatibility), (c) only then proceed to
  httpfs offline-load validation under P4. P4 and P5 are sequential gates, not parallel ones — P5 first.

## Provisioning & Teardown (owned by Data Platform Engineer — OWNER-GATED)
Create order: (1) S3 bucket in lock region w/ versioning+lifecycle+policy [P2/P3] → (2) IAM writer
policy on MWAA role + dev user → (3) Snowflake STORAGE INTEGRATION + `snowflake-gold-reader` role on
`gold/*` [P1] → (4) MWAA env, gated on Airflow-version parse-test passing first [P5], then httpfs
pinned [P4]. Teardown after window: MWAA + Snowflake serving + Snowflake IAM trust. **S3 bucket NOT
torn down** (always-on canonical). No AWS `apply` without explicit owner confirmation — these
sign-offs authorize the PLAN, not the apply.

**Note on step (3) — not a clean slate.** `NOVARTIS_STTM_ROLE`/`_WH`/`_DB` already exist in the trial
account, provisioned under ADR-004's least-privilege model (the role owns the schemas it creates;
no `FUTURE` grants; see `PROJECT_STATUS.md` and `docs/ADR/ADR-004-snowflake-rbac.md`). A `STORAGE
INTEGRATION` + `gold/*`-scoped `snowflake-gold-reader` role is a *different object class* (external
stage/read-only reader, not a transform role that owns its own schemas) and must be layered onto the
existing account, not created against an empty one. The ADR's create-order list doesn't say whether
`snowflake-gold-reader` is a new role alongside `NOVARTIS_STTM_ROLE` or a grant added to it — that
ambiguity should be resolved in the build PR, not left implicit. Recommend a new, separate role
(consistent with ADR-004's "owner vs scoped-grant" alternative, deferred there for lack of a use case
that has now arrived) so the existing transformer role's blast radius isn't widened to include
external-table privileges it doesn't need.

## Stakeholder Sign-off
- Data Architect: APPROVED (veto holder) — guardrails above must hold
- FinOps review: APPROVED-WITH-CONDITIONS — region lock mechanical, version lifecycle, COST_LOG update
- Senior Data Engineer: APPROVED-WITH-CONDITIONS — Conditions A–D (D's ~2-day sizing independently
  verified against current `load_bronze.py` / `_sources.yml` / `stg_alpha__sales.sql` — confirmed not
  understated; see Data Platform Engineer review note below)
- Data Platform Engineer: APPROVED-WITH-AMENDED-CONDITIONS — P1 tightened (pointer-swap atomicity
  mechanism must be explicit, not implied), P5 added (Airflow 3.x-dev/2.10.x-MWAA version gap is a
  real, currently-undocumented-in-this-ADR risk per `docs/OPS_RUNBOOK.md`'s own Session Start
  Checklist finding) — sequence P5 before P4 in any MWAA spike; owns provisioning + teardown,
  owner-gated; Snowflake step (3) is additive to the already-provisioned ADR-004 account, not a clean
  slate — new role recommended over widening `NOVARTIS_STTM_ROLE`
