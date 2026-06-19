# ADR-005 Build Decisions (addendum to ADR-005)

**Status**: Accepted — DESIGN RULING ONLY (not a provisioning authorization)
**Date**: 2026-06-19
**Decider**: Data Architect (veto holder)
**Parent**: `docs/ADR/ADR-005-s3-canonical-storage-duckdb-compute.md`
**Also references**: `docs/ADR/ADR-004-snowflake-rbac.md`

## Purpose & scope

ADR-005 was accepted conditionally and explicitly deferred several *how* decisions to
"the build PR" (P1's pointer-swap mechanism, Condition C's snapshot-state externalization,
the Snowflake role question, the bucket spec, fact-table materialization, and the S3 layout
contract). This addendum closes those six.

**This is a design ruling. It authorizes the PLAN, not the apply.** The owner has approved the
S3-canonical migration in principle and will reviewerlly approve the actual cloud-create commands
(`aws s3api`, Snowflake `CREATE STORAGE INTEGRATION/ROLE`, etc.) at execution time. That human
go-ahead is **out of scope here and is not mine to give** — consistent with ADR-005's
"Provisioning & Teardown (OWNER-GATED)" section and the ARCHITECTURE.md "Provisioning stays OWNER-GATED"
guardrail. **MWAA is OUT this round** — orchestration stays on local `aws-mwaa-local-runner` ($0);
P4/P5 (the MWAA Airflow-version gates) are therefore not triggered by anything decided here.

---

## Decision 1 — P1 pointer-swap atomicity: **(B) immutable `gold/_current/` prefix, copy-on-publish**

