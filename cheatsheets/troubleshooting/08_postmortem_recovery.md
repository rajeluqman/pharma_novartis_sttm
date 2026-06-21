# Phase 08 — Post-Mortem & Recovery (Backfill / Catchup) — Incident Cards  [DRILL-READY]

> Checklist step 8 of 8 (see `00_INDEX.md`), last step before closing an incident. Scope:
> `docs/OPS_RUNBOOK.md` Backfill Procedure + Session End Checklist, `scripts/load_bronze.py`,
> `scripts/seed_landing_to_s3.py`, `scripts/publish_gold.py`, ADR-006-A1 §4 (rubric).
> **DRILL-READY (C3, ADR-006-A1) — cleared 2026-06-20.** Exercised against a real `gym-lake`
> MinIO loop: published two real Gold runs and rolled back live (P-PMR-03/04's documented
> mechanism, confirmed working). The rep also surfaced a genuinely new finding — the rollback
> was only needed because re-running the SAME day twice was found to NOT be idempotent — see
> ★ P-PMR-07.
> Owned by @incident-responder · Governed by ADR-006 / ADR-006-A1.

---

### P-PMR-01 — Backfill here is "rerun for a date," never "delete-then-reload a partition"  ★  [✅ HARDENED]
- Symptom         : the instinct from a partition-table mental model is to delete a bad date's rows then reload.
- Diagnosis       : check how bronze is actually written — every load writes to a fixed, deterministic S3 key per `(source, date, table)`, not an appendable/relational table.
- Root cause      : N/A — documents the idempotent-overwrite recovery model.
- Fix / Recovery  : just re-trigger the task group / rerun the script for the affected `ds` — `load_bronze.py`'s `COPY (...) TO '<bronze_uri>' (FORMAT PARQUET)` writes to the exact same S3 key every time, so a rerun deterministically overwrites, with no delete step and no risk of duplicate partitions.
- Evidence        : `docs/OPS_RUNBOOK.md:69` (Backfill Procedure header: "no quarantine table or partition-delete pattern... backfill here means rerun for a given logical date, not delete-then-reload a partition") + `scripts/load_bronze.py:32-33,41-73` (`bronze_uri()` is deterministic per source/date/table; every `COPY` targets that exact fixed key). Note: the runbook line additionally describes this as `CREATE OR REPLACE TABLE` — that SQL pattern does NOT appear in the current `load_bronze.py` (post-ADR-005 migration writes parquet directly via `COPY...TO`, not a relational table); the runbook is stale on the mechanism but correct on the *consequence* (idempotent overwrite). ✅ HARDENED on the actual current code path.
- ⚠️ Junior mistake : writing a one-off script to delete a date's S3 objects "to be safe" before rerunning — unnecessary and risks a brief window where bronze for that date doesn't exist if anything reads it mid-recovery; the rerun's overwrite already does this safely and atomically per object.
- 🎤 Soundbite      : "There's no quarantine table and no delete-then-reload pattern here — recovery is just rerunning the load for that date, because every bronze write targets a fixed, deterministic key that a rerun safely overwrites."

---

### P-PMR-02 — Backfill must replay the DAG's actual dependency order, with one accepted snapshot caveat  [✅ HARDENED]
- Symptom         : a backfill "looks done" (bronze reloaded) but downstream marts are still wrong or stale.
- Diagnosis       : confirm every downstream step actually reran in order — bronze → `dbt run -s staging` → `dbt snapshot` → `dbt run -s marts.core` → `dbt run -s marts.serving` → `dbt test` + GE.
- Root cause      : a partial backfill that stops at bronze (or skips the snapshot step) leaves `dim_drug`/the OBT built from stale intermediate state.
- Fix / Recovery  : rerun the full chain in the documented order; if a product was delisted from the Beta NDC feed since the last snapshot, accept that the SCD2 `check` strategy will NOT retroactively close its `dbt_valid_to` during a backfill — this is a documented, accepted limitation, not something to chase mid-recovery.
- Evidence        : `docs/OPS_RUNBOOK.md:73` (full ordered rerun chain + the explicit snapshot caveat) — cross-reference `02_orchestration_airflow.md` → `O-AIR-03` for the same dependency at the code level (`airflow/dags/pharma_sttm_pipeline.py:92-95,107`). ✅ HARDENED.
- ⚠️ Junior mistake : reloading bronze, declaring the incident resolved, and closing the ticket without verifying `dbt_marts`/`dbt_serving` actually reran against the corrected bronze data.
- 🎤 Soundbite      : "Backfill isn't done at bronze — I verify the full chain reran in order, snapshot included, and I don't chase the one documented SCD2 limitation around delisted products during recovery; that's an accepted gap, not this incident."

