# Spec 5 — add a `debug` flag

Add a function `debug()` to `app/settings.py` that returns `True` if and only
if the environment variable `DEBUG` is exactly `"1"`; otherwise `False`
(including when `DEBUG` is unset, `"0"`, `"true"` or any other value).

## Acceptance

- with `DEBUG=1` in the environment: `debug() is True`
- with `DEBUG=0` and with `DEBUG` unset: `debug() is False`
