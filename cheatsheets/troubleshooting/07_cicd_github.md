# Phase 07 — CI/CD Audit (GitHub Actions / Parse Gate) — Incident Cards  [DRILL-READY]

> Checklist step 7 of 8 (see `00_INDEX.md`). Audit what the CI gate actually proves before
> trusting a green PR. Scope: `.github/workflows/ci.yml`, `scripts/parse_test_mwaa.sh`.
> **DRILL-READY (C3, ADR-006-A1) — cleared 2026-06-20.** All 5 gate steps run for real,
> locally, against this repo's current state (CI itself needs no MinIO — it's deliberately
> data-free, C-CICD-01 — so the "rep" here is executing every step for real rather than
> trusting the YAML). C-CICD-02's gap is no longer hypothetical — ★ it's now grounded in the
> real O-AIR-07 bug (`02_orchestration_airflow.md`), which every gate in this file, including
> the real MWAA parse gate, was confirmed live to miss completely.
> Owned by @incident-responder · Governed by ADR-006 / ADR-006-A1.

---

### C-CICD-01 — CI is deliberately data-free — green PR proves nothing about data incidents  ★  [✅ HARDENED]
- Symptom         : a PR is green; the assumption is "this won't cause an incident."
- Diagnosis       : check what the CI job actually exercises — no cloud creds, no real data, no warehouse connection are available to it at all.
- Root cause      : N/A — documents the intended scope boundary, stated up front in the workflow itself.
- Fix / Recovery  : treat a green CI as proof against CODE regressions only (syntax, lint, manifest/compile, JSON validity) — it says nothing about upstream schema drift, rate limits, row-count drift, or any other DATA-shaped incident, which can only surface on a real run.
- Evidence        : `.github/workflows/ci.yml:3-5` ("Static, data-free gates... No cloud creds, no data, no warehouse... Catches code/config regressions before merge so the incidents that reach a real run are data/operational, not code bugs.") + the job itself (`:18-56`) never touches AWS/Snowflake/MinIO. ✅ HARDENED — this is the workflow's own stated contract.
- ⚠️ Junior mistake : reading "all checks passed" on a PR as "this change is safe to merge and run" — it only rules out one class of failure (code), not the more common class on this pipeline (data).
- 🎤 Soundbite      : "Our CI is intentionally data-free — it proves the code compiles and the manifest parses, not that tomorrow's openFDA pull or Kaggle schema hasn't drifted. Those are different failure classes with different gates."

---

