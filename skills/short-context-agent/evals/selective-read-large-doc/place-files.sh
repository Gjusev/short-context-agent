#!/usr/bin/env bash
# Generates the large input deterministically so the eval stays small on disk.
set -eu
python3 - <<'PY'
import random
random.seed(1)
words = "the a of to in and is that for on with as by at from it an be this".split()
lines = [" ".join(random.choice(words) for _ in range(9)) + f" line{i}" for i in range(1, 18831)]
lines[3839] = ("Two other verbs ewa 'to speak' and kademor 'to be mad' introduce an object "
               "to the scene when the applicative is used.")
open("grammar.txt", "w").write("\n".join(lines) + "\n")
PY
