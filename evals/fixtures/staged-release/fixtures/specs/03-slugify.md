# Spec 3 — add `slugify`

Add a function `slugify(text)` to `app/text.py` (keep the existing `shout`).
Exact algorithm, in order:

1. lowercase the input
2. strip leading/trailing whitespace
3. replace every run of one or more whitespace characters with a single `-`
4. remove every character that is not `a-z`, `0-9` or `-`

## Acceptance

- `slugify("  Hello  World! ") == "hello-world"`
- `slugify("Big Data, 2026") == "big-data-2026"`
- `slugify("!!!") == ""`
