# Claude Code setup

Claude Code supplies the harness half of the recipe (auto-compaction, `/compact`, `/clear`, hooks). This file wires the skill's content half into it. Verified against the Claude Code hooks reference (code.claude.com/docs/en/hooks) as of 2026-11-05.

## What the hooks can and cannot do

| Event | Receives | Can it rewrite the summary? | Useful for |
|---|---|---|---|
| `PreCompact` | `trigger` (`manual`/`auto`), `custom_instructions` (from `/compact <text>`), `transcript_path` | No — it can only observe or block (`decision: "block"`) | backing up the transcript to disk (the paper's "log the full history" requirement) |
| `SessionStart` with `source: "compact"` or `"clear"` | `source`, `cwd` | n/a — but it can inject `additionalContext` into the fresh context | re-injecting `.claude/handoff.md` so the structured brief survives regardless of what the summarizer wrote |

So the design is: the agent writes the brief to disk (SKILL.md §B); the `SessionStart` hook puts it back after any compaction or `/clear`. Don't block compaction from `PreCompact` — blocking auto-compaction at the context ceiling leaves the session stuck.

## 1. Install the SessionStart hook

If you installed the plugin (`claude plugin install short-context-agent@short-context-agent`), the hook is already registered from the plugin's `hooks/hooks.json` and this section can be skipped. For a plain skill install (copied folder, `npx skills add`), pick one location.

**User or project settings** (`~/.claude/settings.json` or `.claude/settings.json`). Use exec form (`command` + `args`) so the path needs no quoting; replace the path with wherever the skill folder lives (for example `~/.claude/skills/short-context-agent`):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "compact|clear",
        "hooks": [
          {
            "type": "command",
            "command": "python3",
            "args": ["/ABSOLUTE/PATH/TO/short-context-agent/scripts/inject_brief.py"],
            "timeout": 10,
            "statusMessage": "Re-injecting handoff brief"
          }
        ]
      }
    ]
  }
}
```

**Plugin** (`hooks/hooks.json` in the plugin that bundles this skill):

```json
{
  "description": "Re-inject the handoff brief after compaction or /clear",
  "hooks": {
    "SessionStart": [
      {
        "matcher": "compact|clear",
        "hooks": [
          {
            "type": "command",
            "command": "python3",
            "args": ["${CLAUDE_PLUGIN_ROOT}/skills/short-context-agent/scripts/inject_brief.py"],
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Options (environment variables read by the script):

- `COMPACTION_BRIEF_PATH` — override the brief location (default `<cwd>/.claude/handoff.md`).
- `COMPACTION_BRIEF_MAX_AGE_HOURS` — ignore briefs older than this (default `72`), so a week-old file from another task isn't injected into a new session. Set `0` to disable the check.

Add `startup` to the matcher (`startup|resume|compact|clear`) if you want "resume where we left off" to work across sessions automatically. With the age check on, this is usually safe; the brief header carries its timestamp either way.

Check with `/hooks` in a session that the hook is listed, and test it with:

```bash
echo '{"hook_event_name":"SessionStart","source":"compact","cwd":"'"$PWD"'"}' | python3 scripts/inject_brief.py
```

## 2. Optional: back up the transcript on PreCompact

The paper notes that exact recall of arbitrary history needs the full log on disk, read selectively. A `PreCompact` hook can copy the transcript before it is condensed:

```json
{
  "hooks": {
    "PreCompact": [
      {
        "matcher": "auto|manual",
        "hooks": [
          {
            "type": "command",
            "command": "python3",
            "args": ["/ABSOLUTE/PATH/TO/short-context-agent/scripts/backup_transcript.py"],
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Copies land in `<cwd>/.claude/transcripts/<UTC stamp>-<trigger>.jsonl` (override the directory with `COMPACTION_TRANSCRIPT_DIR`). The agent can then `grep` old transcripts like any other document (SKILL.md §A). Keep `.claude/transcripts/` gitignored.

## 3. `.gitignore`

```
.claude/handoff.md
.claude/handoff-*.md
.claude/transcripts/
```

## 4. Using it in a session

**Checkpoint (agent-side).** The agent follows SKILL.md §B and writes `.claude/handoff.md` at milestones. You can force it any time: "checkpoint" / "write the handoff brief".

**Manual compaction (EoCC with the built-in summarizer).**

```
/compact <instruction text from references/compaction-prompt.md>
```

The summarizer writes a six-part brief; the hook adds the on-disk brief on top. If the two disagree, the on-disk one is the agent's own and more precise — tell the agent to reconcile and rewrite the file.

**True reset (the paper's regime).** Make sure the brief is fresh, then:

```
/clear
```

The hook injects the brief; the new conversation is system prompt + brief, and the agent resumes per SKILL.md §C. This is the closest Claude Code equivalent of EoCC and costs nothing in summarizer tokens. Prefer it over `/compact` when the conversation is full of dead-end traces.

**Auto-compaction.** Fires on its own near the context limit. The hook still runs afterwards, so a recent brief survives; an old one is dropped by the age check. The agent cannot see the token count, which is why §B asks for event-based checkpoints — a brief that is never older than ~10 tool calls is always usable.

## 5. Cost and behaviour caveats

- Each compaction or `/clear` discards the prompt cache; the next request re-writes it. On a commercial API this usually raises the nominal bill (the paper's numbers are in `compaction-prompt.md`). The gains are accuracy on long tasks and bounded memory; don't sell it as cheaper.
- Hooks' `additionalContext` is capped at 10,000 characters; longer content is written to a file and only a 2,000-character preview is injected. Keep briefs under ~8K characters (SKILL.md's 300–900 words does this with margin), or the script will inject only the first 9,500 characters and say so.
- Hook stdout is only read as JSON if it is a single JSON object with nothing else around it; the script prints nothing at all when there is no brief to inject.