**Decision.** Adopt mechanism **(B)** from ADR-005 P1: the publish step writes the full run to
`gold/<run_id>/`, verifies completeness, then copies the fully-written, immutable objects into a
fixed `gold/_current/` prefix (objects are only ever *added* there for the new run after the old
run's objects are replaced via copy; never updated in place). Snowflake external tables read
through the **fixed `gold/_current/` prefix** and are never re-pointed per run. Mechanism (A)
(`ALTER EXTERNAL TABLE ... SET LOCATION` per `run_id`) is **rejected** for this round.

**Reasoning.** Blast radius and rollback profile decide this. With (B) the reader contract is
static — Snowflake DDL never changes, so a publish failure cannot leave the external table pointed
at a half-written or non-existent location; the worst case is `_current/` holding the *previous*
good run, which is a safe, queryable state. Rollback = re-copy the prior `gold/<run_id>/` back into
`_current/`, a pure data operation needing no DDL and no Snowflake privilege. (A) couples each
publish to a Snowflake DDL statement (re-point), which (i) requires the publish task to hold
`ALTER` on the external table, widening the writer's blast radius into Snowflake's catalog, and
(ii) makes rollback a DDL operation in a second system — two systems must agree on the current
`run_id`. (B) keeps the swap entirely in S3 where the writer already operates. The cost — extra
copy I/O and object/LIST count — is trivial at low-GB scale (ADR-005 FinOps already sized the
`gold/<run_id>/` multiplier into the guardrail). Note: the per-`run_id` history under `gold/<run_id>/`
is **retained** (immutable lineage, ADR-002 preserved); `_current/` is purely the serving pointer.

**ADR / principle ref.** ADR-005 P1 ("pick one mechanism explicitly in the build PR… different
blast-radius/rollback profiles"); ADR-005 Condition A (S3 has no atomic rename → publish = write-then-pointer);
ADR-002 immutability/replay preserved.

---

## Decision 2 — Condition C snapshot state: **externalize snapshot history to `s3://<bucket>/snapshots/`** (it is the ONE accepted persistent store, and it is data not catalog)

**Decision.** `snap_beta_ndc` history materializes to `s3://<bucket>/snapshots/snap_beta_ndc/` as
parquet (dbt-duckdb `external` materialization for the snapshot relation, explicit `location`).
The DuckDB **catalog** stays ephemeral (in-memory + httpfs) per Condition C; the snapshot's *prior
state* is read from S3 at the start of each run and the new version is written back to S3 at the
end. This is the single accepted persistent store, and it does **not** violate "no persistent
`warehouse.duckdb` as truth" because the persisted artifact is **data on S3 in the canonical layout**,
identical in kind to bronze/silver/gold — not a DuckDB catalog file acting as system of record.

**Reasoning — reconciling the tension.** The `check`-strategy snapshot (openFDA has no reliable
`updated_at`, so it diffs business columns) is *definitionally* stateful: it must read its own prior
output to compute the SCD2 diff. Condition C forbids a persistent *catalog*, not persistent *data* —
the whole point of ADR-005 is that S3 parquet IS the persistent truth and the catalog is disposable.
Snapshot history is therefore just another canonical S3 dataset; putting it under `snapshots/`
(a sibling of `silver/`, distinct because it is accumulating SCD2 state, not a per-run rebuild)
keeps it stateless-worker-safe: any worker can reconstruct the diff by reading `snapshots/` + current
`silver` Beta, with zero local state. This is what makes the snapshot replayable on a cold ephemeral
worker — exactly the property Condition C exists to guarantee. A second "accepted persistent snapshot
store" of a *different kind* (e.g. a standing DuckDB file) is rejected: it reintroduces the catalog-as-truth
footgun Condition C bans and is not stateless-worker-safe.

**ADR / principle ref.** ADR-005 Condition C (ephemeral catalog, parquet-on-S3 the only truth);
ADR-005 Condition B (`external` + explicit `location`); ADR-003 (dim_drug SCD2 crosswalk fed by this snapshot).

---

## Decision 3 — Snowflake role model: **new separate `snowflake_gold_reader` role** (do NOT widen `NOVARTIS_STTM_ROLE`)

**Decision.** Provision a **new, separate** read-only role `snowflake_gold_reader`, scoped via a
`STORAGE INTEGRATION` to `gold/*` only (in practice the `gold/_current/` prefix per Decision 1),
owning the external table(s). `NOVARTIS_STTM_ROLE` is **not** widened to carry external-table or
storage-integration privileges.

**Reasoning.** This resolves the ambiguity ADR-005's create-order list left implicit (it named the
role but never said new-vs-grant). A storage-integration external-table reader is a *different object
class* from the ADR-004 transformer role: the transformer owns the schemas it creates and operates
inside the DuckDB/Snowflake build; the reader only needs `USAGE` on the integration + `SELECT` on the
external table. Folding read privileges into `NOVARTIS_STTM_ROLE` would widen the transformer's blast
radius to include external-stage privileges it does not need — the exact least-privilege anti-pattern
ADR-004 exists to prevent. ADR-004 deferred the owner/scoped-grant split "for lack of a use case" —
the serving veneer is that use case, now arrived. Keep the split.

**ADR / principle ref.** ADR-005 P1 (DuckDB writer role + Snowflake read-only integration scoped to
`gold/*` only); ADR-004 (owner-vs-scoped-grant least-privilege principle; Alternatives #2 deferred-until-needed);
ADR-005 provisioning note ("Recommend a new, separate role").

---

## Decision 4 — S3 bucket spec: **`novartis-pharma-sttm-lake`**, region **`ap-southeast-1`**, guardrails ship in the SAME create step

**Decision.**
- **Bucket name**: `novartis-pharma-sttm-lake` (lowercase, hyphenated, DNS-compatible; `<project>-<purpose>`;
  no dots — avoids virtual-hosted-TLS issues; single canonical bucket per ADR-005 "single bucket, dual reader").
- **Region**: `ap-southeast-1` (Singapore). This **must equal the compute region** — same-region bucket is
  the mechanical region lock; cross-region read must fail loud, never silently egress.
- **Guardrails that MUST be created atomically with the bucket** (a versioned bucket with no lifecycle/policy
  is the silent-cost + security footgun — these are not a follow-up step):
  1. **Versioning ON** (immutability + replay; ADR-005 guardrails / P3).
  2. **Lifecycle: noncurrent-version expiry ≈ 30 days** (caps versioning storage cost; ADR-005 FinOps / P3).
  3. **Bucket policy `aws:RequestedRegion` Deny** — any request outside `ap-southeast-1` → hard 403, not silent
     cross-region egress (ADR-005 P2). Plus the CI pre-flight region assertion (fail red on mismatch) as the
     code-side twin.
  4. **`landing/` delete-deny (write-once)** — bucket policy denies `s3:DeleteObject` (and deny overwrite of
     existing keys) under `landing/*`, making Landing immutable-by-policy, not just by convention (ADR-005
     guardrails "write-once policy on `landing/`" / P3).

**Reasoning.** Region equality is the cheap mechanical defense against ADR-005 FinOps's single named real
risk (cross-region egress, ~$22+/mo if misconfigured) — at low-GB scale storage itself is <$1/mo, so the
egress trap, not storage, is what the spec must engineer out. Shipping versioning + lifecycle + both Deny
policies in the *same* create step is non-negotiable per P3: each is individually a footgun if it lags the
bucket's existence (an unversioned window loses immutability; a versioned-but-no-lifecycle window silently
accrues cost; a policy-less window allows cross-region reads and Landing mutation).

**ADR / principle ref.** ADR-005 P2, P3, FinOps conditions (region lock mechanical, noncurrent-version
expiry, COST_LOG), Guardrails (versioning + write-once `landing/`).

---

## Decision 5 — Incremental facts under `external`: **full deterministic rewrite** (drop `incremental`; do NOT do staging+merge)

**Decision.** Re-materialize `fact_sales` and `fact_review` as **full deterministic rebuilds** (dbt
`table` via `external` materialization to S3), removing the `incremental` + `is_incremental()` /
`load_ts > max(load_ts) from {{ this }}` pattern. A staging+merge emulation on S3 is **rejected**.

**Reasoning.** Condition A is decisive: S3 has no atomic rename, so dbt-duckdb's incremental
strategies (which lean on `MERGE`/rename/`this`-relation read-modify-write semantics) cannot be made
atomic or replay-safe over an `external` S3 location without hand-rolling a staging-prefix + swap —
i.e. re-implementing Decision 1's publish contract per model, multiplying the merge/object-count
surface and the failure modes. The incremental pattern also *requires reading `{{ this }}`'s prior
state* (`max(load_ts)`), which fights the ephemeral catalog (Condition C) — the prior fact table is not
guaranteed present on a cold worker. The facts are **small** (Alpha = ATC-category × day; Gamma reviews
are a bounded historical scrape, not an unbounded stream), so a full deterministic rewrite per run is
cheap, idempotent, and trivially replayable — the same property Decision 1 buys for Gold. Determinism is
already structurally true: surrogate keys are content-hashed (`generate_surrogate_key` on
`sale_date+atc_code` / `review_id`), so a full rebuild reproduces identical keys. This is the honest
trade: spend a little compute to delete a whole class of S3-atomicity and cold-catalog bugs.

**Note for executors (not a blocker, just don't lose it):** dropping the `is_incremental()` branch means
the `load_ts > max(...)` filter goes away — that filter was the *only* consumer of incremental state, so
removal is clean; `load_ts` itself still rides through as a column (lineage). Business logic unchanged
(ADR-005 Condition D: "business logic… unaffected").

**ADR / principle ref.** ADR-005 Condition A (no atomic rename → deterministic per-partition/full overwrite),
Condition C (ephemeral catalog, no `{{ this }}` prior-state dependency), Condition D (business logic unaffected).

---

## Decision 6 — Bronze/Silver/Gold S3 layout + load-meta contract: **confirmed**

**Decision.** Confirm the prefix layout and the load-metadata contract:

```
s3://novartis-pharma-sttm-lake/
  landing/{alpha,beta,gamma}/<date>/        # immutable, versioned, write-once (Decision 4 guardrail 4)
  bronze/<src>/<date>/                       # parquet + load_ts + source_file; per-<date> deterministic overwrite
  silver/<model>/                            # dbt-duckdb external; deterministic rebuild
  snapshots/snap_beta_ndc/                   # SCD2 history, persistent DATA (Decision 2)
  gold/<run_id>/                             # immutable per-run output (lineage retained)
  gold/_current/                             # fixed serving pointer; Snowflake reads here ONLY (Decision 1)
```

- `<src>` ∈ {alpha, beta, gamma}; `<date>` = landing/ingest date (`YYYY-MM-DD`); `<run_id>` = pipeline run id.
- **Load-meta contract**: every **bronze-and-above** object carries `load_ts` and `source_file`. This is
  already true in `scripts/load_bronze.py` (the bronze CREATE statements append `current_timestamp AS load_ts`
  and a literal `source_file`) and is carried through staging/marts (`stg_alpha__sales` keeps `load_ts`;
  facts keep `load_ts`). The migration must **preserve** this as the bronze tables become
  `read_parquet('s3://…/bronze/<src>/<date>/…')` instead of relational `bronze.x` — the columns ride on the
  parquet, not the relational table.

**Reasoning.** The layout encodes the per-layer write/publish contracts decided above into the physical
namespace: `landing/` immutable+versioned (replay), `bronze/<src>/<date>/` per-date deterministic overwrite
(Condition A), `silver/` deterministic rebuild, `snapshots/` the one persistent SCD2 data store (Decision 2),
`gold/<run_id>/` + `gold/_current/` the write-then-pointer-copy publish (Decision 1). The `load_ts`/`source_file`
pair is the lineage backbone (ADR-002 lineage preserved; ADR-005 "Load metadata contract retained") and is the
exact mechanism `fact_*` use for ordering/audit even after Decision 5 removes the incremental filter.

**ADR / principle ref.** ADR-005 Decision §1 (prefix layout), Guardrails ("every bronze+ object carries
`load_ts`/`source_file`"), Condition A (per-`<date>` overwrite, `gold/<run_id>/` + pointer), ADR-002 (lineage/replay).

---

## What this addendum does and does NOT authorize

- **DOES**: settle the six design questions ADR-005 deferred to the build PR, so the refactor/validation
  work is design-unblocked.
- **DOES NOT**: authorize any AWS or Snowflake `apply`. Every create command
  (`aws s3api create-bucket` + the four guardrails, `CREATE STORAGE INTEGRATION`, `CREATE ROLE
  snowflake_gold_reader`, grants) remains **OWNER-GATED** and requires the owner's explicit per-command
  confirmation at execution time, per ADR-005 "Provisioning & Teardown (OWNER-GATED)" and ARCHITECTURE.md.
- **MWAA is OUT this round.** P4/P5 are not in play; orchestration stays on local `aws-mwaa-local-runner` ($0).

## Sign-off
- Data Architect: APPROVED (veto holder) — design ruling; apply remains owner-gated (human).
