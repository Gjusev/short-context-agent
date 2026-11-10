# Evals

The missing piece called out in the repo README: the paper's benchmark numbers
have not been re-run with this code. This directory is the scaffold to change
that.

## What's here

- `tasks/*.json` — task suite. Each task: goal, setup shell lines, a verify
  command (exit 0 = pass), and a workdir template copied from `fixtures/`.
- `run_evals.py` — runs `sac_harness.py` across tasks x regimes
  (fha / eocc / sac), verifies end states, reports accuracy and peak live
  context per regime, writes `results.json`.

## Usage

```bash
# smoke the plumbing (scripted fake model, no API key, tasks will FAIL — expected)
python3 evals/run_evals.py

# real runs (needs anthropic SDK + ANTHROPIC_API_KEY; runs commands in workdirs)
python3 evals/run_evals.py --real
python3 evals/run_evals.py --real --model claude-opus-4-5
python3 evals/run_evals.py --real --regimes eocc,sac
```

## Adding tasks

Drop a JSON file in `tasks/`. Keep tasks small enough to run in minutes and
deterministic to verify. Good first additions beyond the three here:
Terminal-Bench-lite shell tasks, a long-input task where the answer sits in a
file the agent must grep for (selective reading / LCW2), and a multi-session
task where the handoff brief carries state between conversations.

## Note on dry-run

`--dry-run` uses the harness's scripted fake model: it exercises setup, the
ReAct loop, logging and verification end to end, but it does not solve tasks,
so accuracy is 0 by design. It exists to prove the evaluation plumbing works
before spending tokens.
