# Layer 01 — Ingestion Optimization
> Scripts: `ingest_alpha_sales.sh`, `ingest_gamma_reviews.sh` (Kaggle CLI),
> `ingest_beta_ndc.py` (openFDA bulk API), `seed_landing_to_s3.py` (relocate to S3).
> Job of this layer: get raw source bytes into the immutable Landing Zone, safely and replayably.
> See [00_INDEX.md](00_INDEX.md) for card format.

---

### ING-01 — `set -euo pipefail` on every shell ingestion script  [✅ DONE]
- **Junior mistake:** Plain `#!/bin/bash` with no strict flags; let commands fail and keep going.
- **Why it bites:** A failed `kaggle download` or an unset variable doesn't stop the script — it "succeeds" with missing/partial files, and the failure only surfaces three layers downstream.
- **Optimized (this repo):** `set -euo pipefail` aborts on any error, unset var, or broken pipe. `scripts/ingest_alpha_sales.sh:4`, `scripts/ingest_gamma_reviews.sh:5`
- **Business one-liner:** "A broken download stops immediately and loudly — we never silently build on half-arrived data."
- **Soundbite:** *"`set -euo pipefail` is the cheapest reliability upgrade a bash script will ever get."*

### ING-02 — Date-partitioned, env-overridable landing path  [✅ DONE]
- **Junior mistake:** Write each run to one fixed file/folder (`data/landing/x.csv`).
- **Why it bites:** Each run overwrites the last — no history, no ability to replay a specific day, and concurrent runs race on the same path.
- **Optimized (this repo):** every ingest writes to `data/landing/<src>/<date>/`, defaulting from the date but overridable via `LAND_DIR`/`LAND_DATE` (the DAG injects `{{ ds }}`). `scripts/ingest_beta_ndc.py:18-19`, `scripts/ingest_alpha_sales.sh:6`, `scripts/ingest_gamma_reviews.sh:7`
- **Business one-liner:** "Every day's raw data is kept separately, so we can re-process any specific date on demand."
- **Soundbite:** *"Partition by date at landing, and replay stops being a recovery project."*

### ING-03 ★ — Hard network timeout on the API fetch  [✅ DONE]
- **Junior mistake:** `urllib.request.urlopen(url)` with no timeout.
- **Why it bites:** A hung openFDA connection blocks the task forever, silently eating the whole SLA window with no error to act on.
- **Optimized (this repo):** `urlopen(BULK_URL, timeout=180)` — a stalled fetch fails fast and becomes a retryable error (pairs with the DAG's `execution_timeout`/`retries`). `scripts/ingest_beta_ndc.py:25`
- **Business one-liner:** "A frozen upstream API fails quickly and retries, instead of quietly burning the morning deadline."
- **Soundbite:** *"Every network call needs a timeout. 'Wait forever' is not an error-handling strategy."*
- **Related:** orchestration T051 (`execution_timeout`), T052–T054 (retries) — fail-fast thread

### ING-04 — Stream the archive in memory, no temp files on disk  [✅ DONE]
- **Junior mistake:** Save the `.zip` to disk, shell out to `unzip`, then read — leaving temp files behind.
- **Why it bites:** Worker disk fills up over time, temp files leak on failure, and the extra I/O is pure overhead.
- **Optimized (this repo):** read the zip bytes into `io.BytesIO`, open with `zipfile`, load the JSON directly — nothing touches disk until the final landed file. `scripts/ingest_beta_ndc.py:24-31`
- **Business one-liner:** "We download and unpack entirely in memory, so workers stay clean and there's nothing to leak on failure."
- **Soundbite:** *"If you don't need it on disk, don't put it on disk."*

### ING-05 — Landing is immutable / write-once; ingest never transforms  [✅ DONE]
- **Junior mistake:** "Clean as you ingest" — cast types, drop columns, dedupe during landing.
- **Why it bites:** You can never replay the true raw source, the audit trail is gone, and a bug in the cleaning logic permanently corrupts the only copy you kept.
- **Optimized (this repo):** ingest writes source bytes unchanged (`out.write_text(json.dumps(results))`); the S3 seed *relocates* bytes without altering them and is idempotent on re-run (cleaning happens later, in staging). `scripts/ingest_beta_ndc.py:34-39`, `scripts/seed_landing_to_s3.py:5-7`
- **Business one-liner:** "We keep the raw source exactly as received, so any past day can be re-processed from ground truth."
- **Soundbite:** *"Land raw, transform later. The raw zone is your only undo button."*
- **Related:** BRZ-02, BRZ-04, BRZ-05 · orchestration T010 (idempotency thread)

### ING-06 — Optimize for downstream match coverage, not just transfer speed  [✅ DONE]
- **Junior mistake:** Paginate a small NDC sample to "keep ingestion light".
- **Why it bites:** Fewer products in the master means a *lower* real match rate against Gamma's free-text drug names downstream — a local "optimization" that degrades the actual product (the crosswalk KPI).
- **Optimized (this repo):** pull the full ~136k-product bulk snapshot precisely because more coverage raises the conformed match rate — the decision is documented. `scripts/ingest_beta_ndc.py:7-8`
- **Business one-liner:** "We pull the complete product directory because broader coverage directly improves how many patient reviews we can link to a real drug."
- **Soundbite:** *"The fastest ingest isn't the best ingest if it starves the layer that creates the value."*
