---
type: llm
focus: trace
weight: 1
---

No tool call reads grammar.txt in full (no `cat grammar.txt`, no Read of the whole file); the agent searches first and reads a bounded window of at most a few hundred lines.
