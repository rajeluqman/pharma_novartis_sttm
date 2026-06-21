# ADR-006-A1 — Amendment: Incubator, Fidelity Mechanics & CI for the Incident-Response Gym

- **Status:** Accepted (amends ADR-006)
- **Date:** 2026-06-19
- **Type:** AMENDMENT (refines the *implementation* of ADR-006; not a new decision → not ADR-007)
- **Decider:** Data Architect (veto — GO, conditional), reviewed by Data Platform Engineer,
  FinOps review, and Senior Data Engineer.

## Context
ADR-006 established the Incident-Response Gym (Track I + `cheatsheets/troubleshooting/` +
`docs/incidents/`). This amendment reviews an enhancement package to make it (a) **safe** (the
fault-injection tool must never touch the live AWS lake) and (b) **simulate real on-call
troubleshooting**. Two CRITICAL findings + several binding edits emerged.

## Decisions (binding unless marked optional)

### 1. Fail-closed isolation (CRITICAL — was a real blast-radius hole)
`scripts/s3_env.py` **fails open**: unset `S3_ENDPOINT` ⇒ real AWS, and the default `S3_BUCKET`
is the LIVE `novartis-pharma-sttm-lake`. "Gym never hits prod" was prose, not mechanism. BINDING:
- **`gym.env`** (committed; overrides `.gitignore` `*.env` via `!gym.env`) hard-sets
  `GYM_MODE=1`, `S3_BUCKET=gym-lake` (a DISTINCT bucket — the load-bearing guard),
  `S3_ENDPOINT=localhost:9000`, fake creds.
- **`scripts/gym_guard.py`** — fail-closed preflight: ABORTS unless GYM_MODE=1 AND bucket=gym-lake
  AND endpoint is local AND creds aren't real-looking. Every drill runner calls it first.
- No drill runs until both are in place (region-lock protects egress but NOT request/mutation
  against the live bucket — confirmed by Data Platform Engineer + FinOps review).

### 2. Incubator = git branch + gym.env + real code
Per-drill branch `gym/round-NN`; `main` + live cloud never touched. Runs the REAL pipeline code
so the thrown error == production fidelity. (Docker-compose `--profile gym` is an OPTIONAL future
belt; the env guard is the load-bearing mechanism.)

### 3. Grade METHOD, not the clock (BINDING)
- **MTTR is captured + displayed but NOT a graded input** (raw-MTTR scoring teaches cowboy fixes).
  It feeds the post-mortem narrative only.
- Severity tier + fake-alert theatre **introduced at L7+ only** (cognitive-load at L1-3).
- The learning-score grades the **method** (hypotheses logged, evidence-gated, branches ruled
  out, verify-before-re-enable) — NOT speed, NOT merged with the recovery outcome.

### 4. Rubric, not a single answer key (BINDING)
The sealed answer is a **RUBRIC** (acceptable diagnosis paths + a must-not-do list), not one
canonical string. A single key implies one root cause; this pipeline's crosswalk/reconciliation
reality (ADR-003) admits multiple valid paths. Stored sealed at
`docs/incidents/.solutions/INCIDENT_<id>.md` (gitignored). Public `INCIDENT_<id>.md` stays
symptom-only + user-written.

### 5. Three new catalogue failure classes (BINDING)
Add to the Track-I catalogue: **idempotency-trap** (re-run double-loads), **reconciliation-
mismatch** (counts silently diverge), and make **observability-first** the mandatory first
drill step ("what does the signal say" before touching code). Data reconciliation = the
universal diagnostic for the data-failure classes.

### 6. Static-gate CI (APPROVED as-is)
Minimal GitHub Actions: dbt parse/compile + DAG DagBag import + lint + GE-suite JSON validity.
Scoped `on: pull_request: branches:[main]`; gym branches do NOT auto-trigger (opt-in via
`gym/regression-**` for code-regression drills). $0 (no data/creds needed). CI also asserts
`docs/incidents/.solutions/` stays untracked.

### 7. No separate Optimization Gym (RATIFIED)
Optimization is a different cognitive mode (proactive/divergent vs reactive/convergent). The
existing **SLA gym (S1-S10 fault-injection + `docs/sla/SLA_ANALYSIS.md`)** already IS the
optimization gym. Only additive: wire a REAL Gantt capture into one rung (self-play is
`time.sleep`-modeled). The optimization library stays a static system-of-record catalog fed by
the SLA gym's 🟡→✅ promotions. Reuse only the evidence-gate from the troubleshooting mechanics.

