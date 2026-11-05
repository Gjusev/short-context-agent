---
type: llm
focus: trace
weight: 1
---

After the fix, all tests pass, and the change is in app/dates/parse.py (naive input becomes UTC; explicit offsets are preserved); the tests and settings are not modified.
