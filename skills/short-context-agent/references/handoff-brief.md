# The handoff brief

A brief is written for a fresh instance that has the system prompt, the original task, and nothing else. It is not a summary of what happened; it is a description of what is true now and what to do next. Six sections, always in this order, nothing else. Overwrite the file each time.

## Template

```markdown
# Handoff brief — <short task name>
Updated: <ISO-8601 timestamp> · Brief #<n> · Regime: manual | EoCC | SAC

## 1. Objective
<One line. What "done" means. Quote the task's acceptance criterion if it has one.>

## 2. Established facts
Verified (observed directly):
- <path:line> — <fact> (observed: <the output or symptom that proves it>)
- ...

Hypotheses (believed, not yet confirmed):
- <claim> — <why you believe it> — confirm by: <exact check>
- ...

## 3. Changes applied
| # | File | Change | Status | Verified by |
|---|------|--------|--------|-------------|
| 1 | <path> | <one-line description> | verified / unverified / reverted | <command or observation> |

## 4. Checks run
- `<exact command>` → <exit code / key result line>
- ...

## 5. Dead ends (do not repeat)
- Tried <X> → failed because <Y>. <If a variant is still worth trying, say which, under section 6.>
- ...

## 6. Remaining plan (execution order)
1. `<exact next command>` — <what you expect to see>
2. ...
```

## Worked example

The task: "Fix `test_parse_date` failing in `tests/test_parse.py` after the timezone refactor." Written after 7 tool calls, just before running the full suite.

```markdown
# Handoff brief — fix test_parse_date tz regression
Updated: 2026-11-05T14:12:08Z · Brief #2 · Regime: manual

## 1. Objective
`pytest tests/test_parse.py::test_parse_date` passes and the full suite stays green.

## 2. Established facts
Verified (observed directly):
- tests/test_parse.py:41 — asserts parse_date("2024-07-10T02:30") == datetime(2024,7,10,2,30,tzinfo=UTC) (observed in file)
- src/dates/parse.py:88 — parse_date() now calls _localize(dt, tz=settings.DEFAULT_TZ) (observed; added in commit 4f2c1a9 "tz refactor")
- src/dates/parse.py:61 — _localize() returns dt.replace(tzinfo=tz) when dt.tzinfo is None (observed)
- Failing assertion message: "datetime(2024,7,10,2,30,tzinfo=Europe/London) != datetime(...,tzinfo=UTC)" (observed from pytest run)
- settings.DEFAULT_TZ resolves to "Europe/London" in the test env: `python -c "from app import settings; print(settings.DEFAULT_TZ)"` → Europe/London (observed)

Hypotheses (believed, not yet confirmed):
- Three other tests in tests/test_schedule.py also fail for the same reason — confirm by: `pytest tests/test_schedule.py -q`
- The intended behaviour is "naive input = UTC" (the test is right, the refactor is wrong), based on the docstring at src/dates/parse.py:70 — confirm by: reading CHANGELOG.md for the 4f2c1a9 entry

## 3. Changes applied
| # | File | Change | Status | Verified by |
|---|------|--------|--------|-------------|
| 1 | src/dates/parse.py:88 | pass tz=UTC when input string has no offset, else settings.DEFAULT_TZ | unverified | — |

## 4. Checks run
- `pytest tests/test_parse.py::test_parse_date -q` (before change) → 1 failed, tz mismatch as above
- `git log --oneline -5 -- src/dates/parse.py` → 4f2c1a9 is the only commit touching _localize in 6 months

## 5. Dead ends (do not repeat)
- Setting DEFAULT_TZ=UTC in the test conftest → suite passes but masks the behaviour change; rejected (user wants the parser fixed, not the tests).
- Removing _localize() entirely → 11 failures in tests/test_schedule.py that depend on localized output.

## 6. Remaining plan (execution order)
1. `pytest tests/test_parse.py::test_parse_date -q` — expect 1 passed; if not, inspect the offset-detection regex at src/dates/parse.py:84
2. `pytest tests/test_schedule.py -q` — confirms or kills hypothesis 1
3. `pytest -q` — full suite; expect green
4. Update the docstring at src/dates/parse.py:70 to state the naive-means-UTC rule
```

Note what the example does not contain: the pytest traceback (re-runnable), the diff (on disk, in git), the reasoning about how the regression was found (irrelevant to the next instance), or the two earlier wrong guesses about where _localize lived (they were killed; only the dead ends that someone might retry are listed).

## Rules per section

**1. Objective.** One line. If the task has acceptance criteria, quote them. If scope was narrowed or widened mid-task by the user, the objective reflects the current scope — the original task text is already in the fresh context, so don't repeat it.

**2. Established facts.** The most valuable section. Every fact carries a location (`path:line`, a URL, a command) and the observation that proves it. Keep *verified* and *hypotheses* as two lists and never promote a hypothesis without a check. A hypothesis without a "confirm by" is a guess; either add the check or drop it. Facts about the environment (tool versions, env vars, which test runner, which branch) belong here too if they were expensive to discover.

**3. Changes applied.** One row per change. Status is one of `verified`, `unverified`, `reverted`. A change that was made and then undone appears as `reverted` only if the next instance might otherwise re-apply it; otherwise drop it. "Verified by" is the command or observation, not "tests pass".

**4. Checks run.** Exact commands, exact key output. The point is that the next instance can re-run them and compare. Don't include checks that were superseded by a later run of the same command.

**5. Dead ends.** Each line is a decision not to retry something. Give the reason, because a reason lets the next instance judge whether a variant is still worth trying. Don't list every failed command — list the approaches that were abandoned.

**6. Remaining plan.** Execution order, concrete, starting with a command the next instance can run without thinking. Each step says what to expect, so a surprise is detectable. If the plan depends on a hypothesis, the step that checks the hypothesis comes first.

## Size

A good brief is 300–900 words. Under 150 words it is probably missing facts; over 1,200 it is probably carrying narrative or re-fetchable content. In a harness with a 12K compaction budget, keep the brief under ~1.5K tokens so there is room to act before the next reset.
