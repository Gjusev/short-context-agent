---
name: short-context-agent
description: Keep agentic work inside a short context window using the NVIDIA "You don't need long context" recipe (arXiv:2611.05306) — forward-looking handoff briefs instead of generic summaries, End-of-Conversation / Single-Action compaction, and selective reading of large inputs with grep + bounded windows instead of pasting whole files into the prompt. Use this skill whenever a task is long-horizon (multi-step debugging, migrations, multi-file refactors, long investigations or research), whenever the user mentions context limits, compaction, /compact, handoff, checkpointing, "resume where we left off", "pick up from the last session", or "running out of context", and whenever an input is large (long documents, logs, transcripts, grammar books, codebases, anything over a few thousand lines). Also use it when building or tuning an agent harness that needs bounded context (EoCC/SAC loops, state briefs, doc-read tools, token-threshold resets).
---

# short-context-agent — compaction and selective reading protocol

This skill turns the paper's harness-level recipe into something you can run today. The paper's claim: an agent in a sequential loop never needs its whole past conversation, nor a whole document, in working memory. It needs (1) a compact, forward-looking description of where it stands and (2) a tool to fetch raw data on demand. Done right, accuracy holds flat or improves (stale exploration traces stop distracting the model), and peak context drops by an order of magnitude.

Three pieces, in order of how often you'll use them:

| Piece | Paper concept | What you do here |
|---|---|---|
| A. Selective reading | LCW2: long inputs → filesystem + `grep` + bounded `doc-read` windows | Never load a big file whole. Search, then read a window. |
| B. Handoff brief | EoCC / SAC compaction prompt (six-part execution brief) | Write `.claude/handoff.md` at milestones and before compaction. |
| C. Resume | Fresh conversation = system prompt + task + brief | Continue from the brief without re-deriving or re-trying dead ends. |

Context is a cache. State lives in text. If something matters past this turn, it has to be in a file or in the brief.

## A. Selective reading — never paste the document

Applies to any input that would cost more than ~2K tokens to load whole: documents, logs, transcripts, large source files, datasets.

1. Put the source on disk if it isn't already (write pasted content to a file; download URLs to a file).
2. Search before reading. Locate what you need with `grep -n -i -E 'pattern' FILE | head -20` (in Claude Code: the Grep tool). Search for the most specific token you have — a symbol, an error string, a rare word from the question — not a topic.
3. Read a bounded window around the hit: `scripts/doc-read --lines 3835:3870 FILE` (or `--around 3840:20`), or in Claude Code the Read tool with `offset`/`limit` (keep windows ≤ ~150 lines / ~6K chars). The tool hard-caps at 8,000 characters; if you hit the cap, narrow the range instead of widening it.
4. Record what you learned as a fact with its location (`FILE:3840 — kademor is 'to be mad'; applicative introduces an object`) before moving on. Facts with line numbers are re-fetchable; impressions are not.
5. Widen only when the window is insufficient — a second `--around` with more context, or `--grep` for a related term. Don't fall back to reading the whole file; if coverage is genuinely needed (e.g. counting every occurrence), use `grep -c`/`awk`/`wc`, which return counts, not text.
6. For multi-document synthesis (answers that need evidence from 5–15 sources), keep a running `notes.md` on disk with one line per piece of evidence and its source location. The paper shows this is the regime where compaction is lossy (FRAMES-style tasks lose 1–4 ppts), so externalize the evidence rather than holding it in context.

Why this works: the model's own attention is the weak link on long inputs ("lost in the middle"). Command-line search is exact. On needle benchmarks the paper's agents reach ~96% recall with zero compactions simply because `grep` found the needle before the context ever got long.

## B. The handoff brief — compaction as a forward-looking execution brief

Generic summaries fail because they weight all past events equally and dwell on error traces that no longer matter. The brief is different: it is written for a fresh instance of you that has the system prompt, the original task, and nothing else, and it tells that instance what is true and what to do next.

### When to write it

You cannot see your own token count, so checkpoint on events:

- After every verified milestone (a test passes, a file is confirmed written, a hypothesis is confirmed or killed).
- Before any step likely to produce large output (full test suites, log dumps, big diffs, document scans).
- Immediately when the user says checkpoint / handoff / compact / "save state", or runs `/compact`.
- Every ~8–10 tool calls on a long task even if nothing above fired.
- In a custom harness: automatically at the token threshold (EoCC) or after every action (SAC) — see `references/compaction-prompt.md`.

Overwrite the file each time; keep only the current state. History that still matters is either a fact, a dead end, or a plan item — there is no "narrative" section.

### Where

`.claude/handoff.md` in the project root (override with `$COMPACTION_BRIEF_PATH`). Add it to `.gitignore`. One brief per task; if you work on two tasks in one session, name them `.claude/handoff-<task>.md` and say so in the brief's header.

### Format

