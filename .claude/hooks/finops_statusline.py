#!/usr/bin/env python3
"""FinOps status line — always-on model + token-burn indicator.

Claude Code passes session context as JSON on stdin. We render one line:
  green  : cheaper tier, or Opus still under threshold
  red 🛑 : Opus AND output-token burn past the same 40k threshold the hook uses

Shares the threshold with finops_model_guard.py so the badge flips at the same
point the prompt-submit warning fires.
"""
import sys, json, os

OPUS_OUTPUT_TOK_THRESHOLD = 40_000

GREEN = "\033[32m"; YELLOW = "\033[33m"; RED = "\033[31m"; DIM = "\033[2m"; RESET = "\033[0m"

def human(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.0f}K"
    return str(n)

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    model_obj = data.get("model") or {}
    model_name = model_obj.get("display_name") or model_obj.get("id") or "?"
    model_id = (model_obj.get("id") or model_name or "").lower()
    is_opus = "opus" in model_id

    tp = data.get("transcript_path")
    out_tok = 0
    if tp and os.path.exists(tp):
        try:
            with open(tp) as f:
                for line in f:
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    u = (o.get("message", {}) or {}).get("usage") or {}
                    out_tok += u.get("output_tokens", 0)
        except Exception:
            pass

    burn = f"out {human(out_tok)} tok"
    if is_opus and out_tok >= OPUS_OUTPUT_TOK_THRESHOLD:
        print(f"{RED}🛑 {model_name} | {burn} | /model sonnet?{RESET}")
    elif is_opus:
        print(f"{YELLOW}💸 {model_name} | {burn}{RESET}")
    else:
        print(f"{GREEN}✓ {model_name} | {burn}{RESET}")

if __name__ == "__main__":
    main()
