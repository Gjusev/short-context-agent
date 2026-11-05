# Handoff brief — fix test_parse_date tz regression
Updated: 2026-11-05T14:12:08Z · Brief #1 · Regime: manual

## 1. Objective
`python -m unittest discover -s tests` passes with the parser fixed (tests and settings untouched).

## 2. Established facts
Verified (observed directly):
- tests/test_parse.py:9 — test_parse_date_naive_is_utc expects parse_date("2024-07-10T02:30") to carry tzinfo=timezone.utc (observed in file)
- app/dates/parse.py:24 — parse_date() returns _localize(dt, ZoneInfo(settings.DEFAULT_TZ)) for every input (observed)
- app/dates/parse.py:15 — _localize() attaches tz only when dt.tzinfo is None (observed)
- app/settings.py:1 — DEFAULT_TZ = "Europe/London" (observed)
- Failure message from the suite: naive input comes back with tzinfo=Europe/London instead of UTC (observed from `python -m unittest discover -s tests`)

Hypotheses (believed, not yet confirmed):
- The documented rule in app/dates/parse.py:3-6 (naive = UTC) is the intended behaviour and the refactor at line 24 is the bug — confirm by: reading CHANGELOG.md entry 0.9.0

## 3. Changes applied
| # | File | Change | Status | Verified by |
|---|------|--------|--------|-------------|
| — | — | none yet | — | — |

## 4. Checks run
- `python -m unittest discover -s tests` → 1 failure (test_parse_date_naive_is_utc), 2 passed

## 5. Dead ends (do not repeat)
- Changing DEFAULT_TZ to "UTC" in app/settings.py → makes the test pass but changes schedule rendering for every user; rejected, settings must stay as they are.
- Editing the expected value in tests/test_parse.py → rejected; the task is to fix the parser, not the test.

## 6. Remaining plan (execution order)
1. `grep -n "0.9.0" -A 2 CHANGELOG.md` — expect the naive-is-UTC rule; confirms the hypothesis
2. Edit app/dates/parse.py:24 so a naive datetime gets timezone.utc (not DEFAULT_TZ); aware datetimes unchanged
3. `python -m unittest discover -s tests` — expect 3 passed
4. Update this brief: move the change to "Changes applied" as verified
