# Phase 03 — Ingestion (S3 Landing) — Incident Cards  [PILOT]

> Checklist step 3 of 8 (NOT "layer 3" — see `00_INDEX.md` numbering note).
> Scope: `scripts/seed_landing_to_s3.py`, `scripts/ingest_beta_ndc.py`, `scripts/s3_env.py`.
> Diagnostic backbone for this phase: **landing→bronze row-count reconciliation**
> (`scripts/load_bronze.py:80-83` already prints per-table bronze counts — that print IS
> the reconciliation hook).
> Owned by @incident-responder · Governed by ADR-006 · Bucket legend in `00_INDEX.md`.

---

### I-ING-01 — 0-byte / truncated landing file  ★  [🟡 APPLICABLE]
- Symptom         : task fails on read, or bronze row count = 0 for one source while others are fine.
- Diagnosis       : list the landing prefix and check sizes; the seed script even prints byte size
  per upload — `scripts/seed_landing_to_s3.py:67-68` (`size = f.stat().st_size` → printed). A `(0 bytes)` line is your smoking gun.
- Root cause      : 1) partial/hung upstream upload; 2) source produced an empty file; 3) wrong/empty partition dir.
- Fix / Recovery  : re-land the file from source, re-seed (idempotent — see I-ING-06), rerun bronze for that `<date>`.
- Evidence        : upload loop `scripts/seed_landing_to_s3.py:62-69` accepts ANY file — it prints the size but never asserts `> 0`. Guard goes at `:64` (`if f.stat().st_size == 0: raise/skip`). Tradeoff: a legitimately empty daily file (rare here) would need a whitelist.
- ⚠️ Junior mistake : "the upload command exited 0, so the file is there" — exit code says *transferred*, not *non-empty*.
- 🎤 Soundbite      : "First thing I check on an ingestion failure is file size at the landing prefix — a 0-byte object passes the upload but fails every reader downstream."

---

### I-ING-02 — Truncated / partial source download (Beta NDC bulk)  [🟡 APPLICABLE]
- Symptom         : `read_json_auto` parse error in bronze, or NDC product count far below the expected ~136k.
- Diagnosis       : compare landed count to the known baseline — `scripts/ingest_beta_ndc.py:39` prints `landed N NDC products`; a short N means a truncated fetch, not a schema problem.
- Root cause      : single-shot HTTP fetch with no integrity check — a dropped connection lands a partial zip/JSON silently.
- Fix / Recovery  : re-fetch; on repeat, verify HTTP status + `Content-Length` vs bytes read before writing.
- Evidence        : `scripts/ingest_beta_ndc.py:24-31` — `urllib.request.urlopen(BULK_URL, timeout=180)` then `r.read()` with no status check, no length/checksum verify, no retry. Guard: assert `r.status == 200` and `len(zip_bytes) == Content-Length` before `zipfile` parse; add a bounded retry. Tradeoff: openFDA has no published checksum, so length-check is the strongest cheap signal.
- ⚠️ Junior mistake : trusting `urlopen` because it didn't raise — a truncated body reads back fine and only explodes 2 layers downstream.
- 🎤 Soundbite      : "For a 136k-record bulk pull I anchor on expected volume — if the landed count drops, I suspect a truncated download before I ever blame the parser."

---

### I-ING-03 — Schema drift invisible at landing  ★  [🟡 APPLICABLE]
- Symptom         : downstream type error in bronze, OR a column silently disappears with no error at all.
- Diagnosis       : landing→bronze reconciliation — `scripts/load_bronze.py:80-83` prints each bronze table's row count; a count that dropped (or a `read_json_auto`/`read_csv_auto` type error at `load_bronze.py:55-59` / `:65-72`) localizes the drift to a source.
- Root cause      : raw files are landed byte-for-byte with **no schema/contract assertion**, so an added/renamed/dropped column only surfaces when DuckDB infers types downstream.
- Fix / Recovery  : pin expected columns at the bronze read; on drift, quarantine the file and alert. Recovery = re-land corrected source + rerun bronze for `<date>`.
- Evidence        : `scripts/ingest_beta_ndc.py:38` writes the JSON with zero schema check; drift first bites at `scripts/load_bronze.py:55-59` (`read_json_auto`). Partial guard already exists — the round-trip count print at `load_bronze.py:80-83` is the reconciliation hook; promote it to an assert vs an expected-count baseline.
- ⚠️ Junior mistake : "no error, so the load is fine" — schema drift is the failure that ships *quietly*; absence of an exception is not absence of data loss.
- 🎤 Soundbite      : "Schema drift rarely throws — it drops rows. That's why I reconcile counts landing→bronze rather than trusting that the job didn't error."

