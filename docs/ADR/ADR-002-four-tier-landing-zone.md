# ADR-002: Four-tier architecture with an explicit S3 Landing Zone

**Status**: Accepted
**Date**: 2026-06-18
**Decider**: Data Architect

## Context
The enVision-style lineage in the JD is `Source → Landing → Enrich → RRD → Data Mart`. The initial
scaffold collapsed Landing into Bronze. A separate, immutable Landing Zone (raw files exactly as
received) is standard enterprise practice and is explicitly a named enVision layer.

## Decision
Adopt a **four-tier** layout, mapped to the enVision vocabulary used by the STTM:

| Medallion | enVision | Content | Dev (local) | Cloud (artifact window) |
|-----------|----------|---------|-------------|-------------------------|
| **Landing Zone** | Landing | raw files as-received (CSV/JSON), immutable, replayable | `data/landing/{alpha,beta,gamma}/` | `s3://<bucket>/landing/...` |
| **Bronze** | Bronze/Raw | raw → table + load metadata (`load_ts`, `source_file`) | DuckDB raw schema | Snowflake raw schema |
| **Silver** | Enrich | cleaned, typed, conformed; per-source (divergent) | dbt (DuckDB) | dbt (Snowflake) |
| **Gold** | Data Mart + RRD | consolidated star + OBT serving | dbt marts | Snowflake marts |

Divergence lives in Landing/Bronze/Enrich (3 separate sets). Convergence/governance lives in Gold
(one consolidated mart with conformed `dim_drug`). See ADR-001 for star+OBT, ADR-003 for the crosswalk.

## Consequences
(+) Immutable Landing enables replay/audit and faithful enVision lineage (5-hop backward trace).
(+) Same logical layout local and cloud — only the dbt target + landing backend change.
(-) One more layer to orchestrate (extra DAG tasks); acceptable for fidelity + the SLA drill.

## Alternatives Considered
1. **Landing = Bronze (3-tier)** — rejected: loses immutable raw replay + diverges from enVision naming.
2. **No medallion, direct source→mart** — rejected: no DQ gate, no lineage layering for STTM.

## Stakeholder Sign-off
- Data Architect: APPROVED
- Data Platform Engineer: APPROVED (S3 prefixes per source; local folder mirror)
- Senior Data Engineer: APPROVED
