#!/usr/bin/env python3
"""FinOps Bash cost-guard (PreToolUse hook on Bash).

Soft-vetoes Bash commands that provision or run against LIVE cloud (AWS/Snowflake)
— mirrors CLAUDE.md's "Provisioning ... stays OWNER-GATED" rule and the
@finops-agent persona's "Block actions that exceed budget" job. Never hard-denies
(a soft veto can always be overruled by @data-architect) — forces an explicit
"ask" confirmation instead of silently proceeding.

Always exits 0: silent when no match, otherwise emits an "ask" permissionDecision.
"""
import sys, json, re

SCRIPT_PATTERNS = [
    r"\bprovision_s3\.sh\b",
    r"\bprovision_snowflake_iam\.sh\b",
    r"\bprovision_snowflake_veneer\.(py|sql)\b",
    r"\brun_pipeline_aws\.sh\b",
    r"\bsetup_snowflake\.sql\b",
]
CLI_PATTERNS = [
    r"\baws\s+s3\s+mb\b",
    r"\baws\s+cloudformation\b",
    r"\baws\s+mwaa\s+create-environment\b",
    r"\baws\s+iam\s+create-role\b",
    r"\bterraform\s+apply\b",
    r"\bCREATE\s+WAREHOUSE\b",
    r"\bCREATE\s+ROLE\b",
    r"\bALTER\s+WAREHOUSE\b",
]
PATTERN = re.compile("|".join(SCRIPT_PATTERNS + CLI_PATTERNS), re.IGNORECASE)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return  # no payload -> stay silent

    cmd = (data.get("tool_input") or {}).get("command", "")
    if not cmd or not PATTERN.search(cmd):
        return  # nothing cost-sensitive matched -> allow silently

    reason = (
        "\U0001F6D1 BUDGET ALERT [@finops-agent]: this command provisions or runs "
        "against LIVE cloud (AWS/Snowflake) — real spend, not the MinIO gym. "
        "CLAUDE.md: provisioning stays OWNER-GATED. Confirm this is intended before "
        "proceeding. Soft veto — @data-architect can overrule if long-term TCO "
        "is justified."
    )
    print(json.dumps({
        "systemMessage": reason,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        },
    }))


if __name__ == "__main__":
    main()
    sys.exit(0)
