#!/usr/bin/env bash
# Smoke tests for short-context-agent. No API key needed. Run from anywhere:
#   bash tests/smoke.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILL="$ROOT/skills/short-context-agent"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "ok   $*"; }

# 1. Manifests parse and agree on the plugin name
python3 - "$ROOT" <<'PY'
import json, sys
root = sys.argv[1]
p = json.load(open(f"{root}/.claude-plugin/plugin.json"))
m = json.load(open(f"{root}/.claude-plugin/marketplace.json"))
h = json.load(open(f"{root}/hooks/hooks.json"))
assert p["name"] == "short-context-agent", p["name"]
assert any(e["name"] == p["name"] and e["source"] == "./" for e in m["plugins"]), "marketplace entry missing"
assert "SessionStart" in h["hooks"], "SessionStart hook missing"
for group in h["hooks"]["SessionStart"]:
    for hook in group["hooks"]:
        for a in hook.get("args", []):
            assert "${CLAUDE_PLUGIN_ROOT}" in a, f"hook path must use CLAUDE_PLUGIN_ROOT: {a}"
PY
pass "manifests"

# 2. Skill frontmatter and name/directory match
head -1 "$SKILL/SKILL.md" | grep -qx -- '---' || fail "SKILL.md must start with frontmatter"
grep -qx 'name: short-context-agent' "$SKILL/SKILL.md" || fail "frontmatter name must match the skill directory"
grep -q '^description: ' "$SKILL/SKILL.md" || fail "frontmatter description missing"
pass "skill frontmatter"

# 3. doc-read: needle in a ~775 KB file, window cap, exit codes
python3 - "$TMP/grammar.txt" <<'PY'
import random, sys
random.seed(1)
words = "the a of to in and is that for on with as by at from it an be this".split()
lines = [" ".join(random.choice(words) for _ in range(9)) + f" line{i}" for i in range(1, 18831)]
lines[3839] = "Two other verbs ewa 'to speak' and kademor 'to be mad' introduce an object to the scene when the applicative is used."
open(sys.argv[1], "w").write("\n".join(lines) + "\n")
PY
DR="$SKILL/scripts/doc-read"
"$DR" --grep '\bkademor\b' "$TMP/grammar.txt" | grep -q '^3840: ' || fail "doc-read --grep did not find the needle at line 3840"
"$DR" --around 3840:2 "$TMP/grammar.txt" | grep -q "to be mad" || fail "doc-read --around"
[ "$("$DR" --lines 1:400 "$TMP/grammar.txt" | wc -c)" -le 6200 ] || fail "doc-read did not enforce the 6000-char window"
"$DR" --lines 1:400 "$TMP/grammar.txt" | grep -q 'truncated at 6000' || fail "doc-read truncation marker"
[ "$("$DR" --max-chars 99999 --lines 1:400 "$TMP/grammar.txt" | wc -c)" -le 8200 ] || fail "doc-read hard cap 8000"
"$DR" --lines 5:3 "$TMP/grammar.txt" >/dev/null 2>&1 && fail "doc-read accepted an invalid range" || true
pass "doc-read"

# 4. inject_brief hook: silent without a brief, JSON with one, stale skipped, oversize truncated
mkdir -p "$TMP/proj/.claude"
OUT="$(echo '{"hook_event_name":"SessionStart","source":"compact","cwd":"'"$TMP/proj"'"}' | python3 "$SKILL/scripts/inject_brief.py")"
[ -z "$OUT" ] || fail "inject_brief printed output with no brief present"
printf '# Handoff brief — t\n## 1. Objective\nx\n## 6. Remaining plan\n1. `true`\n' > "$TMP/proj/.claude/handoff.md"
echo '{"hook_event_name":"SessionStart","source":"compact","cwd":"'"$TMP/proj"'"}' | python3 "$SKILL/scripts/inject_brief.py" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin)["hookSpecificOutput"]; assert d["hookEventName"]=="SessionStart" and "Handoff brief" in d["additionalContext"]' \
  || fail "inject_brief JSON"
touch -d '5 days ago' "$TMP/proj/.claude/handoff.md"
OUT="$(echo '{"source":"clear","cwd":"'"$TMP/proj"'"}' | python3 "$SKILL/scripts/inject_brief.py")"
[ -z "$OUT" ] || fail "inject_brief injected a stale brief"
python3 -c "open('$TMP/big.md','w').write('# Handoff brief\n' + 'x'*12000)"
echo '{"source":"compact","cwd":"'"$TMP/proj"'"}' | COMPACTION_BRIEF_PATH="$TMP/big.md" python3 "$SKILL/scripts/inject_brief.py" \
  | python3 -c 'import json,sys; c=json.load(sys.stdin)["hookSpecificOutput"]["additionalContext"]; assert len(c)<10000 and "Only the first" in c' \
  || fail "inject_brief oversize handling"
echo 'not json' | python3 "$SKILL/scripts/inject_brief.py" >/dev/null || fail "inject_brief must survive garbage stdin"
pass "inject_brief hook"

# 5. backup_transcript hook
echo '{"a":1}' > "$TMP/transcript.jsonl"
echo '{"hook_event_name":"PreCompact","trigger":"auto","cwd":"'"$TMP/proj"'","transcript_path":"'"$TMP/transcript.jsonl"'"}' \
  | python3 "$SKILL/scripts/backup_transcript.py"
ls "$TMP/proj/.claude/transcripts/"*-auto.jsonl >/dev/null 2>&1 || fail "backup_transcript did not copy the transcript"
pass "backup_transcript hook"

# 6. Harness dry run in all three regimes
mkdir -p "$TMP/wd"
for mode in fha eocc sac; do
  python3 "$SKILL/scripts/sac_harness.py" --task "dry run" --workdir "$TMP/wd" --mode "$mode" --dry-run --log "$TMP/$mode.jsonl" > "$TMP/$mode.json"
done
python3 - "$TMP" <<'PY'
import json, sys
t = sys.argv[1]
r = {m: json.load(open(f"{t}/{m}.json")) for m in ("fha", "eocc", "sac")}
assert r["fha"]["compactions"] == 0, r["fha"]
assert r["eocc"]["compactions"] == 1 and r["eocc"]["conversations"] == 2, r["eocc"]
assert r["sac"]["compactions"] == 3 and r["sac"]["conversations"] == 4, r["sac"]
assert all(v["final"].startswith("FINAL ANSWER") for v in r.values())
assert r["sac"]["peak_ctx"] < r["eocc"]["peak_ctx"] < r["fha"]["peak_ctx"]
logs = [json.loads(l) for l in open(f"{t}/eocc.jsonl")]
assert logs[0]["closed_by"] == "compaction:eocc" and logs[0]["brief_written"], "discarded conversation not logged with its brief"
PY
pass "harness dry run (fha / eocc / sac)"

# 7. Eval fixtures: the regression reproduces, and the planned fix passes
cp -r "$SKILL/evals/writes-handoff-brief-mid-task/files" "$TMP/fixture"
( cd "$TMP/fixture" && python3 -m unittest discover -s tests >/dev/null 2>&1 ) && fail "fixture regression does not reproduce" || true
sed -i 's/return _localize(dt, ZoneInfo(settings.DEFAULT_TZ))/return _localize(dt, timezone.utc)/' "$TMP/fixture/app/dates/parse.py"
( cd "$TMP/fixture" && python3 -m unittest discover -s tests >/dev/null 2>&1 ) || fail "intended fix does not pass the fixture suite"
pass "eval fixtures"

echo "all smoke tests passed"