### C-CICD-02 — Even the REAL MWAA parse gate wouldn't have caught O-AIR-07 — no CI/CD gate on this stack executes a task body  ★  [✅ HARDENED]
- Symptom         : a DAG change merges clean through CI, then fails to PARSE on a real MWAA spike with an import error CI never caught. **Worse, proven live 2026-06-20**: a DAG can pass EVERY gate available on this stack — `py_compile`, `dbt parse`, AND the real `DagBag` import against pinned Airflow 2.10.3 — while being unable to complete a single real orchestrated run.
- Diagnosis       : check exactly what CI's DAG-related step does — `python -m py_compile` on `airflow/dags/*.py` only checks Python SYNTAX; it never imports Airflow or instantiates the `@dag` decorator, so it cannot catch an Airflow-version-specific API break (e.g. a removed `default_args` key). Then check what the STRONGER manual gate (`scripts/parse_test_mwaa.sh`, a real `DagBag` import) does or doesn't execute: `DagBag.process_file()` imports the module and calls the `@dag`-decorated factory function to register the DAG object — it does NOT call `.execute()` on any task, so a `subprocess.run(["dbt", ...])` inside a task body never runs during parse, no matter how faithful the Airflow version is.
- Root cause      : the repo's real MWAA-faithful gate (`scripts/parse_test_mwaa.sh` — a one-shot `DagBag` import against the pinned Airflow 2.10.3 image) exists but is NOT wired into `ci.yml` at all — that's the ORIGINAL, narrower finding. The 2026-06-20 rep proved a SECOND, deeper gap underneath it: even if `parse_test_mwaa.sh` WERE wired into CI on every PR, it still would not have caught `O-AIR-07` (`02_orchestration_airflow.md`) — DagBag import is exactly the wrong altitude to catch a bug that only manifests when task bodies actually execute as separate subprocesses. There is currently NO gate anywhere in this repo, manual or CI, that executes a task body.
- Fix / Recovery  : wiring `parse_test_mwaa.sh` into CI (tradeoff: ~26-min Docker image cold build, breaks the $0/seconds design) closes the ORIGINAL gap (Airflow-version API breaks) but would NOT have caught O-AIR-07. Catching O-AIR-07-class bugs needs a different kind of gate entirely — an actual task-body smoke test (e.g. `airflow tasks test <dag_id> <task_id> <date>` run per-task against a throwaway `gym-lake`-style target) — which doesn't exist yet at any tier (manual or CI) and is a separate, not-yet-proposed addition.
- Evidence        : `.github/workflows/ci.yml:27-28` (`python -m py_compile` — syntax only) — no `DagBag`/Airflow-import step anywhere else in the file (full 57-line file confirmed) — vs `scripts/parse_test_mwaa.sh:6-10,98-112` (the stronger manual gate: real `DagBag` import against pinned Airflow 2.10.3, but import-only). **Live reproduction (2026-06-20):** ran `bash scripts/parse_test_mwaa.sh` AFTER independently proving O-AIR-07 (the DAG cannot survive its own task boundaries) — result: `DAGS: ['...', 'pharma_sttm_pipeline_v1']`, `IMPORT_ERRORS: {}`, `PASS`. The strongest gate this repo has stayed fully green on a DAG that cannot complete an orchestrated run. ✅ HARDENED — both the original gap and the deeper one are now proven, not theorized.
- ⚠️ Junior mistake : assuming `py_compile` passing — or even a real `DagBag` import passing — on a DAG file means "this DAG works." Neither executes a single task body; only an actual run (or a per-task smoke test) proves that.
- 🎤 Soundbite      : "I used to think the gap here was 'CI only syntax-checks, the real parse gate is manual' — then I ran the real parse gate AFTER finding a bug where the DAG can't actually complete a run, and it passed anyway. DagBag import doesn't execute a single task body — on this stack, nothing automated does, at any tier."

---

### C-CICD-03 — Gym/regression branches are deliberately excluded from the default trigger  [✅ HARDENED]
- Symptom         : pushing to a `gym/round-NN` fault-injection branch does NOT trigger CI, while a regular feature branch's PR does.
- Diagnosis       : check the workflow's `on:` trigger scope before assuming CI is broken or being skipped.
- Root cause      : N/A — documents the intentional scope boundary.
- Fix / Recovery  : if a specific gym drill needs to assert a code-level regression gate, push to `gym/regression-**` (opt-in), not a generic `gym/round-NN` branch — the two naming patterns have different CI behavior on purpose.
- Evidence        : `.github/workflows/ci.yml:7-12` (`on: pull_request: branches:[main]` + `push: branches: ['gym/regression-**']` — `gym/round-NN` branches are NOT in this list and do not trigger CI). ✅ HARDENED.
- ⚠️ Junior mistake : filing a CI-is-broken ticket because a `gym/round-04` branch shows no Actions run — that's by design; fault-injection branches shouldn't trip a generic merge gate.
- 🎤 Soundbite      : "Gym drill branches don't auto-trigger CI on purpose — sabotage-on-purpose shouldn't look like a CI outage. The opt-in `gym/regression-**` pattern exists for when a drill specifically needs the code gate."

---