Six sections, always in this order. Full template with a worked example in `references/handoff-brief.md`.

1. **Objective** — one line, what "done" means.
2. **Established facts** — exact file paths, symbols, observed outputs. Two lists: *verified* (you observed it) and *hypotheses* (you believe it, not yet confirmed). Never merge them.
3. **Changes applied** — each change with its verification status (verified / unverified / reverted) and how it was verified.
4. **Checks run** — the exact commands and their outcome (exit code or the key output line).
5. **Dead ends** — what was tried and why it failed, so the next instance does not repeat it.
6. **Remaining plan** — in execution order, starting with the exact next command.

What stays out: narrative of what happened, repeated or superseded error traces, hypotheses already killed (those go to dead ends as one line), anything re-fetchable from disk (quote the path and line, not the content).

## C. Resuming from a brief

When a session starts with a brief in context (hook-injected, pasted by the user, or read from `.claude/handoff.md`):

- Treat *verified* facts as true; do not re-derive them.
- Re-check every *hypothesis* before building on it — that is exactly what the split is for.
- Do not retry anything listed under dead ends unless the plan says to retry it differently.
- If a change is marked *unverified*, run its check first.
- Start at item 1 of the remaining plan. If the plan is empty or stale (the file doesn't match the brief), say so and re-plan from the facts; don't silently start over.
- Update the brief as soon as you've verified or changed anything.

## Claude Code wiring (what the harness does for you)

Claude Code already has the harness half: auto-compaction, `/compact`, `/clear`, and hooks. The skill supplies the content half. Full setup in `references/claude-code-setup.md`; the short version:

- **Manual EoCC**: write the brief (section B), then the user runs `/compact` with the instruction text from `references/compaction-prompt.md` — the built-in summarizer then produces the six-part brief instead of a narrative. For a true reset (the paper's regime), the user runs `/clear` instead; the `SessionStart` hook below re-injects the brief, so the new conversation is exactly system prompt + brief.
- **Hook**: a `SessionStart` hook (matchers `compact|clear`) running `scripts/inject_brief.py` reads `.claude/handoff.md` and injects it as `additionalContext`. Installed automatically with the plugin; for a plain skill install, register it per `references/claude-code-setup.md`. This is the officially supported way to guarantee the structured state survives compaction; a `PreCompact` hook can only observe or block, not rewrite the summary.
- **Cost note**: every reset discards the prompt cache. Under flat API pricing the paper found compaction usually raises the nominal bill (e.g. GPT 5.6 Sol on SWE-bench Verified: $168 → $203 at 16K/12K) while cutting GPU decode cost 3–7x. Compact for accuracy and memory headroom, not to save dollars on a commercial API.

## Custom harness (EoCC / SAC)

If you are building your own agent loop (mini-agent / mini-swe-agent style, one bash command per turn), `scripts/sac_harness.py` is a runnable reference: one bash tool, three regimes (`fha`, `eocc`, `sac`), compaction at a token threshold or after every action, every conversation logged to disk, `--dry-run` with a scripted model for testing. Thresholds and the harness-ready compaction prompt are in `references/compaction-prompt.md`.

Defaults that the paper's results support: 24K/18K (limit/threshold) for frontier models; 16K/12K only for strong, terse models (Opus-class held flat; several open-weight models collapsed, one from 53% to 3.6%, because verbose traces exhausted the budget before any progress). Use SAC when peak memory is the constraint (local serving, batch concurrency), not when API spend is — it calls the model twice per action and discards the KV cache every step.

## Limits to keep in mind

- Compaction is lossy by construction. Tasks that need exact recall of arbitrary history (the i-th outcome of a sequence) need the full log on disk, read selectively — the harness does this; in Claude Code, write important observations to files.
- The brief is only as good as its facts. "Probably in `utils/`" is a hypothesis; `src/utils/parse.py:42` is a fact. Write facts.
- Weaker or chatty models need a larger budget; if a brief keeps getting truncated, raise the threshold before blaming the model.

## Files

- `references/handoff-brief.md` — the six-part template, a filled example, and the rules per section. Read before writing your first brief in a session.
- `references/compaction-prompt.md` — harness-ready compaction prompt, `/compact` instruction text, regime definitions and thresholds.
- `references/claude-code-setup.md` — settings.json / plugin hook config, `/compact` vs `/clear` usage, `.gitignore`, cost caveats.
- `scripts/doc-read` — bounded window reader (`--lines`, `--chars`, `--around`, `--grep`, `--head`), 6K default / 8K hard cap.
- `scripts/inject_brief.py` — SessionStart hook: injects the brief after `/compact` or `/clear`.
- `scripts/backup_transcript.py` — optional PreCompact hook: copies the full transcript to `.claude/transcripts/` so history stays selectively readable.
- `scripts/sac_harness.py` — reference FHA/EoCC/SAC loop with a single bash tool and conversation logging.
