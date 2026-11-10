# Spec 1 — rename `fmt_date`

The function `fmt_date` in `app/dates.py` must be renamed to `format_date`
(same behavior). Update every caller so nothing references the old name;
`app/report.py` imports it. The old name must no longer exist anywhere.

## Acceptance

- `app.dates.format_date(date(2026, 2, 1)) == "2026-02-01"`
- `app.dates` has no attribute `fmt_date`
- `app/report.py` uses the new name
