# Snowflake Clustering Key Optimization

═══════════════════════════════════════════════════════════
SECTION 1: SYMPTOM DETECTION
═══════════════════════════════════════════════════════════

Symptoms observed:
  □ Query duration > 5s on table with > 1M rows
  □ Full table scan in QUERY_HISTORY (bytes_scanned ≈ table size)
  □ Filter on time-series column (event_date, created_at)
  □ Repeated queries with similar WHERE clause

Where to look:
  □ Snowflake UI → History → click query → "Profile" tab
  □ Look at "TableScan" node → "% bytes scanned" should be < 20%
  □ Run: `SELECT SYSTEM$CLUSTERING_INFORMATION('tbl', '(col)')`
  □ Check `total_constant_partition_count` vs `total_partition_count`

═══════════════════════════════════════════════════════════
SECTION 2: ROOT CAUSE INVESTIGATION (Step-by-Step)
═══════════════════════════════════════════════════════════

STEP 1: Confirm full scan
  → Run query → check Query Profile
  → If "Partitions scanned" = "Partitions total" → full scan confirmed

STEP 2: Check current clustering
  → SELECT SYSTEM$CLUSTERING_INFORMATION('your_table', '(filter_col)');
  → Look at "average_overlaps"
  → IF average_overlaps > 50 → clustering NEEDED
  → IF average_overlaps < 10 → clustering already good, look elsewhere

STEP 3: Identify hot filter columns
  → Review last 100 queries on table:
    SELECT query_text FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time > DATEADD(day, -7, current_date())
    AND query_text ILIKE '%your_table%'
    LIMIT 100;
  → Identify most common WHERE columns

STEP 4: Verify table is big enough
  → SELECT row_count, bytes / 1024 / 1024 / 1024 AS gb
    FROM information_schema.tables WHERE table_name = 'YOUR_TABLE';
  → IF rows < 1M → clustering NOT recommended (overhead > benefit)
  → IF rows > 10M and gb > 5 → clustering definitely beneficial

═══════════════════════════════════════════════════════════
SECTION 3: SOLUTION OPTIONS + TRADE-OFFS
═══════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────┐
│ OPTION 1: Single-column clustering                     │
├─────────────────────────────────────────────────────────┤
│ WHAT  : ALTER TABLE tbl CLUSTER BY (event_date)        │
│ WHY   : Most queries filter by single time column      │
│ WHEN  : One dominant filter, > 80% of queries          │
│ TRADE-OFF                                              │
│   (+) 80-90% reduction in bytes scanned                │
│   (+) Simple to implement                              │
│   (-) Re-clustering credits (~$10-50 initial)          │
│   (-) Won't help non-date filter queries               │
│                                                         │
│ STAKEHOLDER IMPACT                                     │
│   Senior Data Engineer : APPROVED                     │
│   FinOps review         : ⚠️ Monitor re-clustering cost│
│   Data Architect       : APPROVED (ADR required)      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ OPTION 2: Multi-column clustering                      │
├─────────────────────────────────────────────────────────┤
│ WHAT  : ALTER TABLE tbl CLUSTER BY (date, customer_id) │
│ WHY   : Queries filter both date AND entity            │
│ WHEN  : 2-3 dominant filter columns                    │
│ TRADE-OFF                                              │
│   (+) Better pruning for compound filters              │
│   (-) Higher re-clustering cost (2-3x single col)      │
│   (-) Order matters! Higher cardinality first          │
│                                                         │
│ STAKEHOLDER IMPACT                                     │
│   Senior Data Engineer : APPROVED                     │
│   FinOps review         : ⚠️ Higher cost, justify ROI  │
│   Data Architect       : APPROVED                     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ OPTION 3: Search Optimization Service (SOS)            │
├─────────────────────────────────────────────────────────┤
│ WHAT  : ALTER TABLE tbl ADD SEARCH OPTIMIZATION         │
│ WHY   : Point lookup queries (equality on high-card)    │
│ WHEN  : Looking up specific values, not range scans    │
│ TRADE-OFF                                              │
│   (+) Sub-second point lookups                         │
│   (-) EXPENSIVE — $$$ ongoing storage cost             │
│   (-) Not for range queries                            │
│                                                         │
│ STAKEHOLDER IMPACT                                     │
│   FinOps review         : 🛑 BLOCK unless justified    │
│   Data Architect       : Only for specific use cases  │
└─────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════
SECTION 4: DECISION TEMPLATE
═══════════════════════════════════════════════════════════

Project: <project_name>
Issue: Slow time-series queries on fact_transactions (6.3M rows)
Investigation: Path B (clustering needed, average_overlaps = 87)
Options considered: 1, 2
Chosen: Option 2 (multi-column: event_date, customer_id)
Justification: Top 10 queries all filter by both columns.
              Date filter alone leaves 200K rows still scanned.
Approved by: Senior Data Engineer, Data Architect, FinOps review
Before metrics:
  - Query time: 8.4s
  - Bytes scanned: 2.1 GB
  - Cost per query: $0.012
After metrics:
  - Query time: 1.2s (86% faster)
  - Bytes scanned: 180 MB (91% reduction)
  - Cost per query: $0.002 (83% savings)
  - Re-clustering one-time cost: $23
  - Break-even: 47 queries (achieved day 3)
ADR link: docs/ADR/007-snowflake-clustering-strategy.md

═══════════════════════════════════════════════════════════
RELATED CHEATSHEETS
═══════════════════════════════════════════════════════════
- snowflake_warehouse_sizing.md
- snowflake_query_profile_reading.md
- snowflake_search_optimization.md
