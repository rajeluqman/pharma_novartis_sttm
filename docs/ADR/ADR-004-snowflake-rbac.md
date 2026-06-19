# ADR-004: Snowflake least-privilege role model for the dbt transformer role

**Status**: Accepted
**Date**: 2026-06-18
**Decider**: Data Architect

## Context
`scripts/setup_snowflake.sql` provisioned `NOVARTIS_STTM_ROLE`/`_WH`/`_DB` for the Phase 4 build.
The first version granted `GRANT ALL ON DATABASE`, `GRANT ALL ON SCHEMA ... PUBLIC`, and
`GRANT ALL ON FUTURE SCHEMAS/TABLES IN DATABASE` to that role. The Phase 4 retroactive review team
review (`docs/DEBATE_LOG_phase_4.md`) vetoed this: `ALL` hands the dbt runtime role
ownership-class privileges (`CREATE`/`MODIFY`/`MANAGE GRANTS`/`DROP`) over the entire database and
every object that will ever exist in it — far beyond what a transform role needs, and exactly the
habit RBAC governance exists to prevent regardless of whether the account is a free trial.

## Decision
`NOVARTIS_STTM_ROLE` gets exactly:
- `USAGE` on the warehouse (unchanged — already correct, never needed more than this)
- `USAGE` on the database
- `CREATE SCHEMA` on the database
- `USAGE` on the default `PUBLIC` schema (unused in practice — every dbt model has an explicit
  custom `+schema` in `dbt_project.yml`, so nothing actually lands in `PUBLIC`)

No `FUTURE SCHEMA`/`FUTURE TABLE` grants exist. Because the role provisions its own working
schemas (`enrich`, `data_mart`, `rrd`, `snapshots`) itself via the `CREATE SCHEMA` privilege, it
becomes the **owner** of each schema it creates and therefore already has full rights on the
objects inside them — no broader grant is needed for dbt to function.

## Consequences
(+) The role cannot drop/alter objects outside what it created, cannot manage grants, cannot touch
    other databases/schemas — blast radius is contained to its own schemas.
(+) Matches the standard "transformer role owns its own build schemas" dbt-on-Snowflake pattern;
    nothing here would need to change if this script were later pointed at a non-trial account.
(-) If a future need arises for this role to read from a separately-owned *raw/source* schema (e.g.
    data landed by a different ingestion role), an explicit `GRANT SELECT ON FUTURE TABLES IN
    SCHEMA <source_schema>` will need to be added then — deliberately not pre-granted now since no
    such schema exists yet.

## Alternatives Considered
1. **Keep `GRANT ALL`** — rejected: ownership-class privileges for a transform role is the exact
   anti-pattern least-privilege RBAC exists to prevent; "it's a trial account" is not an exception.
2. **Separate OWNER role + TRANSFORMER role** (the fuller enterprise pattern: one role owns objects,
   a second role gets scoped grants to operate on them) — deferred: with a single role provisioning
   and owning its own schemas, the owner/transformer split adds a second role to manage for no
   present benefit at this scale. Revisit if/when a second pipeline or a separate ingestion identity
   needs to write into the same database.

## Stakeholder Sign-off
- Data Architect: APPROVED (this ADR resolves the veto recorded in `docs/DEBATE_LOG_phase_4.md`)
- Scope Guardian: noted — re-grant is corrective, not new scope
