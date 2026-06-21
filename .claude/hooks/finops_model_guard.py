#!/usr/bin/env python3
"""FinOps model-guard (UserPromptSubmit hook).

Reads the CURRENT session's own transcript (path supplied on stdin by Claude
Code), tallies output-token burn + the model in use, and — if the session is
on Opus AND past the threshold — emits a budget warning. @finops-agent soft veto.

Output:
  systemMessage     -> shown to the user in the UI (the visible nudge)
  additionalContext -> injected into the session's own context (self-reminder)

Always exits 0: this is a nudge, never a block.
"""
import sys, json, os

OPUS_OUTPUT_TOK_THRESHOLD = 40_000  # cumulative Opus output tokens before we warn

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return  # no payload -> stay silent

    tp = data.get("transcript_path")
    if not tp or not os.path.exists(tp):
        return

    model = None
    out_tok = 0
    try:
        with open(tp) as f:
            for line in f:
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                m = o.get("message", {})
                if m.get("model"):
                    model = m["model"]          # last model wins = current model
                u = m.get("usage") or {}
                out_tok += u.get("output_tokens", 0)
    except Exception:
        return

    if not model or "opus" not in model.lower():
        return  # already on a cheaper tier -> nothing to flag
    if out_tok < OPUS_OUTPUT_TOK_THRESHOLD:
        return  # burn still small -> don't nag

    warn = (
        f"\U0001F6D1 FinOps guard [@finops-agent]: this session is on {model} "
        f"and has burned {out_tok:,} output tokens. Opus output costs ~5x Sonnet "
        f"/ ~15x Haiku. If this isn't live architecture/design reasoning, switch "
        f"with  /model sonnet  (or  /model haiku  for simple listing/exec work)."
    )
    print(json.dumps({
        "systemMessage": warn,
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": warn,
        },
    }))

if __name__ == "__main__":
    main()
    sys.exit(0)
