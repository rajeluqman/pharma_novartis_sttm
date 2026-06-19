#!/usr/bin/env bash
# Project Gamma — Patient Voice / Digital (UCI Drug Review, Drugs.com)
# Kaggle mirror: jessicali9530/kuc-hackathon-winter-2018  (CC BY 4.0)
# Lands raw review CSVs into the immutable Landing Zone.
set -euo pipefail

LAND_DIR="${LAND_DIR:-data/landing/gamma/$(date +%Y-%m-%d)}"
mkdir -p "$LAND_DIR"

# Requires KAGGLE_USERNAME / KAGGLE_KEY (see .env.example)
kaggle datasets download -d jessicali9530/kuc-hackathon-winter-2018 -p "$LAND_DIR" --unzip

echo "[gamma] landed review CSVs -> $LAND_DIR"
ls -1 "$LAND_DIR"
# TODO(build): drugName is free text -> normalized match into conformed dim_drug (ADR-003).