---

### P-PMR-03 — Today, recovering a stale-Gold incident is a fully manual step — nothing in the DAG does it for you  ★  [✅ HARDENED — rollback reproduced live 2026-06-20]
- Symptom         : Gold/serving is confirmed stale or wrong; the recovery action itself is not automatic anywhere in the orchestrated pipeline.
- Diagnosis       : identify the last-good `run_id` from retained `gold/<run_id>/` lineage, then run the publish script directly.
- Root cause      : the recovery mechanism (`scripts/publish_gold.py --run-id <id>`, a pure S3 copy with no DDL) exists and works, but — per `02_orchestration_airflow.md` `O-AIR-01` — the DAG never calls it, so EVERY recovery from a stale-Gold incident today requires a human to remember to run it by hand; there is no automated re-enable step to verify-before-trusting.
- Fix / Recovery  : `python scripts/publish_gold.py --run-id <last-good-or-newly-fixed-run>` — re-copies that run into `gold/_current/`; this is the same command whether "recovery" means rollback to an older run or forward-publish a freshly fixed one. Closing `O-AIR-01` (wiring this into the DAG, gated after `dq_checks()`) would remove the "human must remember" step entirely.
- Evidence        : `scripts/publish_gold.py:75,88` (`--run-id` selects the run; lineage retained, never deleted, so a rollback target always exists) — full detail and the rollback-specific framing already in `05_load_snowflake.md` → `L-SNO-04`; this card is the post-mortem-specific angle: today's recovery path runs ONLY because someone remembers to type the command, not because the system enforces it. **Live rep (2026-06-20, `gym-lake`):** published `run-...-gymrep` (good) to `_current`, then published a second real run `run-...-incident` over it (simulating a bad daily refresh going live), then recovered by re-running `publish_gold.py --run-id run-...-gymrep` — `_current` verifiably pointed back at the original 7 Gold objects (exact row counts: `dim_drug=133654`, `fact_sales=16848`, `fact_review=215063`), no DDL, no half-written state at any point (verify-before-copy held both times). ✅ HARDENED.
- ⚠️ Junior mistake : trying to "fix" a stale veneer by re-pointing the Snowflake external table's location, or by hand-editing files under `gold/_current/` — both bypass the one supported recovery path and risk leaving `_current` in a half-written state.
- 🎤 Soundbite      : "The rollback mechanism here is solid — one command, no DDL, lineage always retained — and I've actually run it: publish a bad run over a good one, then roll back by re-publishing the old run_id, and `_current` comes back exactly as it was. But a human still has to remember to type it, because the DAG has no automated publish-and-verify step yet."

---

