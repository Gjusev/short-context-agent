#!/usr/bin/env python3
"""Reference EoCC / SAC harness — "You don't need long context" (arXiv:2611.05306).

A minimal ReAct loop with one `bash` tool and three context regimes:

  fha   full-history accumulation: the append-only baseline
  eocc  end-of-conversation compaction: when the live context crosses --threshold,
        ask the model for a six-part handoff brief, discard the conversation, and
        start a fresh one containing only the system prompt, the task and the brief
  sac   single-action compaction: do that after every single action

Every discarded conversation is appended to --log as one JSON line, so the full
history stays on disk for selective reading (grep / doc-read), which is what the
paper prescribes for tasks that need exact recall.

Usage:
  python3 sac_harness.py --task "Fix the failing test in tests/" --workdir ./repo --mode eocc
  python3 sac_harness.py --task "..." --mode sac --limit 24000 --threshold 18000
  python3 sac_harness.py --task "..." --dry-run            # scripted fake model, no API key

Requires `pip install anthropic` and ANTHROPIC_API_KEY unless --dry-run.
The model runs arbitrary shell commands in --workdir: run this inside a container.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPT_FILE = HERE.parent / "references" / "compaction-prompt.md"

SYSTEM_PROMPT = """You are an autonomous software agent working in a Unix shell inside a sandbox.

Protocol:
- Act by calling the `bash` tool with exactly one shell command per reply. Think briefly, then act.
- Each command's stdout and stderr come back truncated; design commands whose output is small.
- Read large files selectively: locate what you need with `grep -n`, then read a bounded window with
  `doc-read --lines A:B FILE` or `doc-read --around LINE FILE` (never `cat` a large file).
- Record facts with their exact location (path:line) as you learn them; the conversation may be reset
  at any time and only a short handoff brief carries over.
- When the task is complete and verified, reply with text only (no tool call) beginning with
  `FINAL ANSWER:` followed by what was done and how it was verified.
- If a message contains a handoff brief, continue from it: verified facts are true, re-check
  hypotheses before relying on them, do not repeat dead ends, start at remaining plan step 1.
