#!/usr/bin/env python3
"""One-off utility: upload existing local data/landing/{alpha,beta,gamma}/<date>/ files into
S3 (or MinIO) at s3://<bucket>/landing/{alpha,beta,gamma}/<date>/<file>, unchanged.

ADR-005 Decision 4/6: landing/ is immutable, write-once raw — this script just relocates the
already-landed files; it does not touch or alter their bytes. Re-running it just re-uploads the
same bytes to the same idempotent date-partitioned key.

Configurable by env so this is the same script for MinIO now and real S3 later:
  S3_BUCKET        default novartis-pharma-sttm-lake
  S3_ENDPOINT      MinIO: localhost:9000 ; empty/unset = real AWS
  S3_USE_SSL       default false (MinIO local); true for real AWS
  S3_URL_STYLE     path (MinIO) | virtual (real AWS, ignored by boto3 path param here)
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION
"""
import os
import pathlib

import boto3
from botocore.client import Config

ROOT = pathlib.Path(__file__).resolve().parent.parent
LAND_DATE = os.environ.get("LAND_DATE")

S3_BUCKET = os.environ.get("S3_BUCKET", "novartis-pharma-sttm-lake")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "").strip()
S3_USE_SSL = os.environ.get("S3_USE_SSL", "false").lower() == "true"
S3_URL_STYLE = os.environ.get("S3_URL_STYLE", "path")
AWS_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "ap-southeast-1"))


def make_client():
    kwargs = {"region_name": AWS_REGION}
    if S3_ENDPOINT:
        scheme = "https" if S3_USE_SSL else "http"
        kwargs["endpoint_url"] = f"{scheme}://{S3_ENDPOINT}"
        kwargs["aws_access_key_id"] = os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")
        kwargs["aws_secret_access_key"] = os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin123")
        addressing = "path" if S3_URL_STYLE == "path" else "virtual"
        kwargs["config"] = Config(s3={"addressing_style": addressing})
    return boto3.client("s3", **kwargs)


def latest_dir(source: str) -> pathlib.Path:
    base = ROOT / "data" / "landing" / source
    if LAND_DATE:
        d = base / LAND_DATE
        if d.exists():
            return d
    candidates = sorted(p for p in base.glob("*") if p.is_dir())
    if not candidates:
        raise FileNotFoundError(f"No landing dir for {source}")
    return candidates[-1]


def main() -> None:
    s3 = make_client()
    total = 0
    for source in ("alpha", "beta", "gamma"):
        src_dir = latest_dir(source)
        date_part = src_dir.name
        for f in sorted(src_dir.glob("*")):
            if not f.is_file():
                continue
            key = f"landing/{source}/{date_part}/{f.name}"
            s3.upload_file(str(f), S3_BUCKET, key)
            size = f.stat().st_size
            print(f"[seed] s3://{S3_BUCKET}/{key} ({size} bytes)")
            total += 1
    print(f"[seed] uploaded {total} files to s3://{S3_BUCKET}/landing/")


if __name__ == "__main__":
    main()