### C-CICD-04 — Sealed-rubric leak gate: CI fails the build if the answer key is ever tracked  ★  [✅ HARDENED]
- Symptom         : a PR fails CI with `::error::a sealed rubric under docs/incidents/.solutions/ is tracked — remove it`.
- Diagnosis       : check `git ls-files 'docs/incidents/.solutions/'` locally — if it returns anything, the gitignored sealed rubric got `git add`-ed by mistake.
- Root cause      : a blanket `git add -A`/`git add .` after writing or editing a local rubric note staged the gitignored path despite `.gitignore`, OR the `.gitignore` entry itself was removed/edited.
- Fix / Recovery  : `git rm --cached -r docs/incidents/.solutions/` and recommit — never relax this CI check to "fix" a failure here; the check existing IS the fix.
- Evidence        : `.github/workflows/ci.yml:51-56` (exact assertion: any tracked file under that path fails the job with `exit 1`) — ties to ADR-006-A1 §4 (the rubric must stay sealed, not a single public answer key). ✅ HARDENED.
- ⚠️ Junior mistake : using `git add -A` while working in `docs/incidents/` — the broad add is exactly the habit this gate exists to catch before a sealed answer reaches a PR diff.
- 🎤 Soundbite      : "We don't rely on remembering not to commit the rubric — CI asserts `docs/incidents/.solutions/` stays untracked on every PR, so a `git add -A` mistake fails the build instead of leaking the answer key."

---

### C-CICD-05 — `dbt parse` proves the manifest compiles with ZERO connection, not that models will pass  [✅ HARDENED]
- Symptom         : `dbt parse` is green in CI; conflating that with "the dbt build will succeed."
- Diagnosis       : `dbt parse` only resolves refs/macros/Jinja into a valid manifest — it never connects to DuckDB or Snowflake, never executes a model, never runs a test.
- Root cause      : N/A — documents the scope of this specific check.
- Fix / Recovery  : treat `dbt parse` green as "this will compile," and rely on a real `dbt build` (locally, against `dev`) for "this will actually run and pass tests" — don't skip the local build step just because CI's parse passed.
- Evidence        : `.github/workflows/ci.yml:42-49` (`pip install --quiet dbt-duckdb` then `dbt parse` — no `DBT_TARGET`-specific connection vars set beyond `DBT_PROFILES_DIR`, no `dbt run`/`dbt test`/`dbt build` invoked anywhere in the job). ✅ HARDENED.
- ⚠️ Junior mistake : skipping a local `dbt build` before opening a PR because "CI runs dbt anyway" — CI only parses; it never builds or tests a single model.
- 🎤 Soundbite      : "CI's dbt step only parses the manifest — zero connection, zero models run. I still run a real `dbt build` locally before opening the PR, because parse-clean and build-clean are different claims."

---

### C-CICD-06 — GE suite JSON validity is checked at PR time, not discovered at 3am during `dq_checks()`  [✅ HARDENED]
- Symptom         : a hand-edited `data_quality/expectations/*.json` file has a syntax typo.
- Diagnosis       : check whether CI's JSON-validity step caught it on the PR, before it ever reaches a real `dq_checks()` run.
- Root cause      : N/A — documents the early-catch guard.
- Fix / Recovery  : fix the JSON locally and re-push; `python -m json.tool` against the exact file gives the same parse error CI reports.
- Evidence        : `.github/workflows/ci.yml:35-40` (loops every file under `data_quality/expectations/*.json` through `python -m json.tool`, failing the step on the first invalid file). ✅ HARDENED.
- ⚠️ Junior mistake : hand-editing a GE expectations JSON file and assuming "it'll fail loudly and obviously" at runtime if there's a typo — without this gate, a malformed suite file can fail in a confusing way deep inside `great_expectations`' own JSON loader during a real pipeline run instead of at PR review.
- 🎤 Soundbite      : "A malformed expectations file fails fast at PR time here, with a plain `json.tool` error — not three hours into an overnight run when `dq_checks()` tries to load it."

---

## Phase tally
✅ HARDENED: 6 · 🟡 APPLICABLE: 0 · ⚪ N/A: 0 — **6 cards** (drill-ready, C3, cleared 2026-06-20).

Live rep note (2026-06-20): all 5 gate steps in `ci.yml` were run locally against this repo's
current state — `py_compile` PASS, `ruff` found 2 real PRE-EXISTING lint errors in
`scripts/provision_snowflake_veneer.py:144,146` (unrelated to this session's changes — proof
the lint gate is live and not theater, not a new finding to chase here), GE-JSON validation
PASS (3/3 files), `dbt parse` PASS, sealed-rubric-untracked check PASS.
