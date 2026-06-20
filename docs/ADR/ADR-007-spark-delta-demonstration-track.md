# ADR-007: Parallel Spark + Delta DEMONSTRATION track (local[*], Glue-ready, never run on paid compute)

**Status**: Accepted — APPROVED WITH BINDING CONDITIONS (B1–B9 below must hold; conditions are testable, not prose)
**Date**: 2026-06-20
**Decider**: Data Architect (ULTIMATE VETO on architecture/data-model/governance — owns ADRs)
**Reviewed by**: Senior Data Engineer (feasibility — FEASIBLE WITH CHANGES) · Data Platform Engineer (infra — GREEN WITH CONDITIONS)
**Relates to**: ADR-005 (locked stack), ADR-006 / ADR-006-A1 (Track-I gym + fail-closed guard), ADR-001 (star + OBT)
**Does NOT supersede ADR-005.** ADR-005's stack boundary remains the production stack of record. This ADR adds a *non-production demonstration* track alongside it.

## Context
The locked stack (ADR-005) is DuckDB-only compute, S3-canonical storage, and explicitly **REJECTED AWS Glue/Lambda** as production compute. Internal stack notes restate "Stack boundary = HARD LIMIT."

The owner's resume claims PySpark, Delta Lake, Z-Ordering, AWS Glue (PySpark), and Slack alerting — none currently *demonstrated* in this DuckDB-only repo. The proposal is a parallel `spark/` track that runs PySpark on `local[*]` (s3a connector JAR only, no Hadoop cluster), writes Delta to a separate small S3 staging bucket, and reproduces the troubleshooting incidents on Spark+S3 — converting *claimed* skills to *demonstrated* on the same dataset. The DuckDB+MinIO pipeline is NOT torn down. "Glue-ready, Glue never run" — the same cost discipline already governing MWAA-local (orchestrator demonstrated locally, the paid managed service never provisioned).

The proposal also fixes two real, already-documented production defects first (Fasa A): `O-AIR-07` (orchestrated run cannot complete — staging `view` dies across the subprocess/`:memory:` task boundary) and `P-PMR-07` (`stg_beta__ndc` non-idempotent dedup, missing tie-break).

## The core governance question — RULED

**Does a parallel Spark+Delta DEMONSTRATION track (local[*], Glue-ready, never run on paid compute) EXTEND ADR-005's hybrid/cost-discipline principle, or VIOLATE its "stack boundary = HARD LIMIT / Glue rejected" letter?**

**Ruling: it EXTENDS the principle — it does NOT violate the boundary — *provided* it stays inside the demonstration-track fence defined below.** Reasoning, anchored in ADR-005, not opinion:

ADR-005's Alternative #1 rejected "**Glue/Lambda as cloud compute**" — i.e. as a *production compute path* that the deployed pipeline runs on (paid, managed, always-eligible-to-run, widening the operational/IAM/cost surface). ADR-005 §4 ("Deploy compute path stays MWAA + DuckDB + dbt") governs the **deploy compute path**. A `local[*]` SparkSession that never submits to Glue is not a deploy compute path — it never enters the production lineage, never serves Gold, never runs on paid/managed compute. It is the *same category* as `aws-mwaa-local-runner`: the project's stack table already blesses demonstrating an AWS managed service (MWAA) via a local runner without provisioning the paid service. Spark-on-`local[*]` is that exact pattern for the compute engine.

So this is not stack creep into ADR-005's production stack; it is a clearly-fenced *non-production demonstration* track. ADR-005's letter rejected Glue **as production compute** — that rejection is untouched and reaffirmed here. What ADR-005 did *not* rule on is whether non-production, never-paid-compute demonstration code may live in the repo. This ADR rules that it may, under the fence.

### The PRINCIPLE that distinguishes a "demonstration track" from "stack creep"
(Stated so this ADR cannot be cited to justify arbitrary future tool additions.) A tool may enter the repo *outside* the ADR-005 locked stack **only if ALL FIVE hold** — fail any one and it is stack creep, requiring a full ADR-005 stack-amendment debate, not a rider:

