"""Integration tests: row-count reconciliation across the local DuckDB pipeline.

Read-only against the already-built `data/warehouse.duckdb` (dev/DuckDB target).
Does NOT touch Snowflake/prod and does NOT rebuild the warehouse — it asserts on
whatever is currently materialized, same posture as the dbt tests these complement.

Run: python3 tests/integration/test_pipeline_reconciliation.py
(or: pytest tests/integration/test_pipeline_reconciliation.py -v, if pytest is installed)

Checklist coverage (qa-engineer execution checklist, PROJECT_STATUS.md Phase 4->5 blocker):
  - source row count -> Bronze count (exact match)
  - Bronze -> Silver (within <5% drop tolerance)
  - Silver -> Gold (aggregation match)
"""
import json
import pathlib

import duckdb
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT / "data" / "warehouse.duckdb"
LANDING = ROOT / "data" / "landing"
DROP_TOLERANCE = 0.05  # 5%, per qa-engineer checklist

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        FAILURES.append(label)


def latest_partition(source: str) -> pathlib.Path:
    parts = sorted((LANDING / source).iterdir())
    assert parts, f"no landing partitions found for {source}"
    return parts[-1]


def main() -> int:
    con = duckdb.connect(str(DB_PATH), read_only=True)

    # ---- Source -> Bronze: exact match (no cleaning at this hop, per ARCHITECTURE.md) ----
    alpha_dir = latest_partition("alpha")
    sd_landing = len(pd.read_csv(alpha_dir / "salesdaily.csv"))
    sh_landing = len(pd.read_csv(alpha_dir / "saleshourly.csv"))

    beta_dir = latest_partition("beta")
    with open(beta_dir / "ndc_directory.json") as f:
        ndc_json = json.load(f)
    ndc_landing = len(ndc_json["results"]) if isinstance(ndc_json, dict) else len(ndc_json)

    gamma_dir = latest_partition("gamma")
    gamma_landing = len(pd.read_csv(gamma_dir / "drugsComTrain_raw.csv")) + len(
        pd.read_csv(gamma_dir / "drugsComTest_raw.csv")
    )

    sd_bronze = con.execute("select count(*) from bronze.sales_daily").fetchone()[0]
    sh_bronze = con.execute("select count(*) from bronze.sales_hourly").fetchone()[0]
    ndc_bronze = con.execute("select count(*) from bronze.ndc_directory").fetchone()[0]
    gamma_bronze = con.execute("select count(*) from bronze.drug_reviews").fetchone()[0]

    check("source->bronze: sales_daily exact match", sd_landing == sd_bronze, f"{sd_landing} == {sd_bronze}")
    check("source->bronze: sales_hourly exact match", sh_landing == sh_bronze, f"{sh_landing} == {sh_bronze}")
    check("source->bronze: ndc_directory exact match", ndc_landing == ndc_bronze, f"{ndc_landing} == {ndc_bronze}")
    check("source->bronze: drug_reviews exact match", gamma_landing == gamma_bronze, f"{gamma_landing} == {gamma_bronze}")

    # ---- Bronze -> Silver (enrich): within 5% drop tolerance ----
    # stg_alpha__sales unpivots 8 ATC cols -> long format, so expected silver rows = bronze * 8, not a drop.
    stg_alpha = con.execute("select count(*) from main_enrich.stg_alpha__sales").fetchone()[0]
    check(
        "bronze->silver: stg_alpha__sales unpivot (8x sales_daily, no row loss)",
        stg_alpha == sd_bronze * 8,
        f"{stg_alpha} == {sd_bronze} * 8",
    )

    stg_beta = con.execute("select count(*) from main_enrich.stg_beta__ndc").fetchone()[0]
    beta_drop_pct = 1 - (stg_beta / ndc_bronze)
    check(
        "bronze->silver: stg_beta__ndc dedup within 5% drop tolerance",
        beta_drop_pct <= DROP_TOLERANCE,
        f"dropped {beta_drop_pct:.2%} ({ndc_bronze} -> {stg_beta})",
    )

    stg_gamma = con.execute("select count(*) from main_enrich.stg_gamma__reviews").fetchone()[0]
    gamma_drop_pct = 1 - (stg_gamma / gamma_bronze)
    check(
        "bronze->silver: stg_gamma__reviews within 5% drop tolerance",
        gamma_drop_pct <= DROP_TOLERANCE,
        f"dropped {gamma_drop_pct:.2%} ({gamma_bronze} -> {stg_gamma})",
    )

    # ---- Silver -> Gold: aggregation / grain match ----
    fact_sales = con.execute("select count(*) from main_data_mart.fact_sales").fetchone()[0]
    check(
        "silver->gold: fact_sales preserves stg_alpha__sales grain (1:1, no fan-out)",
        fact_sales == stg_alpha,
        f"{fact_sales} == {stg_alpha}",
    )

    fact_review = con.execute("select count(*) from main_data_mart.fact_review").fetchone()[0]
    check(
        "silver->gold: fact_review preserves stg_gamma__reviews grain (1:1, no fan-out)",
        fact_review == stg_gamma,
        f"{fact_review} == {stg_gamma}",
    )

    # dim_drug = deduped NDC silver rows + 8 synthetic atc_category rows (ARCHITECTURE.md data model)
    dim_drug = con.execute("select count(*) from main_data_mart.dim_drug").fetchone()[0]
    check(
        "silver->gold: dim_drug = stg_beta__ndc + 8 synthetic atc_category rows",
        dim_drug == stg_beta + 8,
        f"{dim_drug} == {stg_beta} + 8",
    )

    con.close()

    print()
    total = 9
    passed = total - len(FAILURES)
    print(f"Integration reconciliation: {passed}/{total} pass")
    if FAILURES:
        print("FAILED:", ", ".join(FAILURES))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
