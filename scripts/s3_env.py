"""Shared S3/httpfs env-var contract (ADR-005 migration).

Every script that touches the lake (load_bronze.py, gold publish, GE validation) configures
DuckDB's httpfs extension from the SAME env vars, so swapping MinIO -> real AWS later is a
pure env change, never a code change:

  S3_BUCKET             default novartis-pharma-sttm-lake
  S3_ENDPOINT           MinIO: localhost:9000 ; empty/unset = real AWS (DuckDB default endpoint)
  S3_USE_SSL            true|false (default false — MinIO local is plain HTTP)
  S3_URL_STYLE          path (MinIO requires path-style) | vhost (real AWS default)
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY  (MinIO: fake local creds; real AWS: real creds)
  AWS_REGION / AWS_DEFAULT_REGION  default ap-southeast-1 (ADR-005 Decision 4 region lock)

Real-AWS-later contract: unset S3_ENDPOINT, set real AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY
(or rely on credential_chain — see configure_httpfs(con, use_credential_chain=True)), leave
S3_URL_STYLE unset (defaults to vhost) — same code path, nothing to edit.
"""
import os

S3_BUCKET = os.environ.get("S3_BUCKET", "novartis-pharma-sttm-lake")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "").strip()
S3_USE_SSL = os.environ.get("S3_USE_SSL", "false").lower() == "true"
S3_URL_STYLE = os.environ.get("S3_URL_STYLE", "vhost" if not S3_ENDPOINT else "path")
AWS_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "ap-southeast-1"))
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")


def s3_uri(*parts: str) -> str:
    """Build s3://<bucket>/<parts...> joined with '/'."""
    return f"s3://{S3_BUCKET}/" + "/".join(p.strip("/") for p in parts)


def configure_httpfs(con, use_credential_chain: bool = False) -> None:
    """Install + configure the httpfs extension on a DuckDB connection from env.

    use_credential_chain=True skips explicit key/secret settings and lets DuckDB's
    AWS credential chain (env/instance-profile/SSO) resolve creds — the real-AWS path.
    For MinIO (S3_ENDPOINT set), explicit keys are required (no credential chain there).
    """
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    con.execute(f"SET s3_region='{AWS_REGION}'")
    if S3_ENDPOINT:
        con.execute(f"SET s3_endpoint='{S3_ENDPOINT}'")
    con.execute(f"SET s3_use_ssl={'true' if S3_USE_SSL else 'false'}")
    con.execute(f"SET s3_url_style='{S3_URL_STYLE}'")

    if use_credential_chain and not S3_ENDPOINT:
        # Real AWS, no MinIO endpoint: let DuckDB's credential_chain resolve creds
        # (env vars / instance profile / SSO) instead of hardcoding keys.
        con.execute("CREATE OR REPLACE SECRET s3_secret (TYPE s3, PROVIDER credential_chain)")
        return

    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        con.execute(f"SET s3_access_key_id='{AWS_ACCESS_KEY_ID}'")
        con.execute(f"SET s3_secret_access_key='{AWS_SECRET_ACCESS_KEY}'")