---

### I-ING-04 — Wrong / stale partition seeded  [🟡 APPLICABLE]
- Symptom         : pipeline succeeds but yesterday's (or an old) dataset lands in today's `<date>` partition; metrics look "stale but valid".
- Diagnosis       : check which dir `latest_dir()` resolved — print/log the chosen `src_dir.name` (`scripts/seed_landing_to_s3.py:61` `date_part = src_dir.name`) and compare to the intended `LAND_DATE`.
- Root cause      : `LAND_DATE` unset → silent fallback to the newest existing dir.
- Fix / Recovery  : require `LAND_DATE` explicitly (or fail loudly if unset in prod); re-seed the correct partition; rerun bronze.
- Evidence        : `scripts/seed_landing_to_s3.py:44-53` — `latest_dir()` returns `candidates[-1]` when `LAND_DATE` is unset/missing. Guard: in a scheduled context, treat unset `LAND_DATE` as an error, not a convenience. Tradeoff: keeps the ergonomic local default for ad-hoc runs — gate by environment.
- ⚠️ Junior mistake : leaning on "it grabs the latest" — convenient locally, a silent wrong-partition incident in production.
- 🎤 Soundbite      : "A pipeline that 'succeeds' on the wrong date is worse than one that fails — I make the partition explicit so stale data can't masquerade as fresh."

---

### I-ING-05 — Region / endpoint / URL-style mismatch (cloud-only)  [🟡 APPLICABLE]
- Symptom         : opaque connection/auth error that only appears on real AWS (or only on MinIO) — "works on my machine".
- Diagnosis       : echo the resolved S3 env trio (`S3_ENDPOINT`, `S3_URL_STYLE`, `AWS_REGION`) before the client builds; a half-set env (endpoint set, url-style not) is the tell.
- Root cause      : path-style (MinIO) vs vhost-style (AWS) addressing mismatch, or region not matching the bucket.
- Fix / Recovery  : set the full env contract consistently; let the endpoint drive the url-style default.
- Evidence        : **two files disagree** — `scripts/s3_env.py:23` defaults `S3_URL_STYLE` by endpoint (`"vhost" if not S3_ENDPOINT else "path"`), but `scripts/seed_landing_to_s3.py:28` hardcodes `"path"` regardless. On real AWS the seed script can pick path-style while the rest of the pipeline picks vhost. Guard: make the seed script import the same default logic from `s3_env.py:23`. Tradeoff: tiny refactor, removes a class of cloud-only "works local" incidents.
- ⚠️ Junior mistake : debugging the bucket/IAM for an hour when the real fault is path-vs-vhost addressing from a half-set env.
- 🎤 Soundbite      : "Most 'works locally, fails in cloud' S3 bugs are addressing-style or region mismatches — I print the resolved endpoint/url-style/region first so I'm debugging config, not guessing at IAM."

---

### I-ING-06 — Idempotent re-seed (this is the GUARD, not the bug)  [✅ HARDENED]
- Symptom         : (none if respected) — re-running the seed must not duplicate or corrupt landing.
- Diagnosis       : confirm replays write the SAME key with the SAME bytes — safe to rerun after any incident above.
- Root cause      : N/A — documents the existing guarantee that makes recovery from I-ING-01..05 safe.
- Fix / Recovery  : just rerun the seed; immutability (ADR-005 Decision 4) means byte-for-byte re-upload to the idempotent date-partitioned key.
- Evidence        : `scripts/seed_landing_to_s3.py:65-66` builds a deterministic key `landing/{source}/{date_part}/{name}` and `upload_file`s the same bytes; docstring `:5-7` states landing is immutable/write-once. ✅ HARDENED.
- ⚠️ Junior mistake : "to be safe, I'll timestamp the filename on re-run" — that breaks idempotency and spawns duplicate landing objects the bronze glob then double-counts.
- 🎤 Soundbite      : "Recovery is cheap here because the seed is idempotent — same key, same bytes — so after any landing incident I just re-land and rerun, no dedupe gymnastics."

---

## Phase tally
✅ HARDENED: 1 · 🟡 APPLICABLE: 5 · ⚪ N/A: 0 — **6 cards** (pilot).
Reconciliation anchor for all of phase 03: `scripts/load_bronze.py:80-83`.
