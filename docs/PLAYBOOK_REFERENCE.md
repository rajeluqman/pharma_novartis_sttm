# DE Cabinet Gym — Playbook

> Reference dokumen untuk semua agents. Referenced dalam STARTER_PROMPT.md.

## Mission

Domain-agnostic practice framework untuk Data Engineering. Bina pipeline dari
0 sampai siap, dengan 17 AI agents sebagai cross-functional cabinet, untuk
build muscle memory tackle ambiguity.

## Core Principles

1. **Stack boundary = HARD LIMIT** — only tools dalam resume
2. **Grain = HARD BLOCKER** — Phase 3 tak boleh sign off kalau grain belum defined
3. **Veto = STOP** — bila DA atau Scope Guardian veto, semua pause
4. **3-round debate max** — beyond that, escalate to human
5. **Always reference docs** — agents WAJIB baca docs/ sebelum respond
6. **No co-author commits** — Claude tak appear in git contributors
7. **Performance senior-level** — min 5 of 6 categories per project
8. **Sprint mode default** — 1 day per problem

## 7-Document Framework + 2 Data Modeling Docs

| Phase | Doc | Question Answered |
|-------|-----|-------------------|
| 1 | BRD.md | Business nak apa? |
| 2 | DRD.md | Source mana? Schema? Frequency? |
| 2 | DATA_DICTIONARY.md | Column definitions, business terms |
| 3 | ARCHITECTURE.md | Tool mana? Layer mana? Kenapa? |
| 3 | PIPELINE_SPEC.md | Transform logic macam mana? |
| 3 | DATA_MODEL.md | Paradigm? Grain? SCD? Trade-off? |
| 4 | CODE | Implementation |
| 5 | DQD.md | Data betul ke? |
| 5 | OPS_RUNBOOK.md | Fail 3am — buat apa? |

**Order matters** — BRD → DRD → ARCH → SPEC → CODE → DQD → OPS.
Jangan skip ke CODE without BRD + DRD.

## Internal Docs (gitignored)

- DEBATE_LOG_phase_N.md — cabinet meeting transcript
- JOURNEY_LOG.md — decisions + learning chronological
- COST_LOG.md — token + cloud spend
- PROJECT_STATUS.md — current progress
- SIGN_OFF_LOG.md — phase gate sign-offs
- LEARNING_LOG.md — Cikgu's notes (Q&A per session)
- HINT_LOG.md — score deductions tracking
- DECISION_LOG.md — granular decisions
- DOCS_CONSULTED.md — official doc index
- INFRA_LIMITS_LOG.md — trial constraints hit
- BLOCKER_LOG.md — blockers + resolution time
- DEBUG_CHECKPOINT.md — active debugging working memory (hypotheses, confirmed-clean files)
- INTERVIEW_GUIDE.md — generated at end

## Phase Flow

```
Phase 1: DISCOVERY (Cabinet Meeting)
  @product-owner opens
  @business-analyst probes acceptance criteria
  @finops-agent checks budget
  @infra-reality-agent checks trial constraints
  @senior-data-engineer effort estimate
  @data-architect proposes architecture
  @scope-guardian locks scope
  @project-manager sign-off
  Output: BRD.md + DRD.md (Section 1) + DEBATE_LOG_phase_1.md

Phase 2: EXPLORATION
  @data-engineer writes exploration script
  @data-quality-steward builds DATA_DICTIONARY.md
  @business-analyst validates business attributes mapped
  @data-architect proposes Conceptual Data Model
  @project-manager sign-off (Phase 2 → 3 gate)
  Output: DRD.md complete + DATA_DICTIONARY.md + DEBATE_LOG_phase_2.md

Phase 3: DESIGN
  @data-architect writes DATA_MODEL.md (Logical)
  @data-architect + @senior-data-engineer write ARCHITECTURE.md
  @senior-data-engineer writes PIPELINE_SPEC.md
  ADRs created in docs/ADR/
  @finops-agent reviews cost
  @scope-guardian final scope check
  @project-manager sign-off (Phase 3 → 4 gate)
  Output: DATA_MODEL.md + ARCHITECTURE.md + PIPELINE_SPEC.md + ADRs

Phase 4: BUILD (user + @cikgu)
  Score starts 100, hint = -5
  @cikgu enforces methodology (diagnostic before solution)
  @data-engineer + @analytics-engineer execute spec
  @senior-data-engineer auto-logs performance
  @cheatsheet-generator auto-generates cheatsheets
  Output: code (bronze/silver/gold) + cheatsheets/

Phase 5: QUALITY + DOCS
  @qa-engineer runs tests
  @data-quality-steward validates DQ suites
  @cikgu generates resume bullet drafts
  @business-analyst honesty check on resume claims
  README.md generated (business Q&A format)
  @project-manager final sign-off
  Output: README.md + DQD.md + OPS_RUNBOOK.md + INTERVIEW_GUIDE.md
```

