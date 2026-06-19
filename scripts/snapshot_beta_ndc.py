#!/usr/bin/env python3
"""snap_beta_ndc externalization wrapper (ADR-005 Decision 2) — DOCUMENTED DEVIATION.

ADR-005-build-decisions.md Decision 2 asks for `snap_beta_ndc` to materialize via "dbt-duckdb
`external` materialization for the snapshot relation, explicit `location`". That is NOT
achievable as literally specified: dbt-core's `snapshot` materialization
(dbt/include/global_project/macros/materializations/snapshots/snapshot.sql) is hardcoded to
`type='table'` and drives an `UPDATE`/`INSERT` MERGE against a real relational target via
`get_or_create_relation` / `assert_valid_snapshot_target_given_strategy`. dbt-duckdb has no
override of this materialization, and there is no `{% materialization snapshot, adapter="duckdb" %}`
anywhere to add a `location`-based external variant to. `external` is a `model`-only
materialization in dbt-duckdb (dbt/include/duckdb/macros/materializations/external.sql) — it
cannot be attached to a `snapshot` block.

MINIMAL EQUIVALENT implemented instead, preserving Decision 2's actual intent ("the snapshot's
prior state is read from S3 at the start of each run and the new version is written back to S3
at the end... a cold ephemeral worker can reconstruct the diff by reading snapshots/ + current
silver Beta, with zero local state"):

  1. `dbt build --select staging snap_beta_ndc` runs the snapshot's upstream staging view
     (`stg_beta__ndc`) AND the snapshot itself in ONE dbt invocation, so both share the SAME
     ephemeral `:memory:` DuckDB session/catalog (Condition C respected — no warehouse.duckdb
     file). A bare `dbt snapshot` run, by itself, fails on a cold ephemeral catalog: dbt
     re-derives `{{ ref('stg_beta__ndc') }}` against the live catalog, and a fresh `:memory:`
     session has no `main_enrich.stg_beta__ndc` view unless something built it first IN THAT
     SAME PROCESS (a separate `dbt run` subprocess would build it into a DIFFERENT, now-discarded
     `:memory:` catalog — verified empirically: `Catalog Error: Table ... does not exist because
     schema "main_enrich" does not exist`). `dbt build` is therefore the only correct invocation
     shape for this snapshot under Condition C, not a `dbt run` + `dbt snapshot` two-step.
  2. `on-run-start` hook (dbt_project.yml -> load_snap_beta_ndc_from_s3 macro) runs INSIDE that
     same session, before the snapshot materialization's existence check: if
     s3://<bucket>/snapshots/snap_beta_ndc/snap_beta_ndc.parquet exists, it is loaded into a real
     table `snapshots.snap_beta_ndc` in the session catalog. This makes a cold worker's first
     query of "does the snapshot target exist" see the S3-persisted prior state, so dbt takes the
     incremental SCD2-merge branch (not the initial-build branch) — exactly the cold-start
     replay property Condition C/Decision 2 require.
  3. `on-run-end` hook (-> export_snap_beta_ndc_to_s3 macro) runs in the SAME session right after
     the snapshot materialization commits, COPYing the now-updated `snapshots.snap_beta_ndc`
     table back out to the S3 parquet path. The :memory: catalog is then discarded with the
     process exit — S3 parquet remains the only persistent truth, never a local file.

Net effect: S3 parquet IS the persistent SCD2 history (Decision 2's requirement), the DuckDB
catalog stays ephemeral end-to-end (Condition C), and the round-trip is stateless-worker-safe.
What's NOT true: the on-disk artifact between runs is not produced by dbt's `external`
materialization syntax — it's produced by two hook-macros wrapping the stock `snapshot`
materialization. That is the deviation; it is functionally equivalent, not a workaround that
skips the requirement.
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DBT_DIR = ROOT / "dbt"


def dbt_bin() -> str:
    venv_dbt = ROOT / ".venv" / "bin" / "dbt"
    if venv_dbt.exists():
        return str(venv_dbt)
    found = shutil.which("dbt")
    if found:
        return found
    raise FileNotFoundError("dbt executable not found (checked .venv/bin/dbt and PATH)")


def run() -> None:
    # `dbt build`, not `dbt snapshot` — see module docstring point 1: the snapshot's upstream
    # staging view must be built in the SAME ephemeral session, in the SAME dbt invocation.
    cmd = [dbt_bin(), "build", "--select", "staging", "snap_beta_ndc", "--profiles-dir", ".", "--project-dir", "."]
    print(f"[snapshot] running: {' '.join(cmd)} (cwd={DBT_DIR})")
    print("[snapshot] on-run-start hook will seed snapshots.snap_beta_ndc from S3 prior state (if any)")
    result = subprocess.run(cmd, cwd=str(DBT_DIR))
    if result.returncode != 0:
        print("[snapshot] dbt build (staging + snap_beta_ndc) FAILED")
        sys.exit(result.returncode)
    print("[snapshot] on-run-end hook exported snapshots.snap_beta_ndc back to S3 — see dbt log above")


if __name__ == "__main__":
    run()
