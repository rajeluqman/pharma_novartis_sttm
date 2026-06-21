# TICKET — CI/CD: GitHub Actions for the pharma STTM platform (DIY Build Mode)

> Mentor writes the WHAT, not the HOW. You build `.github/workflows/ci.yml` yourself (cheatsheet at
> your elbow). When you say "done", we diff vs an answer key and quiz WHY on every difference.
> No peeking at a finished workflow first — you type it.

## Goal
A GitHub Actions **CI** workflow that runs on every Pull Request and PROVES the pipeline still builds
and passes its tests — entirely on **DuckDB ($0, no cloud, no secrets)**. If anything breaks, the PR
goes red and can't merge. (CD — publishing docs on merge — is a SEPARATE later ticket.)

## Inputs you already have (don't rebuild these — call them)
- `requirements/requirements.txt` — deps to install.
- `dbt/` project (profile `novartis_pharma`, target `dev` = DuckDB `:memory:`).
- `scripts/run_ge_validation.py` — the Great Expectations gate.
- `scripts/parse_test_mwaa.sh` — the heavy MWAA DAG-parse (Docker, ~26 min — TOO heavy for CI; in CI
  do a lightweight `DagBag` import instead, like the one-liner inside that script).
- The S3-canonical code reads `S3_ENDPOINT` etc. — for CI you want the **DuckDB-local** path, NOT S3.
  Think: what env makes `dbt build` run against a local DuckDB with no S3 calls?

## Acceptance criteria (Definition of Done)
1. File `.github/workflows/ci.yml`, valid YAML, triggers on `pull_request` (and pushes to a branch is fine).
2. One runner job that: checks out → sets up Python → installs `requirements.txt`.
3. Runs, in order, failing the job on any error:
   - `dbt parse` (or `dbt compile`) — syntax + ref/lineage valid
   - `dbt build` against **DuckDB dev** (seeds + staging + snapshot + marts + tests) — needs the
     landing/bronze data to exist in CI; decide how (hint: the gym/sample seeds, or generate a tiny
     fixture — you do NOT have real S3 in CI)
   - the **DAG parse** check (lightweight `DagBag` import, zero import errors)
4. **No secrets, no real AWS/Snowflake/MWAA.** If your workflow needs `AWS_*` or `SNOWFLAKE_*`, you've
   gone wrong — CI must be self-contained on DuckDB.
5. You can explain every `step` and why it's there.

## Out of scope (do NOT do in this ticket)
- The CD workflow (Confluence publish on merge) — later.
- Running the real `run_pipeline_aws.sh` / provisioning — that's manual, costs money, never in CI.
- Caching, matrix builds, badges — nice-to-have, not now.

## The honest hard part (think before you type)
`dbt build` in CI needs *some* data to build from. On your machine it reads S3/MinIO. A fresh GitHub
runner has neither. So the real design question this ticket is teaching: **how do you give CI a tiny,
deterministic, cloud-free dataset so the build is meaningful but $0 and fast?** Sketch your answer in a
comment at the top of the file BEFORE writing steps. (There are 2–3 valid approaches; pick one and
defend it.)

## Concepts the mentor will quiz (WHY before HOW)
- Why does CI run on **DuckDB**, not the Snowflake/S3 the real pipeline uses?
- A GitHub runner starts empty every time — what does that force you to do in the workflow?
- Why must `AWS_SECRET_ACCESS_KEY` never appear in `ci.yml`? Where would a *real* secret go if CD needed one?
- `job` vs `step` vs `action` — what's the difference?
- What exactly makes a failed step **block the merge**?

## Method — "Plan in Comments, Then Fill"
1. Decompose: one sentence — "on PR, prove the platform builds on DuckDB."
2. Write the workflow as **comments only** first: `# trigger`, `# checkout`, `# python`, `# install`,
   `# dbt parse`, `# dbt build (duckdb)`, `# dag parse`, `# (fixture/data step?)`.
3. Per comment, find the ONE action/command: `actions/checkout@v4`, `actions/setup-python@v5`, `run: ...`.
4. Fill each comment with one line. You never face a blank file.

## When stuck
Don't ask for the YAML. Ask: "where's the official doc for X?" — mentor's first answer is a doc pointer
(`site:docs.github.com/actions pull_request trigger`), not a snippet. Each hint = −5 score.

When done: say "done", and we open the answer key, diff line-by-line, and quiz the WHY.
