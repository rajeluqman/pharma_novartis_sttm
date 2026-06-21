# COST_LOG.md
**Owner**: @finops-agent
**Last updated**: 2026-06-19 — post ADR-005 S3-canonical migration (LIVE on real AWS)
                  + LLM token-burn monitor (parallel-session watch) added below

Update every phase.

---

## 🛑 LLM Token Burn — Parallel Session Monitor (2026-06-19 05:23)
**Mood: PANIC.** This is a SECOND cost axis, separate from cloud dollars above:
the Claude **model tier × token** spend across the parallel CLI sessions. Cloud
$ ≈ $0; the real burn right now is **LLM tokens on Opus**.

**Finding**: 4 active parallel sessions, **ALL on `claude-opus-4-8`** (the most
expensive tier). Cabinet policy (CLAUDE.md) reserves Opus for **@data-architect
only**; everyone else is Sonnet (strategic) or Haiku (executors). Running every
session on Opus violates that locked assignment.

| Session (jsonl prefix) | Task | Msgs | Opus output tok | Cache read | Verdict |
|---|---|---|---|---|---|
| `88dd884b` | STTM build / exec | 250 | 615,986 | 46.8M | Opus only for live design reasoning; if writing files → **drop to Sonnet** |
| `b57a509f` | "list phases, brief simple je" | 133 | 181,239 | 10.0M | 🛑 **clear waste** → **Haiku/Sonnet** |
| `b4dd1571` | optimization scan + interview Q&A | 88 | 176,808 | 6.6M | interview answers don't need Opus → **Sonnet** |
| `e65ee88a` | troubleshooting learning (teaching) | 15 | 26,993 | 0.3M | teaching = @cikgu (Sonnet) → **Sonnet** |
| _(`9e6da8e0` = this FinOps monitor session)_ | — | 6 | 8,862 | — | n/a |

**Σ Opus output ≈ 1.0M tok across the 4 worker sessions.** Output tokens are the
dominant driver on Opus (≈5× Sonnet, ≈15–19× Haiku per output tok). Cache reads
are cheap (~10% of input rate) but `88dd884b`'s 46.8M cache-read is still non-trivial
volume sustained on the Opus rate card.

**🛑 BUDGET ALERT — recommended downgrades (owner runs `/model` in each session):**
- `b57a509f` → **`/model haiku`** (or sonnet) — simple listing task, no reasoning depth needed.
- `e65ee88a` → **`/model sonnet`** — teaching/explainer content.
- `b4dd1571` → **`/model sonnet`** — keep Opus only while doing genuine architecture design; switch back for Q&A.
- `88dd884b` → stay Opus **only** if actively making STTM/architecture decisions; **`/model sonnet`** once it's writing/executing.

**Enforcement note (honest limit)**: @finops-agent can MONITOR (read each session's
transcript JSONL + usage) and FLAG, but **cannot change another live session's model**
— model tier is set per-session by the owner via `/model` in that terminal. This is a
soft-veto recommendation, not an automatic action. Overrulable by @data-architect if a
session genuinely needs Opus-tier reasoning.

---

## Budget
| Resource | Total Budget | Trial Window |
|----------|-------------|--------------|
| AWS (S3 + IAM) | Free Tier + pay-as-you-go | ongoing — S3 is now ALWAYS-ON canonical storage, not a trial window |
| Snowflake | $400 trial credit | 30 days |
| MWAA | N/A — not yet stood up | would be a short-window spike if/when run |
| Azure | $200 | 30 days (unused this build) |

## ADR-005 FinOps premise (supersedes the old stale assumption)
The previous version of this log assumed a short-window "$3–5 teardown" applied to the whole stack.
That premise is **retired** as of the ADR-005 migration going live 2026-06-19. The corrected model:
- **S3 is steady-state, always-on canonical storage** — it is **not torn down** after a session. It
  holds landing/bronze/silver/gold parquet permanently (versioned, lifecycle-managed).
- **MWAA and the Snowflake serving veneer remain the short-window items** — Snowflake's external
  tables/storage integration are cheap to stand up and tear down; MWAA has not been stood up at all
  yet (still $0).
- Region lock (`aws:RequestedRegion` Deny on the bucket policy) removes the main cost-risk vector
  for S3 (cross-region egress) by construction, not by discipline.

