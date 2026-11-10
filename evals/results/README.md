# Results

Every file in this directory records one **real** benchmark run of the task
suite. Dry-run output is never recorded here — `--dry-run` exercises plumbing
only (accuracy 0 by design).

## Format

One file per run: `YYYY-MM-DD-<model>.md` (suffix `-2`, `-3`, … if rerun the
same day). Copy the template below verbatim and fill every field — a field you
cannot fill honestly means the run is not ready to commit.

```markdown
# <date> — <model> — full suite

- **Suite**: <plugin version from .claude-plugin/plugin.json> @ <git short SHA of the run>
- **Model**: <model name exactly as passed to --model>
- **Endpoint**: <provider/endpoint used, e.g. Z.ai Coding Plan anthropic-compat>
- **Command** (verbatim, from the repo root):

      python3 evals/run_evals.py --real --model <model>

- **Environment**: <OS; note that harness bash commands ran directly on it>

## Results

| task             | fha pass | fha peak | eocc pass | eocc peak | sac pass | sac peak |
|------------------|----------|----------|-----------|-----------|----------|----------|
| <task id>        | yes/no   | <tokens> | yes/no    | <tokens>  | yes/no   | <tokens> |
| ...              |          |          |           |           |          |          |

peak = peak live context in tokens, from the harness summary (measured usage).

## Accuracy

| regime | accuracy | avg peak ctx (tokens) | avg compactions |
|--------|----------|-----------------------|-----------------|
| fha    | x/5      |                       | 0               |
| eocc   | x/5      |                       |                 |
| sac    | x/5      |                       |                 |

## Notes

<anomalies, timeouts, compaction counts worth calling out, anything that makes
the numbers non-comparable>
```

`evals/results.json` (repo root of `evals/`) holds the same run as machine data
written by `run_evals.py`; the markdown file is the human record of it.

## Rules

- **No fabricated entries.** Only runs you executed, with the exact command recorded.
- Real runs bill tokens and execute shell commands in workdirs — say so in the entry.
- If a rerun changes numbers, add a new dated file; do not edit old ones.
