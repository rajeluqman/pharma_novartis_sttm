# <Performance Issue Name>
> Example: spark_shuffle_bottleneck.md

═══════════════════════════════════════════════════════════
SECTION 1: SYMPTOM DETECTION
═══════════════════════════════════════════════════════════

Symptoms observed:
  □ <Observable thing 1>
  □ <Observable thing 2>
  □ <Observable thing 3>

Where to look:
  □ <UI path or command>
  □ <Alternative diagnostic location>

═══════════════════════════════════════════════════════════
SECTION 2: ROOT CAUSE INVESTIGATION (Step-by-Step)
═══════════════════════════════════════════════════════════

STEP 1: <First action>
  → <Command or UI step>
  → Note: <what to capture>

STEP 2: <Branching diagnostic>
  → IF condition A → Path A
  → IF condition B → Path B
  → IF condition C → Path C

STEP 3 (Path A): <If skew detected>
  → <Specific commands>
  → <Decision criteria>

STEP 3 (Path B): <If partition count wrong>
  → <Specific commands>

STEP 3 (Path C): <Other root cause>
  → <Specific commands>

═══════════════════════════════════════════════════════════
SECTION 3: SOLUTION OPTIONS + TRADE-OFFS
═══════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────┐
│ OPTION 1: <Solution name>                              │
├─────────────────────────────────────────────────────────┤
│ WHAT  : <code>                                         │
│ WHY   : <mechanism explanation>                        │
│ WHEN  : <use case fit>                                 │
│ TRADE-OFF                                              │
│   (+) <benefit>                                        │
│   (-) <cost or risk>                                   │
│                                                         │
│ STAKEHOLDER IMPACT                                     │
│   Senior Data Engineer : APPROVED/⚠️/REJECTED        │
│   FinOps review         : <cost impact>                │
│   Data Architect       : <governance check>           │
│   Scope Guardian       : <scope check>                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ OPTION 2: <Alternative>                                │
├─────────────────────────────────────────────────────────┤
│ ... (same structure)                                   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ OPTION 3: <Advanced/Last resort>                       │
├─────────────────────────────────────────────────────────┤
│ ... (same structure)                                   │
└─────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════
SECTION 4: DECISION TEMPLATE
═══════════════════════════════════════════════════════════

Project: <project_name>
Issue: <one-line summary>
Investigation: <which Path A/B/C>
Options considered: 1, 2, 3
Chosen: Option <N>
Justification: <2-3 sentence why>
Approved by: Senior Data Engineer, Data Architect, FinOps review
Before metrics:
  - <metric 1>: <value>
  - <metric 2>: <value>
After metrics:
  - <metric 1>: <value> (X% improvement)
  - <metric 2>: <value> (Y% improvement)
ADR link: docs/ADR/00X-<topic>.md

═══════════════════════════════════════════════════════════
RELATED CHEATSHEETS
═══════════════════════════════════════════════════════════
- <related_topic_1>.md
- <related_topic_2>.md
