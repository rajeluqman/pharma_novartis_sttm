# ADR-003: Conformed `dim_drug` via crosswalk, with a partial-match policy

**Status**: Accepted
**Date**: 2026-06-18
**Decider**: Data Architect (with Business Analyst, Data Quality Steward)

## Context
The three sources identify "a drug" three incompatible ways, with **no native shared key**:
- Alpha (sales): **ATC category code** (M01AB, N02BE, …) — 8 coarse categories.
- Beta (NDC): **NDC code + generic/proprietary name + `pharm_class`**.
- Gamma (reviews): **free-text `drugName` + `condition`**.

Consolidating these into one governed dimension *is* the project's core governance test. There is no
clean join — matching is fuzzy and will be partial. We must not pretend 100% linkage is achievable.

## Decision
- Build a **conformed `dim_drug`** as the single governed drug dimension (SCD2; Beta NDC is the
  authoritative product master that feeds it).
- Build an explicit **crosswalk** mapping each source identifier to the conformed key:
  `ATC ↔ pharmacologic_class ↔ generic_name ↔ free-text drugName`.
  - ATC↔pharm_class: maintained **seed** (`dbt/seeds/atc_pharmclass_crosswalk.csv`), reviewed by Business Analyst.
  - free-text drugName → conformed: normalized match (lower/trim/synonym) with a confidence flag.
- **Partial-match policy**: matching is a tracked KPI, not a guarantee.
  - `dim_drug.match_confidence` ∈ {exact, normalized, fuzzy, unmatched}.
  - Unmatched rows route to an **exceptions table** + logged in `docs/sttm/STTM.md` exceptions.
  - Coverage % is a **DQD KPI** (target set per source, NOT 100%).

## Consequences
(+) One governed drug definition; the "Project A vs B define X differently" problem solved explicitly.
(+) Honest data quality — coverage tracked, exceptions auditable, no silent dropping.
(-) Crosswalk is the highest-effort, highest-risk component (fuzzy matching); budget accordingly.
(-) Some Gamma reviews will not link to ATC sales — accepted and surfaced, not hidden.

## Alternatives Considered
1. **Force a join / drop unmatched silently** — rejected: corrupts lineage + hides coverage gaps.
2. **Keep three separate drug keys** — rejected: defeats consolidation, the whole point of the role.

## Stakeholder Sign-off
- Data Architect: APPROVED
- Business Analyst: APPROVED (owns the approved enterprise drug definition + seed review)
- Data Quality Steward: APPROVED (owns coverage KPI + exceptions monitoring)
