# Snowflake SQL Cheatsheet

## Window Functions

| FUNCTION | DESCRIPTION | EXAMPLE |
|----------|-------------|---------|
| `ROW_NUMBER()` | Sequential row number | `ROW_NUMBER() OVER (PARTITION BY col ORDER BY ts)` |
| `RANK()` | Rank with gaps | `RANK() OVER (ORDER BY value DESC)` |
| `DENSE_RANK()` | Rank without gaps | `DENSE_RANK() OVER (ORDER BY value DESC)` |
| `LAG() / LEAD()` | Previous/next row value | `LAG(col, 1) OVER (PARTITION BY id ORDER BY ts)` |
| `FIRST_VALUE() / LAST_VALUE()` | First/last in window | `FIRST_VALUE(col) OVER (PARTITION BY id ORDER BY ts)` |

## Date Functions

| FUNCTION | DESCRIPTION | EXAMPLE |
|----------|-------------|---------|
| `DATEADD()` | Add interval | `DATEADD(day, -30, current_date())` |
| `DATEDIFF()` | Difference | `DATEDIFF(day, start_dt, end_dt)` |
| `DATE_TRUNC()` | Truncate to unit | `DATE_TRUNC('month', col)` |
| `EXTRACT()` | Extract part | `EXTRACT(year FROM col)` |
| `CURRENT_DATE()` | Today | `CURRENT_DATE()` |

## Aggregations

| FUNCTION | DESCRIPTION | EXAMPLE |
|----------|-------------|---------|
| `LISTAGG()` | Concatenate values | `LISTAGG(name, ', ') WITHIN GROUP (ORDER BY name)` |
| `PERCENTILE_CONT()` | Continuous percentile | `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY val)` |
| `APPROX_COUNT_DISTINCT()` | Fast approx distinct | `APPROX_COUNT_DISTINCT(col)` |
| `ARRAY_AGG()` | Aggregate to array | `ARRAY_AGG(col)` |

## CTE & Recursion

```sql
WITH RECURSIVE cte AS (
  SELECT id, parent_id, 1 AS level FROM tbl WHERE parent_id IS NULL
  UNION ALL
  SELECT t.id, t.parent_id, c.level + 1
  FROM tbl t JOIN cte c ON t.parent_id = c.id
)
SELECT * FROM cte;
```

## Snowflake-Specific

| FUNCTION | DESCRIPTION | EXAMPLE |
|----------|-------------|---------|
| `QUALIFY` | Filter by window result | `QUALIFY ROW_NUMBER() OVER (...) = 1` |
| `FLATTEN()` | Expand semi-structured | `FROM tbl, LATERAL FLATTEN(input => json_col)` |
| `PARSE_JSON()` | Parse JSON string | `PARSE_JSON('{"a":1}')` |
| `TRY_CAST()` | Cast with NULL on fail | `TRY_CAST(col AS INT)` |
| `IFF()` | Ternary if-else | `IFF(x > 0, 'pos', 'neg')` |

## Performance Functions

| FUNCTION | DESCRIPTION | EXAMPLE |
|----------|-------------|---------|
| `SYSTEM$CLUSTERING_INFORMATION()` | Check clustering quality | `SELECT SYSTEM$CLUSTERING_INFORMATION('tbl', '(col)')` |
| `SYSTEM$ESTIMATE_SEARCH_OPTIMIZATION_COSTS()` | Estimate SO cost | `SELECT SYSTEM$ESTIMATE_SEARCH_OPTIMIZATION_COSTS('tbl')` |
| `SAMPLE` | Statistical sample | `SELECT * FROM tbl SAMPLE (10)` |

## Gotchas

- `QUALIFY` is Snowflake-specific (not standard SQL)
- `FLATTEN` requires `LATERAL` keyword
- `PARSE_JSON` returns VARIANT type (different from VARCHAR)
- `TRY_CAST` returns NULL on failure — use for resilient pipelines
- Warehouse auto-suspend default 600s — change for short queries

## When to Use Each

- Use `QUALIFY` instead of subquery for window function filter
- Use `APPROX_COUNT_DISTINCT` for big tables (10x faster, <2% error)
- Use `SAMPLE` for development/testing on big tables
- Use `TRY_CAST` in Silver layer for type safety
