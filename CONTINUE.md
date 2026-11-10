# CONTINUE.md — read this first when an agent picks up this fork

## Context

This is a fork of che-shr-cat/short-context-agent (open reproduction of
"You Don't Need Long Context", arXiv:2611.05306) with an `evals/` scaffold
already added on branch `evals-scaffold` and submitted upstream as PR #1.
Read upstream README.md, our evals/README.md and the PR conversation first.

## Working rules

- Stay compatible with the upstream design: the harness (`sac_harness.py`)
  is theirs; we extend around it, not over it.
- `python3 evals/run_evals.py` (dry-run) must always work with zero
  dependencies and no API key — it's the plumbing smoke test.
- Real runs need the anthropic SDK + ANTHROPIC_API_KEY and execute shell
  commands in workdirs: document that clearly in every result you commit.
- Honest claims: dry-run accuracy 0 by design; never present dry-run output
  as a benchmark result. Real numbers only with the exact command recorded.
- Commits in English, conventional-commit style.
- Upstream PR etiquette: small focused commits, reference the roadmap item
  each change fulfills, no drive-by refactors of their code.

## Models — Z.ai Coding Plan (mandatory)

Real harness runs (`--real`) go through the Z.ai Coding Plan subscription —
the plan exposes an Anthropic-compatible endpoint, so the anthropic-SDK
harness works without code changes:

```bash
export ANTHROPIC_BASE_URL="https://api.z.ai/api/anthropic"
export ANTHROPIC_AUTH_TOKEN="<Z.ai Coding Plan key>"
export ANTHROPIC_MODEL="glm-5.3-flash"   # Z.ai model through the compat layer
```

First verify `sac_harness.py` actually reads ANTHROPIC_BASE_URL — if it only
reads ANTHROPIC_API_KEY, add base-URL support via env (small upstream-friendly
patch, note it in the PR). Flat subscription billing: if a billing/endpoint
error appears, stop and report — do NOT switch providers.

## Current task (do this now)

The previous handoff's task is DONE (tasks + template + real run committed;
see `evals/results/` and the git log). Verified along the way: the anthropic
SDK picks up ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN natively, so the harness
needed no patch; `run_evals.py` now copies `fixtures/<id>/fixtures/` into the
workdir itself (the old `cp -r fixtures/* .` setup lines never worked — the
copy step was documented but unimplemented, masked by dry-run) and takes peak
live context from the harness's stdout summary instead of a log field that
never existed.

Nothing queued for this fork right now. Pick up the upstream roadmap instead
(below), or improve the suite: more tasks, tighter token accounting, a second
model for comparison (a results/ entry per model is the format).

## After that

Follow upstream's roadmap: benchmark runs on the real suites the paper used
where feasible (they list SWE-bench Verified, Terminal-Bench 2.1, LongBench
v2, RULER), plus their "Contributions welcome" SSMM experiment idea.