### P-PMR-04 — Idempotency check: which recovery reruns are safe, and which create a "two run_ids, no decision" trap  [✅ HARDENED]
- Symptom         : a "fix" for a failed run is to just rerun with a new identifier rather than the same one.
- Diagnosis       : check whether the step being rerun is idempotent BY KEY (safe) or appends/creates a new identifier each time (risk).
- Root cause      : N/A for the safe steps (documents why they're safe); for the risk, the cause is generating a NEW `run_id` for what should be a retry of the SAME logical run, leaving two `gold/<run_id>/` dirs with no single one marked canonical until a human runs `publish_gold.py` again.
- Fix / Recovery  : for landing/bronze reruns — just rerun for the same `ds`; the fixed S3 key makes repeats safe (this IS the idempotency-trap class, I11, done correctly: the safe direction). For a Gold-publish recovery — reuse the SAME `run_id` you're fixing forward from where possible, or explicitly decide-and-publish the new one; never leave two unpublished run dirs and assume "the latest one" is obviously canonical.
- Evidence        : `scripts/seed_landing_to_s3.py:5-7` (docstring: "Re-running it just re-uploads the same bytes to the same idempotent date-partitioned key") + `dbt/macros/s3_paths.sql:25-26` (every Gold path is keyed by `run_id` — safe for replay, but ambiguous if multiple run_ids accumulate unpublished). ✅ HARDENED for the documented-safe replay path.
- ⚠️ Junior mistake : "fixing" a failed run by triggering a brand-new timestamped run rather than re-triggering the SAME logical date/run — this is exactly the I11 idempotency-trap class (ADR-006-A1 §5), here in its Gold-publish-recovery form rather than its landing-reseed form.
- 🎤 Soundbite      : "Landing and bronze reruns are safe by construction — fixed keys, true idempotent replay. The trap is at Gold: generating a fresh run_id to 'retry' instead of fixing forward on the same one leaves two unpublished runs with no decided winner."

---

### P-PMR-05 — Cloud-window teardown is a mandatory post-mortem checklist line, not optional cleanup  [✅ HARDENED]
- Symptom         : a Snowflake cloud-window incident/backfill is resolved, and the session just... ends.
- Diagnosis       : check whether the Snowflake warehouse/database/role from this window are still live — there is no automated teardown script.
- Root cause      : N/A — documents the manual-only teardown contract and why it's same-day.
- Fix / Recovery  : `DROP DATABASE NOVARTIS_STTM_DB; DROP WAREHOUSE NOVARTIS_STTM_WH; DROP ROLE NOVARTIS_STTM_ROLE;` as `ACCOUNTADMIN`, executed by Data Platform Engineer the SAME day the backfill/incident is verified resolved — `AUTO_SUSPEND=60` caps idle COMPUTE cost but not multi-day idle existence.
- Evidence        : `docs/OPS_RUNBOOK.md:75` (Backfill Procedure step 5: "there is no `scripts/teardown_snowflake.sql`... Teardown is manual... do not leave the warehouse running") + `:86` (Session End Checklist: "if a Snowflake/MWAA cloud window was opened this session, confirm teardown happened"). ✅ HARDENED.
- ⚠️ Junior mistake : closing the incident ticket as resolved once data is correct, without separately confirming the Snowflake objects opened to investigate/fix it were torn down the same day.
- 🎤 Soundbite      : "Fixing the data isn't the last step in a cloud-window incident — there's no teardown script, so I check Snowsight myself and tear it down same-day before I close the ticket."

---

### P-PMR-06 — The post-mortem write-up is graded against a sealed RUBRIC, not a single answer key  [✅ HARDENED]
- Symptom         : after recovery, the temptation is to write "the cause was X" and move on.
- Diagnosis       : check `docs/incidents/.solutions/INCIDENT_<id>.md` (sealed, gitignored) only AFTER writing your own post-mortem — it holds acceptable diagnosis PATHS and a must-not-do list, not one canonical root cause.
- Root cause      : N/A — documents why this pipeline's grading model is rubric-based.
- Fix / Recovery  : write the post-mortem yourself first (hypothesis trail, evidence cited, what you ruled out, the actual fix/recovery taken); only then diff it against the sealed rubric — this pipeline's crosswalk/reconciliation reality (ADR-003) genuinely admits more than one valid root-cause framing for some incidents, so a single-string answer key would be the wrong tool.
- Evidence        : `docs/ADR/ADR-006-A1-incubator-fidelity-amendment.md` §4 ("Rubric, not a single answer key... Stored sealed at `docs/incidents/.solutions/INCIDENT_<id>.md` (gitignored). Public `INCIDENT_<id>.md` stays symptom-only + user-written.") + the CI gate that keeps this enforceable, `07_cicd_github.md` → `C-CICD-04` (`.github/workflows/ci.yml:51-56`). ✅ HARDENED.
- ⚠️ Junior mistake : peeking at the sealed rubric before attempting your own write-up — defeats the re-derivation that's the actual point of the drill (the rubric existing doesn't replace doing the diagnosis).
- 🎤 Soundbite      : "I write the post-mortem myself, with my own evidence trail, before ever opening the sealed rubric — it's there to check my reasoning against acceptable paths, not to hand me the one true answer."

