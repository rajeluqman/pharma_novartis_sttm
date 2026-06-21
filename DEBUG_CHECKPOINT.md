# Debug Checkpoint — <issue title>

> Working memory untuk troubleshooting. WAJIB baca file ni SEBELUM re-scan codebase.
> WAJIB update sebelum tamat setiap debugging turn. Gitignored.

## Active Issue
- **Symptom**: <what's broken, observable behaviour>
- **Error (verbatim)**: `<paste exact error message>`
- **First seen**: <date/phase>
- **Reproduce steps**: <command/notebook cell that triggers it>

## Hypotheses
| # | Hypothesis | Status | Evidence |
|---|-----------|--------|----------|
| 1 | <e.g. schema mismatch on order_id> | open / ruled-out / confirmed | <what was checked> |

## Confirmed Clean — JANGAN re-read
| File / component | Verified how | Date |
|------------------|--------------|------|
| <e.g. bronze/ingest_to_delta.py> | <ran + row count match DRD> | <date> |

## Files In Scope (baca ini SAHAJA)
- <file 1>
- <file 2>

## Next Step
<one line — exact next action when resuming>

---
*Bila issue resolved: pindahkan root cause + fix ke TROUBLESHOOTING.md, lepas tu kosongkan file ni.*
