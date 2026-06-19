#!/usr/bin/env python3
"""Great Expectations suite — Gold layer, complementary to the dbt schema tests.

dbt's generic tests (not_null/unique/relationships/accepted_range/accepted_values, see
dbt/models/**/_*.yml) already cover row-level constraints. This suite covers what those don't:
table-level row counts and FK-resolution-rate *distributions* (the DQD.md coverage KPIs/SLAs),
the kind of check Great Expectations is actually suited for. Added per the Phase 4 retroactive
peer review (DEBATE_LOG_phase_4.md) — Data Quality Steward flagged that `data_quality/
expectations/` was empty despite GE being in ARCHITECTURE.md's locked stack.

Suite + validation result JSON are written to data_quality/expectations/ and
data_quality/validations/ respectively (the paths ARCHITECTURE.md names as owned by Data Quality Steward).

ADR-005 migration: Gold is no longer a relational table in a persistent data/warehouse.duckdb
file — it's parquet on S3 (gold/_current/<model>/, the fixed serving pointer per Decision 1).
This script now opens an ephemeral in-memory DuckDB session (Condition C) with httpfs configured
from the same env-var contract as load_bronze.py/publish_gold.py (scripts/s3_env.py) and reads
gold/_current/ via read_parquet('s3://...') instead of a relational `main_data_mart.*` table.
"""
import json
import pathlib

import duckdb
import great_expectations as gx
from great_expectations import expectations as gxe

import s3_env

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPECTATIONS_DIR = ROOT / "data_quality" / "expectations"
VALIDATIONS_DIR = ROOT / "data_quality" / "validations"


def gold_current(model: str) -> str:
    return s3_env.s3_uri("gold", "_current", model, f"{model}.parquet")


def build_suites():
    return {
        "dim_drug": (
            f"select * from read_parquet('{gold_current('dim_drug')}')",
            [
                # ADR-005: dim_drug carries full SCD2 history (open + closed rows, no is_current
                # filter — see dim_drug.sql). Its row count is monotonically non-decreasing as
                # snap_beta_ndc accumulates change history across runs, so a fixed `==` baseline
                # (133654, true only for a single-run/never-snapshotted-twice state) is wrong by
                # construction once the pipeline runs more than once. Floor + sane ceiling instead.
                gxe.ExpectTableRowCountToBeBetween(min_value=133654, max_value=200000),
                gxe.ExpectColumnValuesToNotBeNull(column="drug_sk"),
                gxe.ExpectColumnValuesToBeUnique(column="drug_sk"),
                gxe.ExpectColumnDistinctValuesToBeInSet(
                    column="drug_member_type", value_set=["ndc_product", "atc_category"]
                ),
            ],
        ),
        "fact_sales": (
            f"select * from read_parquet('{gold_current('fact_sales')}')",
            [
                gxe.ExpectTableRowCountToEqual(value=16848),
                gxe.ExpectColumnProportionOfNonNullValuesToBeBetween(
                    column="drug_sk", min_value=1.0, max_value=1.0
                ),
                gxe.ExpectColumnProportionOfNonNullValuesToBeBetween(
                    column="date_sk", min_value=1.0, max_value=1.0
                ),
                gxe.ExpectColumnValuesToBeBetween(column="units_sold", min_value=0),
            ],
        ),
        "fact_review": (
            f"select * from read_parquet('{gold_current('fact_review')}')",
            [
                gxe.ExpectTableRowCountToEqual(value=215063),
                # DQD.md SLA: fact_review.drug_sk resolution >= 65% (measured 71.9%).
                gxe.ExpectColumnProportionOfNonNullValuesToBeBetween(
                    column="drug_sk", min_value=0.65, max_value=1.0
                ),
                # DQD.md target: condition_sk resolution >= 90% (measured 98.9%).
                gxe.ExpectColumnProportionOfNonNullValuesToBeBetween(
                    column="condition_sk", min_value=0.90, max_value=1.0
                ),
                gxe.ExpectColumnValuesToBeBetween(column="rating", min_value=1, max_value=10),
                gxe.ExpectColumnValuesToNotBeNull(column="dq_flag"),
            ],
        ),
    }


def main() -> None:
    EXPECTATIONS_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATIONS_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(":memory:")  # Condition C: ephemeral catalog, no warehouse.duckdb
    s3_env.configure_httpfs(con)
    context = gx.get_context(mode="ephemeral")
    pandas_ds = context.data_sources.add_pandas("gold_pandas_ds")

    overall_pass = True
    for name, (query, expectations) in build_suites().items():
        df = con.execute(query).df()

        asset = pandas_ds.add_dataframe_asset(name)
        batch_def = asset.add_batch_definition_whole_dataframe(f"{name}_batch")
        batch = batch_def.get_batch(batch_parameters={"dataframe": df})

        suite = context.suites.add(gx.ExpectationSuite(name=f"{name}_suite"))
        for exp in expectations:
            suite.add_expectation(exp)

        result = batch.validate(suite)
        overall_pass = overall_pass and result.success

        (EXPECTATIONS_DIR / f"{name}_suite.json").write_text(
            json.dumps(suite.to_json_dict(), indent=2, default=str)
        )
        (VALIDATIONS_DIR / f"{name}_result.json").write_text(
            json.dumps(result.to_json_dict(), indent=2, default=str)
        )

        status = "PASS" if result.success else "FAIL"
        print(f"[{status}] {name}_suite — {len(expectations)} expectations")
        if not result.success:
            for r in result.results:
                if not r.success:
                    print(f"    FAILED: {r.expectation_config.type} {dict(r.expectation_config.kwargs)}")

    con.close()
    print("OVERALL:", "PASS" if overall_pass else "FAIL")


if __name__ == "__main__":
    main()
