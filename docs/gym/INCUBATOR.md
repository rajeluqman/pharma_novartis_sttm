# The Incubator — how to run a troubleshooting drill safely

> Governed by ADR-006 + ADR-006-A1. The incubator lets you break the pipeline and practise
> diagnosing it **without ever touching the live AWS lake, the live Snowflake veneer, or `main`**.
> Companion to the SLA gym (`SLA_GYM_PROMPT.md`).

## Why it's safe (3 mechanical layers — not prose)
1. **Distinct storage** — drills write to a LOCAL MinIO bucket `gym-lake`, never the prod
   `novartis-pharma-sttm-lake`. Config lives in committed `gym.env`.
2. **Fail-closed guard** — `scripts/gym_guard.py` ABORTS the run unless `GYM_MODE=1` AND
   bucket=`gym-lake` AND endpoint is local AND creds aren't real. (Closes the `s3_env.py`
   fail-open hole — see ADR-006-A1 §1.)
3. **Throwaway git branch** — each drill runs on `gym/round-NN`; `main` is never touched.
   Reset = `git checkout main` / delete the branch. Because it runs the REAL code, the error
   you see is identical to a production failure.

## Start a drill (the only supported path)
```bash
# 1. cut an isolated branch from main
git checkout main && git checkout -b gym/round-07-<slug>

# 2. point EVERYTHING at the local gym-lake (fail-closed contract)
set -a; source gym.env; set +a

# 3. preflight — refuses to continue if the env could hit prod
python scripts/gym_guard.py    # exit 0 = safe; non-zero = aborted, nothing ran

# 4. fault injection breaks the pipeline (Track I), logs SYMPTOM only to SABOTAGE_LOG.md,
#    seals the RUBRIC at docs/incidents/.solutions/INCIDENT_<id>.md (gitignored)

# 5. YOU diagnose — run real commands against gym-lake, read real errors/output
# 6. self-review coaches the METHOD (never reveals the sealed cause)
```

## The drill loop (what each step does)
1. **Fault injection** — injects one Track-I failure into the gym branch; logs the
   **symptom only** (presented FAR from the root cause — a business/observability signal, not
   "bronze=0 rows"); seals the rubric.
2. **YOU** — observability first ("what does the signal say?"), then a **hypothesis log** in
   `docs/incidents/INCIDENT_<id>.md` *before* running anything: `hypothesis → test → predicted
   output`. Run the test. Record actual vs predicted. Rule out, repeat. **No hypothesis is
   accepted without command + output** (evidence-gate).
3. **Incident documentation** — scaffolds the 8-step skeleton + sealed rubric; after you solve,
   grades your path against the rubric (acceptable paths + must-not-do list) and distils a card.
4. **Self-review** — Socratic; after 2 failed hypotheses, hints the *method* ("what does the log
   timestamp tell you?"), never the answer. Scores the **method**, not the clock.

## Recovery is graded too (not just diagnosis)
A drill isn't done when you find the cause — it's done when you **recover safely**:
idempotent backfill, **reconcile counts before you trust the fix**, verify before re-enabling
downstream. Causing a second outage (double-load, re-enable-too-early) fails the recovery grade.

## Severity / MTTR / alert theatre
- **L1-L6:** plain symptom, no theatre — learn to trace.
- **L7+:** fake alert artifact (PagerDuty/Slack-style), SEV1/2/3 tag, blast radius grows over
  "time". MTTR is **displayed for your post-mortem story but is NOT graded** (ADR-006-A1 §3).

## Reset between drills
```bash
git checkout main
git branch -D gym/round-07-<slug>      # throw the sabotage away
# gym-lake is local MinIO — wipe the bucket prefix or just re-seed for the next drill
```

## Hard rules (ADR-006-A1)
- Never run a drill without `source gym.env` + a green `gym_guard.py`.
- Never point a drill at `novartis-pharma-sttm-lake` or the live Snowflake veneer.
- The sealed rubric (`docs/incidents/.solutions/`) is gitignored — don't read it before you solve.
