# LEARNING_LOG.md
**Owner**: @cikgu

Every question user asks → captured here as study notes.

---

## [2026-06-19] — HANDOVER TO CIKGU (cabinet → owner)
**Event**: Build phase complete; owner takes over to LEARN (Track B).
**State handed over**:
- **Track A (build)** done: 3-source pharma pipeline → governed star + OBT, all tests green.
- **ADR-005 S3-canonical migration LIVE on real AWS** (this session): S3 storage + DuckDB httpfs
  compute + Snowflake external-table serving veneer (`obt_*_ext`, 16,848 / 215,063 rows). KPIs ==
  baseline. AH v3 / ERD v2 / STTM v3 re-published to Confluence.
- **Track B (SLA gym)** seeded: @senior-data-engineer self-play solved **L3 / L5 / L8** as worked
  examples (`docs/sla/SABOTAGE_LOG.md`, `docs/sla/SLA_ANALYSIS.md`, `airflow/dags/gym_l{3,5,8}_*.py`).
**Where the owner starts**: read `SLA_GYM_PROMPT.md` + `learning/CURRICULUM.md`, then build **L1**
(`hello_pharma`) hands-on — ticket waiting at `learning/diy/TICKET_l1_hello_pharma.md`.
**Cikgu contract reminder**: WHY before HOW; minimal hints (−5 score each); the L3/L5/L8 answer keys
exist but the owner must RE-DERIVE — don't open `gym_l8_*` before earning it.
**Score**: 100/100 (no hints spent yet).
**Concept tags**: #handover #airflow #sla #critical-path

---

## Concepts Mastered (no hints needed)
- (none logged yet — owner hasn't started Track B)

## Concepts Struggling (multiple hints)
- (none yet)
