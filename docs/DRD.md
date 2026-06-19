# DRD — Data Requirements Document (Kaggle Source)
## <Project Name>

**Owner**: Data Quality Steward + Business Analyst
**Version**: 1.0

---

## 1. Source: Kaggle Dataset

| Field | Value |
|-------|-------|
| Provider | <Kaggle account/org> |
| URL | https://www.kaggle.com/datasets/<slug> |
| License | <CC BY-NC-SA 4.0 / etc> |
| Files | <N CSV tables> |
| Volume | <rows + size> |
| Refresh | Static (one-time download) |
| Auth | Kaggle API key required |
| Download command | `kaggle datasets download -d <slug> -p data/raw --unzip` |

## 2. Schema per File

### File: <filename.csv>
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| col_a | INT | No | <desc> |
| col_b | STRING | Yes | <desc> |

(repeat per file)

## 3. SLA & Retention
- Data freshness SLA: N/A (static)
- Retention: Bronze forever, Silver/Gold project duration

## 4. Known Data Issues
- <Issue 1>
- <Issue 2>

## 5. Business Attribute Mapping (Business Analyst)
| Business Question | Required Columns |
|------------------|------------------|
| Q1 | <columns> |
| Q2 | <columns> |
