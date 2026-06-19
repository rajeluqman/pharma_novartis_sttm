# PERFORMANCE_LOG.md
**Owner**: Senior Data Engineer (auto-extract)

Categories tracked:
- QUERY_PERFORMANCE | SPARK_EXECUTION | STORAGE_LAYOUT
- PIPELINE_THROUGHPUT | DBT_PERFORMANCE | RESOURCE_UTILIZATION

Senior-level target: minimum 5 of 6 categories per project.

---

## [2026-04-30 14:30] [silver_clean_transactions]

**Category**: QUERY_PERFORMANCE
**Tags**: #snowflake #clustering #window-function
**Issue ID**: PERF-001

### Symptom
Query taking 8.4s on 6.3M-row transactions table during Silver dedup pass.

### Investigation
1. Snowflake UI → Query Profile → TableScan node showed 100% partitions scanned
2. SYSTEM$CLUSTERING_INFORMATION → average_overlaps = 87 (poor clustering)
3. Last 100 queries → 89% filter by (event_date, customer_id)
4. Hypothesis: missing clustering key on time-series column

### Solution
Added compound clustering key: `(event_date, customer_id)`
```sql
ALTER TABLE silver.transactions CLUSTER BY (event_date, customer_id);
```

### Before/After
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Query time | 8.4s | 1.2s | 86% faster |
| Bytes scanned | 2.1 GB | 180 MB | 91% reduction |
| Cost per query | $0.012 | $0.002 | 83% savings |
| Re-clustering cost (one-time) | — | $23 | Break-even at 47 queries |

### Stakeholder Sign-off
- Senior Data Engineer: APPROVED
- Data Architect: APPROVED (ADR-007 created)
- FinOps review: APPROVED — net $30/month savings projected

### Code
See: `silver/notebooks/cluster_transactions.sql`

### Lesson
Snowflake clustering essential for time-series queries.
Always cluster compound key (date + entity) when both are filtered.

### Related Cheatsheets
- cheatsheets/performance/snowflake_clustering.md
- cheatsheets/performance/snowflake_query_profile.md

---

## [2026-04-30 16:15] [silver_clean_orders]

**Category**: SPARK_EXECUTION
**Tags**: #pyspark #shuffle #skew #broadcast-join
**Issue ID**: PERF-002

### Symptom
Silver clean job hanging — Stage 3 running 12 minutes vs Stage 1 (45 seconds).

### Investigation
1. Spark UI → Stages tab → Stage 3 took 12m, 200 tasks
2. Sort tasks by duration → top task = 11m, median = 30s (skew 22x)
3. df.groupBy("seller_id").count() → seller_id "XYZ001" had 4.2M rows (35% of data)
4. Lookup table `sellers_dim` was only 8 MB
5. Hypothesis: skew on seller_id + missing broadcast hint

### Solution
Force broadcast join on small dim:
```python
from pyspark.sql.functions import broadcast
silver = orders.join(broadcast(sellers_dim), "seller_id", "left")
```

Also enabled AQE:
```python
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
```

### Before/After
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Stage 3 duration | 12 min | 1.5 min | 87% faster |
| Total job duration | 18 min | 4 min | 78% faster |
| Shuffle write | 4.2 GB | 0 GB | Eliminated |
| Skewed task variance | 22x | 1.4x | Fixed |

### Stakeholder Sign-off
- Senior Data Engineer: APPROVED
- Data Architect: APPROVED (8 MB < 10 MB broadcast threshold safe)
- QA Engineer: Added size guard test (broadcast fails if > 10 MB)

### Code
See: `silver/notebooks/clean_orders.py:42-58`

### Lesson
Always check Spark UI Stages tab first. Skew >5x = investigate.
Broadcast small dims (<10 MB) by default — explicit hint beats config.

### Related Cheatsheets
- cheatsheets/performance/spark_broadcast_join.md
- cheatsheets/performance/spark_skew_handling.md
- cheatsheets/performance/spark_aqe.md

---

## [2026-04-30 18:42] [dbt_build_gold]

**Category**: DBT_PERFORMANCE
**Tags**: #dbt #incremental #materialization
**Issue ID**: PERF-003

### Symptom
`dbt build` taking 25 minutes nightly — all 47 models running as `table`.

### Investigation
1. dbt --debug output → 12 models recompute full dataset every run
2. Reviewed model `fct_daily_orders.sql` — appends daily data, full refresh wasteful
3. Hypothesis: should be incremental, not table

### Solution
Convert 12 high-volume models to incremental:
```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    on_schema_change='append_new_columns'
) }}

SELECT * FROM staging.orders
{% if is_incremental() %}
WHERE created_at > (SELECT MAX(created_at) FROM {{ this }})
{% endif %}
```

### Before/After
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| dbt build duration | 25 min | 6 min | 76% faster |
| Snowflake credits/run | 4.2 | 0.9 | 79% reduction |
| Rows processed | 100M (full) | 1.2M (delta) | 99% reduction |

### Stakeholder Sign-off
- Senior Data Engineer: APPROVED
- Analytics Engineer: Updated 12 models in PR #14
- Data Architect: APPROVED (incremental strategy doc'd in ADR-012)
- FinOps review: APPROVED — projected $180/month savings

### Code
See: `dbt/models/marts/fct_daily_orders.sql`

### Lesson
Default materialization should be `view`. Use `table` for slow source.
Use `incremental` for append-only fact tables > 100K rows.
Always set `unique_key` for incremental — required for upsert.

### Related Cheatsheets
- cheatsheets/performance/dbt_incremental_strategies.md
- cheatsheets/functions/dbt_macros.md

---

## Senior-Level Coverage Check

Aim for minimum 5 of 6 categories per project:
- [x] QUERY_PERFORMANCE (PERF-001)
- [x] SPARK_EXECUTION (PERF-002)
- [ ] STORAGE_LAYOUT
- [ ] PIPELINE_THROUGHPUT
- [x] DBT_PERFORMANCE (PERF-003)
- [ ] RESOURCE_UTILIZATION

**Current: 3/6** — need 2 more before Phase 5 sign-off.
