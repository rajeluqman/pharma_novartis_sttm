#!/usr/bin/env bash
# Project Alpha — Commercial Sales (Kaggle: milanzdravkovic/pharma-sales-data)
# Lands raw CSVs into the immutable Landing Zone (local folder / S3 in cloud).
set -euo pipefail

LAND_DIR="${LAND_DIR:-data/landing/alpha/$(date +%Y-%m-%d)}"
mkdir -p "$LAND_DIR"

# Requires KAGGLE_USERNAME / KAGGLE_KEY (see .env.example)
kaggle datasets download -d milanzdravkovic/pharma-sales-data -p "$LAND_DIR" --unzip

echo "[alpha] landed sales CSVs -> $LAND_DIR"
ls -1 "$LAND_DIR"
# TODO(build): on cloud, sync to s3://$MWAA_DAGS_S3_BUCKET/../landing/alpha/