## Burn per Phase
| Phase | Resource | Amount | Notes |
|-------|----------|--------|-------|
| 1 | — | $0 | Discovery only |
| 2 | — | $0 | Exploration / profiling, local only |
| 3 | — | $0 | Design / ADRs, no cloud spend |
| 4 | Snowflake | ~$0 | XSMALL warehouse, auto-suspend 60s; `dbt build --target prod` run once, ~3s actual compute before erroring on missing Bronze schema (pre-ADR-005 issue, now moot) |
| 5 | AWS S3 | ~$0 (within Free Tier at this volume) | Bucket created, versioning + lifecycle + region-lock guardrails; full pipeline run landing→bronze→silver→gold parquet via DuckDB httpfs |
| 5 | Snowflake | ~$0 (a few cents) | `STORAGE INTEGRATION` + new scoped `snowflake_gold_reader` role + `gold_stage` + 2 external tables (`obt_sales_wide_ext` 16,848 rows, `obt_review_wide_ext` 215,063 rows) reading S3 Gold directly — XSMALL warehouse, auto-suspend, trial credits cover this trivially |
| 5 | MWAA | $0 | Not stood up — orchestration still on local `aws-mwaa-local-runner` |

## Current Status (as of 2026-06-19, post-migration)
- **Total spent**: effectively **$0** in real dollars — all usage this session falls inside AWS Free
  Tier (S3 at ~1GB total across landing+bronze+silver+gold parquet) and Snowflake trial credit
  (XSMALL warehouse, seconds of compute, auto-suspend).
- **Standing line items going forward** (steady-state, not one-off):
  - **S3 storage** — ~<$1/month at current low-GB volume (landing+bronze+silver+gold parquet,
    versioned with 30-day noncurrent-version expiry). This is the one cost that is genuinely
    always-on now; everything else in the stack is ephemeral or not provisioned.
  - **Cross-region egress watch** — mechanically prevented by the bucket's `aws:RequestedRegion`
    Deny policy (region-locked to `ap-southeast-1`, matching compute region), so this is a
    structural $0, not a discipline item to monitor manually.
  - **Snowflake external-table reads** — trivial trial-credit burn (XSMALL, auto-suspend); no
    dbt-written tables in Snowflake anymore under ADR-005 (read-only veneer over S3 Gold only).
  - **MWAA** — still $0; remains a short-window spike-and-teardown item if/when it is ever stood up.
- **Days remaining (Snowflake trial pace)**: effectively unconstrained at this burn rate — trial
  credit consumption is negligible (cents, not dollars) per session.

## Cost-Saving Actions Taken
- Region-locked the S3 bucket (`aws:RequestedRegion` Deny) so cross-region egress is structurally
  impossible, not just discouraged — removes the single largest latent S3 cost risk by design.
- Kept MWAA out of scope this round (ADR-005 build-decisions ruling) — orchestration stays on the
  $0 local `aws-mwaa-local-runner` until there's a concrete reason to spike MWAA.
- Snowflake demoted to a read-only external-table serving veneer (ADR-005) — no dbt-written tables,
  no Bronze/Silver compute in Snowflake, no need for a bigger warehouse; XSMALL + auto-suspend 60s
  is sufficient for the BI-demo read pattern.
- 30-day noncurrent-version lifecycle policy on the S3 bucket caps storage growth from versioning
  rather than letting old object versions accumulate indefinitely.
- New `snowflake_gold_reader` role scoped to `gold/*` only (ADR-004 least-privilege carried forward
  into ADR-005) — avoids over-provisioning broader Snowflake access than the read pattern needs.

## Cost Risks Flagged
- **S3 storage growth over time** — currently ~1GB and trivial, but landing/bronze/silver/gold all
  retain historical run data; if run frequency increases significantly (e.g., daily production
  cadence vs. this lab's occasional manual runs), revisit the lifecycle policy and consider
  Glacier/Intelligent-Tiering for older `gold/<run_id>/` snapshots that are superseded by
  `gold/_current/`.
- **MWAA stand-up** — when it eventually happens, budget ~$3–5 for a disciplined spike-and-teardown
  window (this is the one place the old "short-window teardown" premise still correctly applies).
- **Snowflake trial expiry** — trial credit window is 30 days from provisioning; if the trial lapses
  before this project wraps, the external-table veneer demo would need re-provisioning (cheap, but
  not instant) — not currently a blocker, just a date to watch.
