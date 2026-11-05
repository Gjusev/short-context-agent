---
type: llm
focus: trace
weight: 1
---

app/dates/parse.py is changed so naive input becomes UTC while explicit offsets are preserved, and `python -m unittest discover -s tests` reports all tests passing.