"""

BASH_TOOL = {
    "name": "bash",
    "description": "Run one shell command in the task's working directory. Returns the exit code "
                   "and the combined stdout/stderr, truncated if long.",
    "input_schema": {
        "type": "object",
        "properties": {"command": {"type": "string", "description": "The shell command to run."}},
        "required": ["command"],
    },
}


# ----------------------------------------------------------------------------- helpers

def load_compaction_prompt():
    text = PROMPT_FILE.read_text(encoding="utf-8")
    m = re.search(r"<!-- COMPACTION_PROMPT_START -->\s*(.*?)\s*<!-- COMPACTION_PROMPT_END -->", text, re.S)
    if not m:
        sys.exit(f"compaction prompt markers not found in {PROMPT_FILE}")
    return m.group(1).strip()


def initial_messages(task, state):
    text = f"Task:\n{task}"
    if state:
        text += ("\n\nHandoff brief from the previous conversation. Continue from it: verified facts are "
                 "true, re-check hypotheses before relying on them, do not repeat dead ends, start at "
                 "remaining plan step 1.\n\n" + state)
    else:
        text += "\n\nNo prior state. Begin."
    return [{"role": "user", "content": text}]


def block_to_dict(block):
    if isinstance(block, dict):
        return block
    if hasattr(block, "model_dump"):
        d = block.model_dump()
        return {k: v for k, v in d.items() if k in ("type", "text", "id", "name", "input")}
    return {"type": getattr(block, "type", "text"), "text": getattr(block, "text", "")}


def usage_num(usage, field):
    v = getattr(usage, field, None)
    if v is None and isinstance(usage, dict):
        v = usage.get(field)
    return int(v or 0)


def context_size(usage):
    """Live context after this call ≈ everything the model read plus what it wrote."""
    return (usage_num(usage, "input_tokens") + usage_num(usage, "cache_read_input_tokens")
            + usage_num(usage, "cache_creation_input_tokens") + usage_num(usage, "output_tokens"))


def truncate_observation(text, max_chars):
    if len(text) <= max_chars:
        return text
    head = max_chars * 2 // 3
    tail = max_chars - head
    return (text[:head] + f"\n[... {len(text) - max_chars} chars elided by harness; "
            f"use grep/doc-read for the middle ...]\n" + text[-tail:])


def run_bash(command, workdir, timeout, max_chars):
    env = dict(os.environ)
    env["PATH"] = f"{HERE}:{env.get('PATH', '')}"  # puts doc-read on PATH
    try:
        proc = subprocess.run(["bash", "-lc", command], cwd=workdir, env=env,
                              capture_output=True, text=True, timeout=timeout)
        out = proc.stdout + (("\n[stderr]\n" + proc.stderr) if proc.stderr.strip() else "")
        return f"[exit {proc.returncode}]\n" + truncate_observation(out, max_chars)
    except subprocess.TimeoutExpired:
        return f"[timeout after {timeout}s]"


def append_user_text(messages, text):
    """Add text as a user turn, merging into a trailing user message so roles keep alternating."""
    if messages and messages[-1]["role"] == "user":
        content = messages[-1]["content"]
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        content = list(content) + [{"type": "text", "text": text}]
        return messages[:-1] + [{"role": "user", "content": content}]
    return messages + [{"role": "user", "content": text}]


# ----------------------------------------------------------------------------- model clients

class Usage:
    def __init__(self, input_tokens, output_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = 0


class FakeResponse:
    def __init__(self, content, usage, stop_reason):
        self.content, self.usage, self.stop_reason = content, usage, stop_reason


class FakeClient:
    """Scripted model for --dry-run: three actions, then a final answer; canned briefs.

    Reports a growing context so an EoCC run at the default 24K/18K crosses the
    threshold on the third action, exercising the reset path without an API key.
    """
    SCRIPT = [
        "echo 'step one' > harness_note.txt && wc -c harness_note.txt",
        "doc-read harness_note.txt",
        "doc-read --head 1 harness_note.txt",
    ]

    def __init__(self):
        self.calls = 0
        self.actions = 0

    def create(self, *, messages, tools=None, tool_choice=None, max_tokens=0, **_):
        self.calls += 1
        assistant_turns = sum(1 for m in messages if m["role"] == "assistant")
        in_tok = 6000 + 7000 * assistant_turns
        if tool_choice and tool_choice.get("type") == "none":
            brief = ("# Handoff brief — dry run\n## 1. Objective\nFinish the scripted dry run.\n"
                     f"## 2. Established facts\nVerified:\n- harness_note.txt written (observed wc output)\n"
                     f"Hypotheses:\n- none\n## 3. Changes applied\n| 1 | harness_note.txt | created | verified | wc -c |\n"
                     f"## 4. Checks run\n- `wc -c harness_note.txt` → 9\n## 5. Dead ends\n- none\n"
                     f"## 6. Remaining plan\n1. continue the script at action {self.actions + 1}\n")
            return FakeResponse([{"type": "text", "text": brief}], Usage(in_tok, 180), "end_turn")
        if self.actions < len(self.SCRIPT):
            cmd = self.SCRIPT[self.actions]
            self.actions += 1
            content = [{"type": "text", "text": f"Running action {self.actions}."},
                       {"type": "tool_use", "id": f"toolu_fake_{self.actions}", "name": "bash",
                        "input": {"command": cmd}}]
            return FakeResponse(content, Usage(in_tok, 60), "tool_use")
        return FakeResponse([{"type": "text", "text": "FINAL ANSWER: dry run complete; harness_note.txt "
                                                      "created and read back via doc-read."}],
                            Usage(in_tok, 40), "end_turn")


class AnthropicClient:
    def __init__(self, model):
        try:
            import anthropic
        except ImportError:
            sys.exit("pip install anthropic   (or use --dry-run)")
        self._client = anthropic.Anthropic()
        self.model = model

    def create(self, *, messages, tools, tool_choice=None, max_tokens=4096):
        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            tools=tools,
        )
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        return self._client.messages.create(**kwargs)


# ----------------------------------------------------------------------------- the loop

def compact(client, messages, prompt, args, stats):
    msgs = append_user_text(messages, prompt)
    resp = client.create(messages=msgs, tools=[BASH_TOOL], tool_choice={"type": "none"},
                         max_tokens=args.brief_max_tokens)
    stats["in_tok"] += usage_num(resp.usage, "input_tokens")
    stats["out_tok"] += usage_num(resp.usage, "output_tokens")
    stats["cache_read"] += usage_num(resp.usage, "cache_read_input_tokens")
    text = "\n".join(block_to_dict(b).get("text", "") for b in resp.content
                     if block_to_dict(b).get("type") == "text").strip()
    return text or "(the model returned an empty brief; re-derive state from the task)"


def log_conversation(log_fh, conversation_id, messages, reason, brief=None):
    if not log_fh:
        return
    log_fh.write(json.dumps({"conversation": conversation_id, "closed_by": reason, "ts": time.time(),
                             "brief_written": brief, "messages": messages}) + "\n")
    log_fh.flush()


def run(args):
    prompt = load_compaction_prompt()
    client = FakeClient() if args.dry_run else AnthropicClient(args.model)
    log_fh = open(args.log, "a", encoding="utf-8") if args.log else None
    os.makedirs(args.workdir, exist_ok=True)

    state = None
    messages = initial_messages(args.task, state)
    stats = dict(steps=0, actions=0, compactions=0, conversations=1, peak_ctx=0,
                 in_tok=0, out_tok=0, cache_read=0)
    final = None
    est_ctx = 0

    while stats["steps"] < args.max_steps:
        stats["steps"] += 1
        max_tokens = args.max_output if args.mode == "fha" else max(512, min(args.max_output, args.limit - est_ctx))
        resp = client.create(messages=messages, tools=[BASH_TOOL], max_tokens=max_tokens)
        ctx = context_size(resp.usage)
        stats["peak_ctx"] = max(stats["peak_ctx"], ctx)
        stats["in_tok"] += usage_num(resp.usage, "input_tokens")
        stats["out_tok"] += usage_num(resp.usage, "output_tokens")
        stats["cache_read"] += usage_num(resp.usage, "cache_read_input_tokens")

        blocks = [block_to_dict(b) for b in resp.content]
        messages.append({"role": "assistant", "content": blocks})
        tool_uses = [b for b in blocks if b.get("type") == "tool_use"]

        if not tool_uses:
            final = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
            break

        results = []
        for tu in tool_uses:
            cmd = (tu.get("input") or {}).get("command", "")
            if args.verbose:
                print(f"[{args.mode} c{stats['conversations']} s{stats['steps']}] $ {cmd}", file=sys.stderr)
            obs = run_bash(cmd, args.workdir, args.timeout, args.max_observation)
            if args.verbose:
                print(obs[:400], file=sys.stderr)
            results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": obs})
            stats["actions"] += 1
        messages.append({"role": "user", "content": results})
        est_ctx = ctx + sum(len(r["content"]) // 4 for r in results)

        due = args.mode == "sac" or (args.mode == "eocc" and est_ctx >= args.threshold)
        if due:
            state = compact(client, messages, prompt, args, stats)
            log_conversation(log_fh, stats["conversations"], messages, f"compaction:{args.mode}", brief=state)
            stats["compactions"] += 1
            stats["conversations"] += 1
            messages = initial_messages(args.task, state)
            est_ctx = 0
            if args.verbose:
                print(f"[{args.mode}] compaction #{stats['compactions']} ({len(state)} chars)", file=sys.stderr)

    log_conversation(log_fh, stats["conversations"], messages, "final" if final else "max_steps")
    if log_fh:
        log_fh.close()

    print(json.dumps({"final": final, "state": state, **stats, "mode": args.mode,
                      "limit": args.limit, "threshold": args.threshold}, indent=2))
    return 0 if final else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--task", required=True)
    p.add_argument("--workdir", default=".")
    p.add_argument("--mode", choices=["fha", "eocc", "sac"], default="eocc")
    p.add_argument("--limit", type=int, default=24000,
                   help="context ceiling in tokens (default 24000); caps max_tokens per turn in eocc/sac")
    p.add_argument("--threshold", type=int, default=18000, help="EoCC compaction trigger (default 18000)")
    p.add_argument("--model", default="claude-sonnet-4-6")
    p.add_argument("--max-steps", type=int, default=100)
    p.add_argument("--max-output", type=int, default=4096, help="max_tokens per action turn")
    p.add_argument("--brief-max-tokens", type=int, default=1500)
    p.add_argument("--max-observation", type=int, default=4000, help="chars of tool output kept")
    p.add_argument("--timeout", type=int, default=120, help="seconds per bash command")
    p.add_argument("--log", help="JSONL file; every discarded conversation is appended here")
    p.add_argument("--dry-run", action="store_true", help="scripted fake model, no API key needed")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)
    if args.threshold >= args.limit:
        p.error("--threshold must be below --limit")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
