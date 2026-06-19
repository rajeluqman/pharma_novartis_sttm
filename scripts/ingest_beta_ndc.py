#!/usr/bin/env python3
"""Project Beta — Product Master / Regulatory (FDA openFDA NDC Directory).

Lands the NDC product directory JSON into the immutable Landing Zone.
Beta is the authoritative product master feeding the conformed dim_drug (ADR-003).

Full bulk snapshot (~136k products) — more product coverage means a higher
real match rate against Gamma's free-text drug names in the crosswalk.
"""
import datetime as dt
import io
import json
import os
import pathlib
import urllib.request
import zipfile

LAND_DIR = pathlib.Path(
    os.environ.get("LAND_DIR", f"data/landing/beta/{dt.date.today():%Y-%m-%d}")
)
BULK_URL = "https://download.open.fda.gov/drug/ndc/drug-ndc-0001-of-0001.json.zip"


def fetch_bulk() -> list[dict]:
    with urllib.request.urlopen(BULK_URL, timeout=180) as r:  # noqa: S310
        zip_bytes = r.read()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        name = zf.namelist()[0]
        with zf.open(name) as f:
            payload = json.load(f)
    return payload.get("results", [])


def main() -> None:
    LAND_DIR.mkdir(parents=True, exist_ok=True)
    out = LAND_DIR / "ndc_directory.json"
    results = fetch_bulk()
    out.write_text(json.dumps(results))
    print(f"[beta] landed {len(results)} NDC products -> {out}")


if __name__ == "__main__":
    main()