1. **Additive, never substitutive.** It does not replace, fork, or degrade the ADR-005 production path. The DuckDB+S3 pipeline remains the sole system of record and the sole thing the deploy path runs.
2. **Never runs on paid/managed cloud compute.** `local[*]` only; Glue/EMR/Lambda code may exist but is NEVER `apply`/submitted. Identical to MWAA-local discipline.
3. **Mechanically guard-isolated from the live lake.** It reaches no production bucket; a fail-closed guard (not prose) enforces this — the ADR-006-A1 standard.
4. **Derives from, and never becomes, the governed data model.** It reads the same ADR-001 star inputs; its outputs are demonstration artifacts, never a second system of record, never read by Snowflake/serving.
5. **Honestly scoped — no over-claim.** What `local[*]` cannot show (real shuffle, executor loss/recovery, dynamic allocation) is stated, not implied.

This fence is the binding test for any future "demonstration track" proposal. ADR-007 is precedent for the *pattern*, not a blanket license for tools.

## Decision
1. **Fasa A (production fixes) is approved and sequenced FIRST**, independent of the Spark track. See B1.
2. **A parallel `spark/` demonstration track is approved** under conditions B2–B9. It is non-production, additive, `local[*]`-only, guard-isolated, and derives from the ADR-001 star.
3. **ADR-005's stack boundary is reaffirmed, not amended.** Glue/Lambda remain rejected *as production compute*. This ADR governs only the demonstration fence above.
4. **A new ADR (this one) IS required** — not an amendment to ADR-005 (it does not change the production stack) and not to ADR-006 (it is not a gym-mechanism change). It is a new architectural decision: admitting a fenced non-production track. (Contrast ADR-006-A1, which was a mere amendment because it only refined an *existing* decision's implementation.)

## Binding Conditions (testable — each names its proof)

**B1 — Fasa A first, and the O-AIR-07 framing is corrected (amends the proposal).** Adopting the Senior Data Engineer's correction: the SCD2 snapshot already survives task boundaries via the existing `on-run-start/end` S3 roundtrip hooks (`snapshot_s3_roundtrip.sql`); the ONLY real `O-AIR-07` failure is that `marts.core`/`dim_drug` reads the staging **VIEW**, which is gone in a separate subprocess. **External-materializing staging to S3 via the unused `silver_location()` macro IS the whole fix; the snapshot leg gets NO new work.** Proof: a gym-lake rep showing `dbt_marts` re-reads `silver/` parquet, not an in-memory view, and the orchestrated DAG completes a full run end-to-end. `P-PMR-07`: copy the `int_drug_crosswalk` tie-break pattern (secondary key); proof = same-day rerun no longer inflates `dim_drug` SCD2 history (the 133,654→133,758 regression closes). **Data-model/lineage note (B1a):** staging ceases to be a transient `view` and becomes a **materialized Silver layer on S3** under `silver/`. This is consistent with ADR-005 Implementation Condition B (dbt-duckdb `external` materialization with explicit `location` for any model canonical in S3) and ADR-005's Silver row — it does NOT introduce a new layer, it makes the *already-specified* Silver materialization real. `silver/` is governed by ADR-005's per-`<date>` deterministic-overwrite contract (Condition A). Lineage in ARCHITECTURE.md / ERD does not change shape; only the staging materialization strategy is now "external," as ADR-005 already required.

**B2 — Java pin (clears the Senior Data Engineer's soft veto).** Pin Java 21 (21.0.10-ms via sdkman) for the `spark/` track; Codespace-default Java 25 will not run Spark. Pin the version matrix: Spark 3.5.x → `hadoop-aws:3.3.4` + `aws-java-sdk-bundle:1.12.262` + `delta-spark` 3.2.x (NOT Spark 4). Proof: documented in a `requirements/requirements-spark.txt` mirroring the `requirements-mwaa.txt` pinning precedent (ADR-005 P4/P5 pinning discipline), with jar coordinates locked.

**B3 — `spark_gym_guard.py` is the LOAD-BEARING HARD GATE (adopts Data Platform Engineer condition C1).** This is the condition that makes the Spark track governable at all. The existing `gym_guard.py` inspects DuckDB-httpfs env vars (`S3_BUCKET`/`S3_ENDPOINT`) — Spark reaches S3 through a DIFFERENT client (`spark.hadoop.fs.s3a.*` in SparkConf) that the existing guard NEVER inspects. Without a Spark-specific guard, a sabotage drill could be guard-green and still mutate the live `novartis-pharma-sttm-lake`. This re-opens exactly the fail-open blast-radius hole ADR-006-A1 §1 closed for DuckDB — **unacceptable**. BINDING: build `scripts/spark_gym_guard.py` + a single `spark_session_factory()` that EVERY SparkSession routes through; it asserts (a) only-allowed bucket == the gym staging bucket, (b) `fs.s3a.endpoint` ∈ {localhost,127.0.0.1,minio} for drills, (c) `fs.s3a.access.key` is not a real `AKIA`/`ASIA` key. **NO raw `SparkSession.builder` anywhere under `spark/`.** Proof: a fail-closed test (guard ABORTS on a non-gym bucket/endpoint/real-key combination) + a grep CI assertion that `SparkSession.builder` appears only inside the factory. Until B3 passes, the Spark track is structure-only and MUST NOT run a sabotage drill (mirrors ADR-006-A1's "no drill until guard in place").

**B4 — Separate staging bucket, owner-gated (adopts Data Platform Engineer condition C2).** A DISTINCT bucket via `provision_s3_staging.sh`: region-lock + public-access-block + versioning + 30d noncurrent lifecycle + a SHORT-TTL expiry on staging prefixes (Delta/Z-Order rewrites multiply object versions — a cost footgun, same risk class ADR-005 FinOps flagged for `gold/<run_id>/`). Provisioning stays OWNER-GATED per ADR-005 ("no AWS apply without explicit owner confirmation"). **Reuse the running `gym-minio` container with a new staging bucket for DRILLS** — real-AWS staging bucket is for the *demonstration*, MinIO for *drills*.

**B5 — DAG subprocess shape (adopts Data Platform Engineer condition C3, and must not repeat O-AIR-07).** The new Airflow DAG shells out via `spark-submit` subprocess (same pattern as the existing DAG) and MUST pass `parse_test_mwaa.sh`. It MUST NOT replicate the `O-AIR-07` multi-subprocess-shared-state trap — keep single-process, or S3-staging-backed between tasks. Proof: parse-test green + a run that completes across task boundaries.

**B6 — CI static gates extended (adopts Data Platform Engineer condition C4).** Extend `ci.yml`: `spark/**/*.py` → `py_compile` + `ruff`; assert the pinned jar coordinates (B2) are present and unchanged; assert B3's no-raw-builder grep. Data-free, $0 (consistent with ADR-006-A1 §6 CI scope, PR→main).

**B7 — Slack secret hygiene (adopts Data Platform Engineer condition C5).** Slack webhook is env-only, NEVER committed (consistent with ADR-006-A1 §1 fake-creds / no-real-keys discipline). BONUS adopted as a requirement-of-honesty: wire Slack to the EXISTING DuckDB DAG too, so the resume's Slack claim is backed on the PRIMARY pipeline, not only the demo track.

**B8 — Two-engine data-model consistency (Data Architect-owned governance).** Both the DuckDB mart and the Spark+Delta slice derive from the SAME ADR-001 star. To prevent silent divergence into two systems of record, BINDING: (a) **DuckDB+S3 remains the SOLE system of record**; the Spark+Delta output is a *demonstration artifact* in the staging bucket, NEVER read by Snowflake/serving, NEVER published to `gold/_current/`. (b) A **reconciliation check** — Spark+Delta's slice must row-count and key-set match the DuckDB mart for the same `<date>` (reuse the existing reconciliation discipline that ADR-006-A1 §5 made the universal diagnostic). A divergence is a defect to investigate, not an accepted fork. Proof: a reconciliation rep (counts + key-sets equal) committed alongside the slice. This is the data-model fence (principle #4) made testable.

**B9 — Honesty scoping (adopts the Senior Data Engineer's review; principle #5 made testable).** The `spark/` README/docs MUST state explicitly that `local[*]` demonstrates the Spark API / Catalyst-AQE plans / Delta transaction log / `OPTIMIZE ZORDER` / broadcast-vs-sort-merge selection, but does **NOT** demonstrate real network shuffle, executor loss/recovery, or dynamic allocation. No over-claim in any artifact or the resume narrative. **Glue-ready code stays code — do NOT balloon into unused Glue IaC**; Step Functions stay OUT of ADR-007 scope.

## Consequences
- (+) Converts claimed skills (PySpark/Delta/Z-Order/Glue-pattern/Slack) to demonstrated, on the same dataset, as an honest engine comparison — without touching the production stack.
- (+) Reaffirms ADR-005's boundary by *defining the fence* that keeps demonstration code from becoming stack creep — future "let's add tool X" proposals now have a 5-part test to pass.
- (+) Forces two real production fixes (`O-AIR-07`, `P-PMR-07`) to land first, with the corrected, cheaper framing.
- (−) A second guard surface (`spark_gym_guard.py`) must be maintained; the DuckDB guard does NOT cover Spark (B3 is precisely why). This is new, permanent maintenance.
- (−) `local[*]` has a permanent fidelity ceiling (no real shuffle/executor recovery) — accepted and disclosed (B9), analogous to ADR-006-A1's MinIO substrate limit.
- (−) Real-AWS staging bucket is a new (small) always-eligible cost line; B4's short-TTL lifecycle caps it.

## Sequencing + sign-off chain (mirrors ADR-006-A1 / Track-I clearances)
1. **Fasa A (build):** implement B1 (`O-AIR-07` external-staging fix + `P-PMR-07` tie-break). Verify via a gym-lake rep (DAG completes; same-day rerun stable). Data Architect confirms the data-model/lineage note (B1a: Silver-materialization is ADR-005 Condition B, not a new layer). **Closes** with a `SIGN_OFF_LOG.md` entry.
2. **Spark track gate 0 (B2, B3):** build `requirements-spark.txt` (Java/jar pins) + `spark_gym_guard.py` + `spark_session_factory()`. Independently re-run the fail-closed guard test (not on faith — own shell, own non-gym-bucket attempt, confirm ABORT) and the no-raw-builder grep. **No Spark drill runs until this gate is green.**
3. **Spark track build (B4–B9):** staging bucket (owner-gated), DAG (B5), CI gates (B6), Slack (B7), the Delta slice + reconciliation (B8), honesty docs (B9).
4. **Drill-readiness (mirrors C3):** a Spark sabotage drill is only authorized once B3's guard is proven against real S3-compatible storage (a MinIO `gym-lake` Spark loop), independently re-verified — the SAME evidentiary bar that cleared Track-I layers 04/05/06.
5. **Final close:** re-derive that the 5-part fence holds against the as-built track (not on faith), issue the clearance, and **close** with a `SIGN_OFF_LOG.md` entry + the governance follow-up (a project stack-notes update is a separate, not-yet-authored task).

## Stakeholder Sign-off
- Data Architect: **APPROVED WITH BINDING CONDITIONS** (veto holder) — ADR-007 GO; B1–B9 binding and testable; ADR-005 boundary reaffirmed not amended; the 5-part demonstration-fence is the controlling principle.
- Senior Data Engineer: FEASIBLE WITH CHANGES — soft-veto clears on B1 (O-AIR-07 reframe) + B2 (Java/jar pins).
- Data Platform Engineer: GREEN WITH CONDITIONS — C1→B3 (load-bearing), C2→B4, C3→B5, C4→B6, C5→B7.
