#!/usr/bin/env python3
"""Deterministic generator for the find-needle-log task (LCW2 / selective reading).

Writes server.log into the current directory: ~20k lines, ~1.4 MB (far beyond the
harness's 24K-token context limit in every regime, so the needle can only be
found by locating it with grep and reading a bounded window).

The needle is planted verbatim, so the expected answer is fixed by construction:
the single line containing 'transaction=8817' carries CODE K7QX-ZULU-4229.
Near-miss ids 18817 and 58817 are planted on fixed lines so a sloppy grep for
'8817' returns several hits and the agent must use the exact marker. Decoy ids
never start with '8817', so grep 'transaction=8817' matches exactly one line.

Run from a task workdir via the task's setup line; no arguments, no deps.
"""
from pathlib import Path

LINES = 20000
NEEDLE_AT = 12317  # 1-based line number of the needle
NEEDLE = ("2026-04-17 09:41:23 ERROR node=7 transaction=8817 "
          "status=failed retry=3 CODE K7QX-ZULU-4229")
NEAR_MISS_1_AT, NEAR_MISS_1 = 7777, \
    "2026-04-09 11:02:44 INFO node=12 transaction=18817 status=ok latency=212ms"
NEAR_MISS_2_AT, NEAR_MISS_2 = 15002, \
    "2026-04-22 18:33:09 INFO node=3 transaction=58817 status=ok latency=87ms"

# explicit LCG: byte-identical output on every platform and Python version
_state = 123456789


def _rnd(mod):
    global _state
    _state = (6364136223846793005 * _state + 1442695040888963407) % (1 << 64)
    return (_state >> 33) % mod


def decoy():
    day = 1 + _rnd(27)
    hh, mm, ss = _rnd(24), _rnd(60), _rnd(60)
    node = 1 + _rnd(31)
    tid = 1000 + _rnd(8990000)
    while str(tid).startswith("8817"):  # keep 'transaction=8817' unique
        tid = 1000 + _rnd(8990000)
    return (f"2026-04-{day:02d} {hh:02d}:{mm:02d}:{ss:02d} INFO node={node} "
            f"transaction={tid} status=ok latency={1 + _rnd(4000)}ms")


def main():
    out = []
    for i in range(1, LINES + 1):
        if i == NEEDLE_AT:
            out.append(NEEDLE)
        elif i == NEAR_MISS_1_AT:
            out.append(NEAR_MISS_1)
        elif i == NEAR_MISS_2_AT:
            out.append(NEAR_MISS_2)
        else:
            out.append(decoy())
    Path("server.log").write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