## Veto Protocol

When @data-architect or @scope-guardian raises VETO:
1. STOP all execution
2. Document veto in DECISION_LOG.md + DEBATE_LOG_phase_N.md
3. Emergency meeting: PM + Senior DE + Veto-raiser + affected agent
4. Resolve OR pivot
5. SIGN_OFF_LOG.md updated

## Score System

- Start: 100/100
- Hint requested: -5
- Mistake user makes despite docs: -3
- Score thresholds:
  - **<60**: Cikgu force docs reading break
  - **<40**: Remedial cheatsheet review
  - **=0**: Auto-trigger @senior-data-engineer pair-programming

## Performance Coverage (Senior-Level)

Each project MUST hit minimum **5 of 6 categories**:

1. **QUERY_PERFORMANCE** — SQL execution, EXPLAIN, cache
2. **SPARK_EXECUTION** — stage duration, shuffle, skew, OOM
3. **STORAGE_LAYOUT** — partition pruning, Z-Order, small files
4. **PIPELINE_THROUGHPUT** — DAG duration, parallelism, bottlenecks
5. **DBT_PERFORMANCE** — model timing, incremental, threads
6. **RESOURCE_UTILIZATION** — CPU/memory, autoscale, cost

Auto-extracted by @senior-data-engineer dari job output (Spark UI,
Snowflake QUERY_HISTORY, dbt --debug).

## Anti-Hallucination Rules

1. WAJIB reference docs/ before respond
2. Don't assume columns not in DRD.md
3. Don't suggest tools not in stack (CLAUDE.md)
4. Max 3 rounds debate → escalate human
5. Scope Guardian VETO → everyone STOPS
6. DA must sync with DPE before paradigm presented
7. AE must read DATA_MODEL.md before build
8. Don't assume grain/SCD/paradigm settled if not in DATA_MODEL.md
9. Databricks trial = SQL warehouse only (no PySpark cluster)

## Token Efficiency Protocol

Punca burn token: setiap agent spawn start cold dan re-read context; debugging
re-scan files yang sama; cache mati bila gap >5 minit.

1. **Checkpoint-first** — semua agents baca `PROJECT_STATUS.md` /
   `DEBUG_CHECKPOINT.md` / `LEARNING_LOG.md` SEBELUM baca code.
   Checkpoint dah jawab = JANGAN scan codebase.
2. **Module scope** — baca hanya files module semasa, max ~3 files per turn.
3. **DEBUG_CHECKPOINT.md** — masa debug, rekod hypothesis ruled-out +
   "Confirmed Clean" files setiap turn. Turn seterusnya baca checkpoint
   (ratusan token), bukan re-scan codebase (puluhan ribu).
4. **Explore subagent untuk search** — "kat mana X defined?" → spawn Explore
   (return kesimpulan), jangan banjirkan main thread dengan file dumps.
5. **Subagent hanya bila perlu** — kerja yang main thread boleh buat sendiri,
   buat sendiri. Subagent untuk kerja parallel atau kerja yang akan banjirkan
   context.
6. **Sesi cikgu = main session** — jangan spawn `@cikgu` berulang untuk sesi
   mengajar panjang. Satu blok mengajar (45-60 min) = satu module.
7. **Cache discipline** — prompt cache TTL 5 minit. Sesi fokus berterusan
   lebih murah dari banyak sesi pendek yang start cold. Bila balik dari gap
   panjang, baca checkpoint dulu.

