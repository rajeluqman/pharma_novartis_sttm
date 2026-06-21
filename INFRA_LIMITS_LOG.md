# INFRA_LIMITS_LOG.md
**Owner**: @infra-reality-agent

| Date | Service | Limit Hit | Workaround | Time Lost |
|------|---------|-----------|------------|-----------|
| YYYY-MM-DD | Databricks | SQL only, no PySpark cluster | Use dbt + SQL | 1h |

## Trial Status Snapshot
| Service | Days Left | Credits Left |
|---------|-----------|--------------|
| Databricks | N | $X |
| Snowflake | N | $X |
| Azure | N | $X |

## Lessons (avoid next time)
- <lesson>

---

## 2026-06-18 — ADR-005 P5 parse-test sanity check (@infra-reality-agent)
**Verdict: GO ($0) — status: ok.** Reviewed the request to pin a 2.10.x Airflow
in a separate cloud requirements file and parse-test `pharma_sttm_pipeline.py`
via `aws-mwaa-local-runner`, LOCAL PARSE ONLY (no MWAA env, no AWS spike).

**Cost (money):** $0 against all trials. MWAA has NO free tier (~$50–100/mo) — but
nothing here touches MWAA the AWS service. `aws-mwaa-local-runner` is a Docker
image that runs MWAA's base on localhost; it never calls an AWS API. Confirmed $0.

**Cost (non-money — real, not a blocker):**
- Docker base-image pull ≈ 1.5–2.5 GB; built local image can reach ~3–4 GB.
- Disk: budget ~5 GB free for image + layers. Build/pull time: several minutes
  on first run (cached after).
- These are time/disk, NOT credits. Flagged so the owner isn't surprised.

**Target to pin:** `apache-airflow==2.10.3` (current MWAA 2.10.x line; pick the
exact patch MWAA exposes at execution time — 2.10.3 is the safe default).
Python **3.11** (MWAA 2.10.x runtime). Constraints file:
`https://raw.githubusercontent.com/apache/airflow/constraints-2.10.3/constraints-3.11.txt`
Keep this in a SEPARATE cloud requirements file (e.g.
`requirements/requirements-mwaa.txt`) — do NOT touch dev `requirements/requirements.txt`
or the unpinned 3.x `.venv`.

**Why Docker local-runner, not a bare 3.12 venv pip:** local interpreter is
Python 3.12; MWAA 2.10.x runs 3.11. The local-runner bundles MWAA's real 3.11
base image, so the parse runs on the faithful interpreter+lib matrix. A bare
`pip install apache-airflow==2.10.3` into the 3.12 venv would parse on the wrong
Python and miss runtime-divergence bugs. Break-point confirmed:
`default_args={"sla": ...}` (line 43) + TaskFlow `@dag/@task/@task_group`
decorators — `sla` was REMOVED in Airflow 3.0, which is exactly why 3.2.2 in
`.venv` is an invalid parse target and 2.10.x is the right one.

**Lighter OPTION (owner asked for local-runner, so this is advisory only):** a
throwaway py3.11 venv + `pip install apache-airflow==2.10.3 -c <constraints>` +
`DagBag().import_errors` import check is faster/smaller than a full image build,
but is LESS faithful (no MWAA base image, host py3.11 not guaranteed). Acceptable
as a smoke pre-check; the local-runner remains the authoritative gate.

**Reproducibility guardrails (keep it $0 and contained):**
- Do NOT run `./mwaa-local-env start` long-lived — use a one-shot parse (e.g.
  `docker run ... airflow dags list-import-errors` / python DagBag import). A
  running webserver/scheduler is unnecessary for a parse gate.
- Image and volumes are LOCAL only. Nothing reads AWS creds from `.env`; do not
  mount `.env` / `~/.aws` into the container for a parse test.
- This closes P5 only. P4 (httpfs offline-load) is the NEXT, separate gate — P5
  before P4 per ADR-005.

**GO / NO-GO:** GO for @data-platform-engineer + @devops-orchestrator, conditions
above honored.
