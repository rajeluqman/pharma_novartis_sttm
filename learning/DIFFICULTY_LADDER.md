# Incident-Response Difficulty Ladder (Track I)

> Governed by ADR-006-A1 §3/§5. Sibling to `CURRICULUM.md` (which is the DAG-build ladder).
> **Key idea (cabinet ruling):** separate *what breaks* from *how hard it is to find*.
> - **Failure catalogue** = `I1-I12` in `.claude/agents/18-bottleneck-saboteur.md` — the
>   library system-of-record (what can break).
> - **Difficulty ladder (this file)** = how FAR the symptom is presented from the root cause,
>   plus red herrings, time pressure, and recovery risk. The SAME failure (e.g. a 0-byte file)
>   is an L2 drill if the symptom is "bronze=0 rows" and an L5 drill if the symptom is
>   "coverage KPI dropped 12%".

## What gets harder as you climb
| Axis | Low levels | High levels |
|------|-----------|-------------|
| Symptom distance | at/near the root (bronze count) | far (business KPI / dashboard) |
| Causes | single | compound / contributing |
| Red herrings | none | misleading-but-innocent signals |
| Theatre | none | SEV tag + fake alert + growing blast radius (L7+) |
| Recovery risk | trivial re-run | idempotency trap, downstream re-enable order |

## The ladder
| Level | Focus skill | Symptom distance | Mechanics introduced | Example failure (catalogue) |
|-------|-------------|------------------|----------------------|------------------------------|
| **L1** | Run the 8-step checklist at all | symptom = the failure | observability-first; hypothesis log | I1 0-byte file (symptom: task error) |
| **L2** | Localize layer from a clean error | near root | evidence-gate (command+output) | I2 truncated download (symptom: parse error) |
| **L3** | Code-bug vs data-quality isolation | near root | clean-sample rerun | I5 bad join (symptom: bronze→silver count drop) |
| **L4** | Trace BACKWARD one hop | one layer away | reconciliation as diagnostic | I3 schema drift (symptom: downstream type error) |
| **L5** | Trace backward from a business signal | far (KPI/dashboard) | full backward chain | I7 wrong partition (symptom: "numbers look stale") |
| **L6** | Recover SAFELY, not just diagnose | far | graded recovery: idempotent backfill, verify-before-re-enable | I11 idempotency-trap (symptom: counts doubled after a re-run) |
| **L7** | Isolate amid a red herring | far + 1 decoy | SEV tag + fake alert artifact begins | I12 reconciliation-mismatch + a harmless-but-scary log line |
| **L8** | Hold discipline under SEV1 | far + decoy | growing blast radius, MTTR displayed (ungraded) | I8 stale gold pointer (symptom: veneer returns nothing) |
| **L9** | Compound, multi-cause | far + 2 causes | isolate one at a time | I10 schema drift + silent drop together |
| **L10** | Compound + recovery-gone-wrong | far + compound | a naive fix makes it worse; must reconcile + roll back | I6 OOM + a panicked non-idempotent backfill |

## Grading (ADR-006-A1 §3 — method, not clock)
@cikgu scores the **method**, not speed:
- Did you go **observability-first** before touching code?
- Did you **log a hypothesis (test + predicted output) before running**?
- Did you **gate every claim on evidence** (command + output)?
- Did you **rule out branches** instead of thrashing?
- Did you **reconcile counts and verify before re-enabling downstream**?

MTTR is recorded and shown for your post-mortem narrative only — it is **not** a score input.
Fixing fast with no method = low score.

## Resume convention
On return, read the last `LEARNING_LOG.md` entry + your current level here. One drill = one level
boundary; close it with a LEARNING_LOG entry and a user-written post-mortem before climbing.
