#!/usr/bin/env python3
"""Claude Code PreCompact hook: copy the full transcript to disk before it is condensed.

The paper's point: compaction is lossy, so exact recall of arbitrary history
needs the full log on disk, read selectively. This hook copies transcript_path
to <cwd>/.claude/transcripts/<UTC timestamp>-<trigger>.jsonl (override the
directory with $COMPACTION_TRANSCRIPT_DIR). It never blocks compaction and
prints nothing.
"""
import json
import os
import shutil
import sys
from datetime import datetime, timezone


def main():
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return 0
    src = payload.get("transcript_path")
    if not src or not os.path.isfile(src):
        return 0
    cwd = payload.get("cwd") or os.getcwd()
    out_dir = os.environ.get("COMPACTION_TRANSCRIPT_DIR") or os.path.join(cwd, ".claude", "transcripts")
    try:
        os.makedirs(out_dir, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        trigger = payload.get("trigger", "compact")
        shutil.copyfile(src, os.path.join(out_dir, f"{stamp}-{trigger}.jsonl"))
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