## Cheatsheet Strategy

**Two types**:
1. **Function reference** — table format (like PySpark cheatsheet)
2. **Performance diagnostic** — 4-section format (symptom → investigation → options → decision)

**Generation timing (Hybrid)**:
- **Pre-build**: At Phase 1 end, generate high-level reference for concepts in scope
- **Just-in-time**: When hint triggered or performance issue logged

**Storage**:
- `cheatsheets/functions/` — syntax reference
- `cheatsheets/performance/` — diagnostic guides

## Token Budget per Project

Sprint mode (1 day):
- Opus (1 agent — @data-architect, veto moments): ~$2-3
- Sonnet (12 agents, strategic + cikgu + @scope-guardian): ~$8-12
- Haiku (4 agents, executors): ~$1-2
- **Total: ~$11-17/project**

Compared to all-Sonnet (~$25-30): **~50% cost saving**
Dengan Token Efficiency Protocol (checkpoint-first, module scope): jangka
20-40% tambahan saving pada debugging-heavy phases.

## Documentation Order

Strict sequence — don't skip:
1. BRD (30 min)
2. DRD (1-2 hr)
3. ARCHITECTURE (1 hr)
4. PIPELINE_SPEC (2-3 hr)
5. CODE (majority of time)
6. DQD (1 hr — after pattern emerges)
7. OPS_RUNBOOK (1-2 hr — after pipeline running)

## What Makes a Senior-Level DE (this framework's target)

Junior DE: Fixes obvious bottleneck when complaint comes
Mid DE: Optimizes after MVP works
**Senior DE (target)**: Designs with performance in mind from Day 1.
Articulates trade-offs: "Picked broadcast over shuffle because right side
8MB < 10MB threshold; saves 4s." Without that sentence = mid level.

## Track B — SLA Troubleshooting Gym (v1)

Track A (Phases 1–5) BUILDS a pipeline. Track B TROUBLESHOOTS it — the real "ensure the
7AM SLA" muscle. Run it after a working pipeline exists. Starter: `prompts/SLA_GYM_PROMPT.md`.

**Roles**
- USER builds + fixes the DAGs (hands on keyboard).
- @cikgu teaches the diagnostic METHOD (critical path, Gantt, logs); minimal hints, −5 each.
- @bottleneck-saboteur injects ONE realistic flaw; logs the SYMPTOM only, root cause `[SEALED]`.
- @senior-data-engineer reviews the DAG before sabotage.

**The Ladder** — `templates/curriculum/DAG_LADDER_TEMPLATE.md` (L1→L10). Build a DAG, then
break it; each level unlocks a harder sabotage.

**One round**
1. @cikgu teaches the level concept (WHY before HOW; DIY Build Mode).
2. USER builds `airflow/dags/<dag>.py`; @senior-de reviews.
3. @bottleneck-saboteur injects a flaw → `docs/sla/SABOTAGE_LOG.md` (OPEN, sealed cause).
4. USER + @cikgu diagnose: critical path → isolate ONE root cause.
5. USER fixes; saboteur verifies → SOLVED, reveals cause.
6. USER records before/after runtime in `docs/sla/SLA_ANALYSIS.md`.

**Rules**: deadline is a hard clock (run starts 03:00, must finish < 07:00); measure
everything (a number, not "feels faster"); one root cause per round until L8+ compound;
saboteur never touches truth artifacts (AH, STTM, ERD).

## Lead Deliverables (v1)
For enVision-style "Architecture / STTM Lead" responsibilities, v1 adds templates in
`templates/docs/`: **Architecture Handbook** (AH), **STTM**, **Erwin ERD** (dbdiagram.io
clone). Plus a practical skills cheatsheet: `templates/cheatsheets/DE_SKILLS_DICTIONARY.md`.

---

*Domain-agnostic. Dataset berubah, framework sama. v1 — Last updated: 2026-06-18.*
*v1 adds: @bottleneck-saboteur, DAG Ladder + SLA track, AH/STTM/Erwin templates,
DE Skills Dictionary, upgraded @cikgu teaching methods, sample-novartis-sttm.*
