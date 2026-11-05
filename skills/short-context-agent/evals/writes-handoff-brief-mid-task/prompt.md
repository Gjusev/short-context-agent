---
tags: [short-context-agent]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

One test in tests/test_parse.py started failing after the timezone refactor (commit 4f2c1a9). Investigate and fix the parser, not the tests. We are going to compact this session right after your first fix attempt, so before you run the full test suite, write a handoff brief to .claude/handoff.md that a fresh session could continue from. Then run the full suite and update the brief with the result.

Input files: app/, tests/, CHANGELOG.md, README.md
