# PIPELINE_SPEC.md
**Owner**: Senior Data Engineer

---

## Data Flow
```
Source -> Bronze -> Silver -> Gold -> ML/Serving
```

## Bronze Spec

### bronze_ingest_<source>.py
**Input**: <path>
**Output**: bronze.<table>

Transform steps:
1. Read source
2. Add metadata: ingestion_ts, source_file, batch_id
3. Write Delta (append mode)
4. NO cleaning

## Silver Spec

### silver_clean_<table>.py
**Input**: bronze.<table>
**Output**: silver.<table>

Transform steps:
1. DEDUPLICATE on (key cols)
2. TYPE CAST per DATA_DICTIONARY.md
3. NULL HANDLING:
   - Critical cols → quarantine
   - Optional cols → flag
4. VALIDATION (ranges)
5. DERIVED COLUMNS
6. FILTER (production only, etc.)

## Gold Spec

### gold_fact_<name>.py
**Input**: silver.<tables>
**Output**: gold.fact_<name>

Per DATA_MODEL.md logical design.

### gold_dim_<name>.py
SCD Type X implementation.

## Business Rules
| Rule | Formula | Null Handling |
|------|---------|---------------|
| metric_a | col_x / col_y * 100 | NULL if y=0 |

## Error Handling
| Scenario | Action |
|----------|--------|
| NULL critical | Quarantine |
| Out of range | Quarantine + flag |
| Duplicate | Keep latest ingestion_ts |
