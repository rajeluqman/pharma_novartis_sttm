#!/usr/bin/env python3
"""ADR-005 Snowflake serving veneer — full automated handshake (no Snowsight needed).

Does the whole STORAGE INTEGRATION dance in one orchestration:
  1. connect (.env creds), USE ROLE ACCOUNTADMIN
  2. CREATE STORAGE INTEGRATION s3_gold_integration (role ARN, gold/* scoped)
  3. DESC INTEGRATION -> read STORAGE_AWS_IAM_USER_ARN + STORAGE_AWS_EXTERNAL_ID
  4. update the snowflake-s3-gold-reader IAM role trust (boto3) to exactly that principal+external-id
  5. CREATE ROLE snowflake_gold_reader + grants (ADR-004 scoped, separate from NOVARTIS_STTM_ROLE)
  6. CREATE STAGE gold_stage -> s3://<bucket>/gold/_current/ ; CREATE EXTERNAL TABLE x2 (infer schema)
  7. SELECT COUNT(*) from each external table -> prove "warehouse over lakehouse"

Real (trivial) spend: small external-table reads on trial credits. Reads creds from .env.
"""
import json
import os
import sys
import time

import boto3
import snowflake.connector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUCKET = "novartis-pharma-sttm-lake"
IAM_ROLE = "snowflake-s3-gold-reader"
REGION = "ap-southeast-1"


def load_env():
    env = {}
    with open(os.path.join(ROOT, ".env")) as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v.strip()
    return env


def main():
    env = load_env()
    sts = boto3.client(
        "sts", region_name=REGION,
        aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
    )
    account = sts.get_caller_identity()["Account"]
    role_arn = f"arn:aws:iam::{account}:role/{IAM_ROLE}"
    print(f">> AWS account {account} | role {role_arn} | bucket {BUCKET}")

    con = snowflake.connector.connect(
        account=env["SNOWFLAKE_ACCOUNT"], user=env["SNOWFLAKE_USER"],
        password=env["SNOWFLAKE_PASSWORD"], warehouse=env["SNOWFLAKE_WAREHOUSE"],
        database=env["SNOWFLAKE_DATABASE"],
    )
    cur = con.cursor()

    def run(sql, label=None):
        print(f">> {label or ' '.join(sql.split())[:80]}")
        cur.execute(sql)
        return cur.fetchall()

    # 1-2. integration (needs ACCOUNTADMIN)
    try:
        run("USE ROLE ACCOUNTADMIN")
    except Exception as e:
        print(f"!! cannot USE ROLE ACCOUNTADMIN ({e}). User {env['SNOWFLAKE_USER']} likely lacks it.")
        sys.exit(2)
    run(f"""CREATE STORAGE INTEGRATION IF NOT EXISTS s3_gold_integration
            TYPE=EXTERNAL_STAGE STORAGE_PROVIDER='S3' ENABLED=TRUE
            STORAGE_AWS_ROLE_ARN='{role_arn}'
            STORAGE_ALLOWED_LOCATIONS=('s3://{BUCKET}/gold/')""",
        "CREATE STORAGE INTEGRATION s3_gold_integration")

    # 3. DESC -> Snowflake's IAM user + external id
    props = {r[0]: r[2] for r in run("DESC INTEGRATION s3_gold_integration")}
    sf_arn = props["STORAGE_AWS_IAM_USER_ARN"]
    sf_ext = props["STORAGE_AWS_EXTERNAL_ID"]
    print(f">> handshake: IAM_USER_ARN={sf_arn}  EXTERNAL_ID={sf_ext}")

    # 4. tighten IAM role trust to exactly that principal + external id
    iam = boto3.client(
        "iam", region_name=REGION,
        aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
    )
    trust = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"AWS": sf_arn},
            "Action": "sts:AssumeRole",
            "Condition": {"StringEquals": {"sts:ExternalId": sf_ext}},
        }],
    }
    iam.update_assume_role_policy(RoleName=IAM_ROLE, PolicyDocument=json.dumps(trust))
    print(">> IAM role trust updated; waiting 15s for propagation ...")
    time.sleep(15)

    # 5. scoped reader role + grants
    run("CREATE ROLE IF NOT EXISTS snowflake_gold_reader")
    for g in [
        "GRANT USAGE ON INTEGRATION s3_gold_integration TO ROLE snowflake_gold_reader",
        "GRANT USAGE ON WAREHOUSE NOVARTIS_STTM_WH TO ROLE snowflake_gold_reader",
        "GRANT USAGE ON DATABASE NOVARTIS_STTM_DB TO ROLE snowflake_gold_reader",
        "GRANT USAGE ON SCHEMA NOVARTIS_STTM_DB.PUBLIC TO ROLE snowflake_gold_reader",
        f"GRANT ROLE snowflake_gold_reader TO USER {env['SNOWFLAKE_USER']}",
    ]:
        run(g)

    # 6. stage + external tables (created as ACCOUNTADMIN in PUBLIC)
    run("USE SCHEMA NOVARTIS_STTM_DB.PUBLIC")
    run("CREATE FILE FORMAT IF NOT EXISTS parquet_fmt TYPE=PARQUET")
    run(f"""CREATE OR REPLACE STAGE gold_stage
            STORAGE_INTEGRATION=s3_gold_integration
            URL='s3://{BUCKET}/gold/_current/' FILE_FORMAT=parquet_fmt""",
        "CREATE STAGE gold_stage -> gold/_current/")

    def create_ext(name):
        sql = f"""CREATE OR REPLACE EXTERNAL TABLE {name}_ext
            USING TEMPLATE (SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*))
              FROM TABLE(INFER_SCHEMA(LOCATION=>'@gold_stage/{name}/', FILE_FORMAT=>'parquet_fmt')))
            LOCATION=@gold_stage/{name}/ FILE_FORMAT=parquet_fmt AUTO_REFRESH=FALSE"""
        last = None
        for attempt in range(4):  # retry for IAM trust propagation
            try:
                run(sql, f"CREATE EXTERNAL TABLE {name}_ext")
                return
            except Exception as e:
                last = e
                print(f"   .. attempt {attempt+1} failed ({str(e)[:90]}); waiting 15s")
                time.sleep(15)
        raise last

    for t in ("obt_sales_wide", "obt_review_wide"):
        create_ext(t)
        run(f"GRANT SELECT ON {t}_ext TO ROLE snowflake_gold_reader")

    # 7. verify
    sales = run("SELECT COUNT(*) FROM obt_sales_wide_ext")[0][0]
    review = run("SELECT COUNT(*) FROM obt_review_wide_ext")[0][0]
    print("\n============================================================")
    print(f">> VENEER LIVE — obt_sales_wide_ext={sales} rows, obt_review_wide_ext={review} rows")
    print(f">> (expect sales=16848, review=215063 — same S3 gold the DuckDB pipeline wrote)")
    print("============================================================")
    cur.close(); con.close()


if __name__ == "__main__":
    main()
