#!/usr/bin/env python3
"""Claude Code SessionStart hook: re-inject the handoff brief after compaction or /clear.

Reads the hook's JSON input on stdin, looks for the brief at
$COMPACTION_BRIEF_PATH or <cwd>/.claude/handoff.md, and, if it exists and is
fresh, prints a SessionStart JSON output whose additionalContext carries the
brief. Prints nothing (exit 0) when there is nothing to inject, so the hook is
a no-op in sessions that never used the protocol.

Environment:
  COMPACTION_BRIEF_PATH           brief location (default <cwd>/.claude/handoff.md)
  COMPACTION_BRIEF_MAX_AGE_HOURS  skip briefs older than this; 0 disables (default 72)

Register under SessionStart with matcher "compact|clear" (see references/claude-code-setup.md).
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

MAX_INJECT_CHARS = 9500  # hooks cap additionalContext at 10,000 chars


def main():
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    path = os.environ.get("COMPACTION_BRIEF_PATH") or os.path.join(cwd, ".claude", "handoff.md")
    if not os.path.isfile(path):
        return 0

    try:
        max_age_h = float(os.environ.get("COMPACTION_BRIEF_MAX_AGE_HOURS", "72"))
    except ValueError:
        max_age_h = 72.0
    mtime = os.path.getmtime(path)
    age_h = (time.time() - mtime) / 3600.0
    if max_age_h > 0 and age_h > max_age_h:
        return 0

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            brief = fh.read().strip()
    except OSError:
        return 0
    if not brief:
        return 0

    truncated = False
    if len(brief) > MAX_INJECT_CHARS:
        brief = brief[:MAX_INJECT_CHARS]
        truncated = True

    updated = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    source = payload.get("source", "unknown")
    header = (
        f"The file {path} holds the handoff brief written before the last "
        f"context reset (session start source: {source}; file updated {updated}, "
        f"{age_h:.1f} h ago). It describes the current state of the task: verified "
        f"facts are true, hypotheses still need their check, dead ends are not to be "
        f"repeated, and the remaining plan starts at step 1. The brief follows."
    )
    if truncated:
        header += (f" Only the first {MAX_INJECT_CHARS} characters are included; "
                   f"the full brief is in the file.")

    out = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": header + "\n\n" + brief,
        }
    }
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