## Naming/placement (BINDING)
- `gym-lake` (bucket), `gym/round-NN` (branches), `learning/DIFFICULTY_LADDER.md` — approved.
- **`gym.env`** (NOT `.env.gym` — the latter is silently ignored by `.env.*`); requires `!gym.env`.
- `docs/incidents/.solutions/` gitignored (added).

## Consequences
- (+) Mechanical, fail-closed safety — sabotage cannot reach the live lake.
- (+) Drills mirror real on-call: backward tracing, evidence discipline, graded recovery.
- (+) $0 cloud. Pilot gate held — prove mechanics on Ingestion first.
- (−) `s3_env.py` keeps its fail-open default for prod ergonomics; the guard compensates for gym use.
- (−) **Permanent fidelity boundary, accepted (2026-06-19):** the incubator's substrate is
  MinIO + DuckDB, which has no external-table metadata cache. Snowflake server-side behavior
  that depends on that cache — specifically `ALTER EXTERNAL TABLE ... REFRESH` stale-metadata
  semantics (card L-SNO-03, `cheatsheets/troubleshooting/05_load_snowflake.md`) — cannot be
  mechanically reproduced by any MinIO loop, no matter how many times it's run. This is not an
  incubator gap to close; it is a substrate limit. **L-SNO-03 stays capped below L5 grading
  permanently**, unless a future drill ever adds a real Snowflake session to the loop — which
  ADR-006-A1 §1-2 deliberately forbids (drills never touch the live Snowflake veneer). All
  other layer-05 cards (L-SNO-01/02/04/05, pure S3-side `publish_gold.py` mechanics) are
  unaffected and cleared to L10 by the same MinIO-loop evidence that cleared layers 04/06.

## Addendum: sealed rubric — untracked-ness downgraded (2026-06-21)
Repo flipped PRIVATE (owner decision, confirmed `gh repo view --json isPrivate` → `true`). Owner
then deliberately tracked `docs/incidents/.solutions/INCIDENT_2026-06-19_beta-zero-byte-landing.md`
(commit `65df336`, "Track sealed incident rubrics in private repo for cikgu teaching"), reasoning
that a gitignored file is not backed up — it would be silently lost on Codespace
recreation/re-clone, breaking the rubric for cikgu's future use. This is a real durability
problem the untracked approach could not solve.

Re-assessed §4/§6's `gitignored`/`stays untracked` requirement against the two functions it was
actually serving:
- **Public-leak prevention** — the original primary driver. Moot now: the repo is private, so
  nobody outside has read access regardless of git-tracked status.
- **Anti-accidental-self-spoiler friction** — untracked-ness never technically blocked the owner
  from opening the file at any time; it only kept it out of `git ls-files`/push. This was always
  a discipline nudge, not an access boundary, so tracking it removes no real protection.

**Ruling: §4/§6's "stays untracked" clause is downgraded from a binding mechanical control to a
non-requirement**, superseded by deliberate git-tracking for durability. The rubric itself stays
sealed in spirit (acceptable-paths + must-not-do list, not skimmed casually mid-drill by
convention) — only the untracked-enforcement mechanism is retired. CI's "sealed answer keys must
stay untracked" step is removed accordingly (`.github/workflows/ci.yml`). Re-activate the
untracked requirement (and restore the CI gate) if this repo ever goes public again.

## C3 clearance (2026-06-19)
ADR-006-A1 §1-2's mechanism-proof bar — "the cited file:line guards behave as described against
real S3-compatible storage, not just read as source" — is **satisfied for layers 04, 05, 06**:
a real pipeline run (seed → `load_bronze.py` → `dbt build` PASS=63/WARN=1/ERROR=0 →
`publish_gold.py --run-id` verify-then-copy, all 7 Gold objects → `run_ge_validation.py`
OVERALL: PASS) executed against local MinIO `gym-lake`, independently re-verified (container
creds, `gym_guard.py` rerun, DuckDB+httpfs row-count cross-check, citation-line re-read, GE
cache-freshness check). Architecture sign-off: layers 04 and 06 **drill-ready to L10**; layer 05
**drill-ready to L10 except L-SNO-03**, capped per the Consequences entry above. Governance
follow-up: `SIGN_OFF_LOG.md` entry + a project stack-notes status-line update (both same date).
