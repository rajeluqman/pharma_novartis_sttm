# Layer 07 — Publish / Pointer-Swap Optimization
> Script: `scripts/publish_gold.py` — promotes a verified `gold/<run_id>/` build into the fixed
> `gold/_current/` serving prefix that Snowflake reads. Theme: **atomic, safe publish** on object
> storage that has no atomic rename (ADR-005). See [00_INDEX.md](00_INDEX.md).

---

### PUB-01 ★ — Verify-then-publish: prove the build is complete before serving it  [✅ DONE]
- **Junior mistake:** Write models straight into the serving location as the run produces them.
- **Why it bites:** Consumers can read the serving prefix mid-build and see a half-written mart — some tables new, some old, some missing.
- **Optimized (this repo):** `verify_run()` confirms every expected Gold object exists and is non-empty *before* `publish_to_current()` touches `_current`. `scripts/publish_gold.py:9-14,41-55,81-85`
- **Business one-liner:** "Dashboards only ever see a fully-built, verified dataset — never a run in progress."
- **Soundbite:** *"Build into a staging prefix, verify, then publish. Readers should never witness construction."*

### PUB-02 ★ — Copy into a stable pointer; don't assume atomic rename on S3  [✅ DONE]
- **Junior mistake:** "Move"/rename the new run's folder onto the serving path, assuming it's atomic like a filesystem.
- **Why it bites:** Object storage has no atomic rename — a move is really delete+copy, so readers can catch a torn state.
- **Optimized (this repo):** publish is an explicit `read_parquet → COPY TO` into `gold/_current/`, and `_current` only changes per model after that model's run object passed verify — so it always holds either the last good run or the fully-published new one. `scripts/publish_gold.py:11,58-70`
- **Business one-liner:** "Switching to the new data is a controlled copy, so the live serving layer is never caught half-updated."
- **Soundbite:** *"On object storage, 'rename' is a lie. Copy into a stable pointer instead."*
- **Related:** PUB-01, PUB-05, GLD-05, BRZ-04 (atomicity + idempotency threads)

### PUB-03 ★ — Retain per-run history; rollback is re-publishing an older run_id  [✅ DONE]
- **Junior mistake:** Overwrite or delete the previous Gold output once the new one is live.
- **Why it bites:** A bad run that passed checks but contains wrong data has no rollback path, and there's no lineage to audit what served when.
- **Optimized (this repo):** every build is kept at `gold/<run_id>/` (not deleted); rollback = re-run publish with an older `--run-id`, a pure data copy with no DDL or warehouse privilege. `scripts/publish_gold.py:14,16-17,88`
- **Business one-liner:** "If a release is bad, we roll back to a previous good dataset in seconds — and we keep a full history of what was served."
- **Soundbite:** *"Keep the runs. Rollback should be choosing an older pointer, not restoring a backup."*

### PUB-04 — Fail loud and abort; never publish a bad run  [✅ DONE]
- **Junior mistake:** Catch the verify error and continue, or publish whatever managed to build.
- **Why it bites:** A partial or empty build reaches BI and is trusted as real.
- **Optimized (this repo):** a failed verify raises `RuntimeError`, and `main()` exits non-zero without publishing — `_current` is left untouched. `scripts/publish_gold.py:51-52,93-97`
- **Business one-liner:** "If a build is incomplete, the publish stops and the previous good data keeps serving — bad data never reaches users."
- **Soundbite:** *"The safest publish is the one that refuses to run when the data isn't right."*

### PUB-05 — Readers point only at the stable `_current` prefix  [✅ DONE]
- **Junior mistake:** Point BI / the warehouse at the latest `gold/<run_id>/` folder.
- **Why it bites:** Consumers must track changing run ids, and they can read a run while it's still building.
- **Optimized (this repo):** Snowflake reads only `gold/_current/`, never per-run paths — the run id is an implementation detail behind a fixed pointer. `scripts/publish_gold.py:13`
- **Business one-liner:** "Reporting always reads from one fixed location — it never needs to know or chase the latest run id."
- **Soundbite:** *"Give consumers a stable address. The run id is your concern, not theirs."*
