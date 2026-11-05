# Compaction prompt, regimes, thresholds

## The compaction prompt (harness-ready)

This is the message the harness injects when a reset is due. The model is expected to stop calling tools and answer with the brief only. `scripts/sac_harness.py` imports it from here by reading the block between the markers, so keep the markers.

<!-- COMPACTION_PROMPT_START -->
Stop. Do not call any tools in this reply.

This conversation is about to be discarded. A fresh instance of you will continue the task with only the system prompt, the original task, and the brief you write now. Write that brief. It is not a summary of what happened; it is a description of what is true and what to do next.

Use exactly these six sections, in this order, with these headings:

## 1. Objective
One line: what "done" means.

## 2. Established facts
Two lists. "Verified" — things you observed directly, each with its exact location (file path and line, command, URL) and the observation that proves it. "Hypotheses" — things you believe but have not confirmed, each with the exact check that would confirm it. Never put a hypothesis in the verified list.

## 3. Changes applied
One row per change: file, one-line description, status (verified / unverified / reverted), and the command or observation that verified it.

## 4. Checks run
The exact commands you ran that still matter, each with its exit code or key output line.

## 5. Dead ends
Approaches you tried and abandoned, each with the reason, so the next instance does not repeat them.

## 6. Remaining plan
Steps in execution order. Step 1 is the exact next command to run and what output to expect.

Rules: be exact — file paths, symbols, commands, observed outputs, not paraphrases. Include nothing re-fetchable from disk (cite the path and line instead of quoting content). Include no narrative, no repeated error traces, no hypotheses you have already ruled out (those are dead ends, one line each). Everything the next instance needs to continue without repeating work must be here; everything else must not.
<!-- COMPACTION_PROMPT_END -->

## `/compact` instruction text (Claude Code)

Paste after `/compact` so the built-in summarizer produces a brief instead of a narrative:

```
/compact Produce a handoff brief for a fresh session, not a narrative. Exactly six sections: 1. Objective (one line); 2. Established facts, split into Verified (with exact path:line and the observation that proves each) and Hypotheses (each with the check that confirms it); 3. Changes applied (file, change, status verified/unverified/reverted, verified by); 4. Checks run (exact commands and key output); 5. Dead ends (what was tried and why it failed); 6. Remaining plan in execution order starting with the exact next command. Omit narrative, repeated error traces, and anything re-fetchable from disk.
```

If `.claude/handoff.md` is current, the `SessionStart` hook re-injects it anyway, so the summarizer's output only needs to be non-conflicting. If the file is stale, say so in the first message after compaction and rewrite it.

## Regimes

| Regime | Trigger | Fresh context after reset | Use when |
|---|---|---|---|
| FHA (full-history accumulation) | never | — | baseline; short tasks that finish under the threshold anyway |
| EoCC (end-of-conversation compaction) | live context crosses the threshold | system prompt + task + brief | default; long tasks on any harness |
| SAC (single-action compaction) | after every action/observation | system prompt + task + brief | peak-memory-bound serving; experiments on state-as-text |

Written `limit/threshold`, e.g. `24K/18K`: the model is given a 24K context ceiling and the harness triggers compaction when the live conversation crosses 18K. The gap (6K) is the budget for the brief itself plus one more action.

In EoCC the live context after a reset is small, so most tasks hit the threshold zero or one times. The paper's uncompacted baselines already had median lengths of 7–32K tokens; the regime mostly matters for the long tail (max lengths of 130–200K).

## Thresholds

| Setting | Who | Evidence |
|---|---|---|
| 48K/36K or 32K/24K | any model | within noise of full-history on all six long-horizon benchmarks |
| 24K/18K | frontier models | SWE-bench Verified: Opus 4.5 70.0 → 74.8 (pruning stale traces helps) |
| 16K/12K | strong, terse models only | Opus-class flat; GPT-class −2 to −3 ppts; several open-weight models collapsed (one from 53.0% to 3.6%) because verbose traces ate the 12K budget before any progress |
| 8K/6K | tool-use benchmarks with tiny actions (τ²-bench) | flat |

Rule of thumb: the threshold must leave room for (median tool observation) + (the brief) + (one reasoning turn). If the model's traces are long, raise the threshold or shorten the tool-output cap before concluding compaction hurts.

## What compaction cannot fix

- **Exact recall of arbitrary history.** If the task may later need the i-th outcome of a sequence, log every conversation to disk (`--log` in the reference harness does this) and treat the log as a document to be read selectively.
- **Multi-document synthesis.** Tasks that need evidence from many sources at once (FRAMES) lose 1–4 ppts under compaction at every threshold. Externalize the evidence to a notes file as it is found.
- **Prompt-cache economics.** Each reset discards the cached prefix; nominal API cost usually goes up (the paper: SWE-bench Verified $168 → $203, Terminal-Bench 2.1 $49 → $61 for GPT 5.6 Sol at 16K/12K). The savings are in decode throughput and memory on your own hardware.

## Cost model used in the paper (for your own estimates)

Output-token cost ratio at 16K vs 256K, from inverse peak decode throughput on H100: r ≈ 0.20 (3.6x–7x across GLM 5.2, Kimi K2.6, Qwen 3 Coder Next). Estimated output price at context limit W:

```
C_out(W) = C_out(W_max) * [ r + (1 - r) * (max(W, 16K) - 16K) / (W_max - 16K) ]
```

Input and cached-input prices follow at the standard 5:1 and 10:1 ratios. The paper's "2.2x–233x" savings are this estimate (EORC) applied to a run's token totals under hypothetical context-tiered pricing — not a commercial bill.
