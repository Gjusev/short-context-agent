# Spec 4 — accept US date format in `parse`

`app/dates.py: parse(s)` currently accepts only `YYYY-MM-DD`. Extend it to
also accept `MM/DD/YYYY` (US format). Both formats keep returning a
`datetime.date`. Anything else may keep raising.

## Acceptance

- `parse("2026-04-17") == date(2026, 4, 17)`
- `parse("04/17/2026") == date(2026, 4, 17)`
