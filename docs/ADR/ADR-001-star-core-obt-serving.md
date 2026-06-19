# ADR-001: Star schema as system-of-record, OBT as derived serving layer

**Status**: Accepted
**Date**: 2026-06-18
**Decider**: Data Architect (with Senior Data Engineer)

## Context
Three divergent project sources (Alpha=sales/ATC, Beta=NDC product master, Gamma=free-text reviews)
must be consolidated into one governed warehouse. The core deliverable is a **conformed `dim_drug`**
that reconciles three different definitions of "a drug". Senior Data Engineer argued for One Big
Table (OBT) on Snowflake for query/BI performance and DAG simplicity. Data Architect argued for a
Kimball star to preserve a single source of truth, clean SCD2, and clean STTM lineage.

## Decision
Use **both, at different layers**:
- **Data Mart = Star schema (Kimball)** — the *system of record*. Conformed dimensions
  (`dim_drug` SCD2, `dim_date`, `dim_condition`), fact tables (`fact_sales`, `fact_review`).
  All STTM lineage maps to this layer. Governance lives here.
- **RRD / serving = OBT** — wide denormalized tables **materialized from the star** (dbt models),
  clustered for BI consumption at the 7AM SLA. OBT is *derived*, never a source of truth.

## Consequences
(+) Single governed definition of every drug → consolidation showcase intact.
(+) SCD2 handled once on `dim_drug`; OBT rebuilt from star on dimension change (no mass rewrite).
(+) STTM/backward-lineage drills map to stable star targets.
(+) Trainee practices BOTH paradigms (Kimball modelling + denormalization/clustering).
(-) More models + joins than a pure-OBT design (acceptable; build is "thick" by choice).
(-) OBT must be kept in sync with star (dbt dependency + tests).

## Alternatives Considered
1. **Pure OBT (system of record)** — rejected: no single source of truth for `dim_drug`, SCD2
   becomes a mass-rewrite, STTM lineage forks across repeated attributes.
2. **Pure star (no OBT)** — rejected: heavier BI-time joins on `fact_review` (~215k rows) risk the
   7AM SLA; serving OBT is cheap to materialize and de-risks it.

## Stakeholder Sign-off
- Data Architect: APPROVED
- Senior Data Engineer: APPROVED (OBT at serving satisfies perf concern)
- FinOps review: APPROVED (OBT materialization is bounded, local-first)