---

### P-PMR-07 — Re-running the SAME day twice is NOT idempotent: an unguarded tie-break in `stg_beta__ndc` inflates `dim_drug`'s SCD2 history every replay  ★  [✅ HARDENED]
- Symptom         : a "harmless" rerun of the same logical day (e.g. retrying a failed publish, or backfilling a date that already ran once) silently changes `dim_drug`'s row count, even though nothing about the source data changed.
- Diagnosis       : run the full pipeline twice in a row against the identical `LAND_DATE`/bronze data and diff `dim_drug` row counts — they should be byte-identical (per `04_transformation.md` `T-XFM-05`'s reproducibility standard) and, for this column set, weren't.
- Root cause      : `stg_beta__ndc.sql:20-23` dedupes the Beta NDC bronze data with `row_number() over (partition by product_ndc order by marketing_start_date desc)` — no secondary tie-break key. Real query against this session's bronze data found **1,317 `(product_ndc, marketing_start_date)` tie groups covering 2,972 rows** — i.e., real and frequent, not an edge case. `row_number()`'s pick among tied rows isn't guaranteed stable across separate DuckDB sessions reading S3 in a fresh `:memory:` catalog each time (O-AIR-07's same ephemerality, here causing a *different* symptom). When the tied candidates differ on any of `snap_beta_ndc`'s `check_cols` (`generic_name`, `pharm_class`, `route`, `dosage_form`, ...), the SCD2 `check` strategy reads a flipped "winner" as a genuine business-data change and inserts a new history row — inflating the snapshot (and therefore `dim_drug`) on every replay, forever, even though nothing in the real world changed.
- Fix / Recovery  : add a deterministic secondary key to the `row_number()` window, mirroring the EXACT pattern `int_drug_crosswalk.sql:65-74` already uses (`order by marketing_start_date desc, product_ndc` is insufficient since `product_ndc` is the partition key itself and constant within a tie group — needs a real tiebreaker such as a stable hash of the full row, or `labeler_name`/`proprietary_name` if those are reliably distinguishing, or ultimately `load_ts`/source row position if openFDA exposes one). Until fixed, treat any backfill/rerun of an already-published day as a risk of phantom SCD2 history, not a no-op.
- Evidence        : `dbt/models/staging/beta/stg_beta__ndc.sql:20-23` (the unguarded window) vs. `dbt/models/intermediate/int_drug_crosswalk.sql:65-74` (the guarded sibling pattern, `04_transformation.md` `T-XFM-05`) + `dbt/snapshots/snap_beta_ndc.sql:9-13` (`check_cols` that the tie-flip corrupts). **Live reproduction (2026-06-20, `gym-lake`):** two consecutive full `dbt build` runs against the byte-identical `LAND_DATE=2026-06-18` bronze parquet produced `dim_drug` = 133,654 rows (run `run-...-gymrep`) then 133,758 rows (run `run-...-incident`) — a 104-row drift with zero change to any input. DuckDB query against `s3://gym-lake/bronze/beta/2026-06-18/ndc_directory.parquet` confirms `1317` tie groups / `2972` affected rows. ✅ HARDENED — reproduced, not hypothesized; this is also why the live rollback rep above (P-PMR-03) had two genuinely different `dim_drug` counts to roll back between, not a contrived setup.
- ⚠️ Junior mistake : treating "I re-ran the same day's pipeline to be safe" as a strictly harmless, idempotent action — on this specific table, a careless rerun is itself a (small, silent) data-corrupting event, exactly the I11 idempotency-trap failure class (ADR-006-A1 §5), discovered here in a place the existing I11 cards didn't cover.
- 🎤 Soundbite      : "I assumed reruns were safe because the crosswalk's tie-break was already hardened — but I found the identical missing-tie-break bug in a sibling staging model, and proved it live: two back-to-back runs on the same unchanged data gave me two different `dim_drug` row counts. Idempotency has to be checked per-model, not assumed from one good example."

---

## Phase tally
✅ HARDENED: 7 · 🟡 APPLICABLE: 0 · ⚪ N/A: 0 — **7 cards** (drill-ready, C3, cleared 2026-06-20).
