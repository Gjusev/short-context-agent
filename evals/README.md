# Evals

The missing piece called out in the repo README: the paper's benchmark numbers
have not been re-run with this code. This directory is the scaffold to change
that.

## What's here

- `tasks/*.json` — task suite. Each task: goal, setup shell lines, and a verify
  command (exit 0 = pass). The agent's starting files come from
  `fixtures/<id>/fixtures/`, copied into the run's workdir; files next to that
  directory (deterministic generators, reference solutions) are NOT copied.
- `run_evals.py` — runs `sac_harness.py` across tasks x regimes
  (fha / eocc / sac), verifies end states, reports accuracy and peak live
  context per regime, writes `results.json`.
- `results/` — human-readable records of real runs (template inside); see the
  rules there before adding an entry.

## The suite

| task | what it exercises |
|---|---|
| `count-words` | baseline: small shell/python work |
| `fix-import` | baseline: read a test, write the missing module (needs `pytest`) |
| `make-config` | baseline: single trivial file creation |
| `find-needle-log` | long input (LCW2): a 1.5 MB / ~20k-line log; the answer must be located with `grep` and read through a bounded window — every regime is far under the file's size |
| `staged-release` | multi-session: five numbered specs applied in order; under eocc/sac the handoff brief must carry progress between compacted conversations (or progress is re-derived from disk) (needs `pytest`) |

## Usage

```bash
# smoke the plumbing (scripted fake model, no API key, tasks will FAIL — expected)
python3 evals/run_evals.py

# real runs (needs anthropic SDK + ANTHROPIC_API_KEY or an anthropic-compatible
# endpoint via ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN; runs commands in workdirs)
python3 evals/run_evals.py --real
python3 evals/run_evals.py --real --model claude-opus-4-5
python3 evals/run_evals.py --real --regimes eocc,sac
```

## Adding tasks

Drop a JSON file in `tasks/`. Keep tasks small enough to run in minutes and
deterministic to verify. Large inputs should be generated in `setup` by a
deterministic script kept outside `fixtures/<id>/fixtures/` (see
`fixtures/find-needle-log/generate.py`) so the repo stays lean and the agent
cannot short-circuit the task by reading the generator.

## Note on dry-run

`--dry-run` uses the harness's scripted fake model: it exercises setup, the
ReAct loop, logging and verification end to end, but it does not solve tasks,
so accuracy is 0 by design. It exists to prove the evaluation plumbing works
before spending tokens.
