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

## Current task (do this now)

Fill the evals the upstream roadmap asks for ("Contributions welcome,
especially benchmark runs"):

1. Add 2-3 more deterministic tasks to `evals/tasks/` — at least one
   long-input task where the answer sits in a file the agent must grep for
   (selective reading / LCW2 regime) and one multi-step task where the
   handoff brief must carry state between compacted conversations.
2. Add `evals/results/` with a README template: suite version, model, regime,
   accuracy, peak live context, raw command. No fabricated entries.
3. If ANTHROPIC_API_KEY is present, run all tasks x regimes for real and
   commit results. Otherwise stop after the tasks + template.
4. Push to `evals-scaffold` — the open PR picks it up automatically.

## After that

Follow upstream's roadmap: benchmark runs on the real suites the paper used
where feasible (they list SWE-bench Verified, Terminal-Bench 2.1, LongBench
v2, RULER), plus their "Contributions welcome" SSMM experiment idea.
