#!/usr/bin/env python3
"""Benchmark runner for the three context regimes (arXiv:2611.05306).

Runs sac_harness.py across a task suite x regimes (fha / eocc / sac), verifies
each task's expected end state, and reports accuracy + peak live context per
run. This is the piece the reproduction repo says is still missing: the paper's
benchmark numbers have not been re-run.

Usage:
  python3 evals/run_evals.py                          # dry-run smoke (no API key)
  python3 evals/run_evals.py --real                   # real model (needs anthropic key)
  python3 evals/run_evals.py --real --model claude-opus-4-5
  python3 evals/run_evals.py --regimes fha sac        # subset

Task format (evals/tasks/<id>.json):
  {
    "id": "fix-test",
    "task": "Make the failing test in the repo pass.",
    "setup": ["python3 -m venv? ..."],        // shell lines run before the agent starts
    "verify": "python3 -m pytest -q",          // exit 0 = pass
    "workdir": "tasks/fix-test"                // directory copied from evals/fixtures/
  }
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "skills" / "short-context-agent" / "scripts" / "sac_harness.py"
TASKS_DIR = Path(__file__).resolve().parent / "tasks"
WORKDIRS = Path(__file__).resolve().parent / "workdirs"
REGIMES = ["fha", "eocc", "sac"]


def load_tasks():
    tasks = []
    for p in sorted(TASKS_DIR.glob("*.json")):
        tasks.append(json.loads(p.read_text()))
    return tasks


def run_one(task, regime, real, model):
    workdir = WORKDIRS / task["id"] / regime
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.parent.mkdir(parents=True, exist_ok=True)
    workdir.mkdir()

    # set up the task workspace
    # shell=True is intentional: setup/verify lines come from trusted, repo-authored
    # task JSON files (not user input) and may contain pipes/redirects.
    for line in task.get("setup", []):
        subprocess.run(line, shell=True, cwd=workdir, capture_output=True)

    log = workdir / "transcript.jsonl"
    cmd = [sys.executable, str(HARNESS),
           "--task", task["task"],
           "--workdir", str(workdir),
           "--mode", regime,
           "--log", str(log)]
    if not real:
        cmd.append("--dry-run")
    if model:
        cmd += ["--model", model]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)

    # verify the end state
    verify = subprocess.run(task["verify"], shell=True, cwd=workdir, capture_output=True)
    passed = verify.returncode == 0

    # peak live context: the harness logs every discarded conversation; in dry-run
    # mode we approximate peak context by the number of logged turns * avg turn size
    peak_ctx = 0
    if log.exists():
        for line in log.read_text().splitlines():
            try:
                entry = json.loads(line)
                peak_ctx = max(peak_ctx, entry.get("live_context_tokens", 0))
            except json.JSONDecodeError:
                continue

    return {
        "task": task["id"],
        "regime": regime,
        "passed": passed,
        "exit_code": proc.returncode,
        "peak_live_context_tokens": peak_ctx,
        "log": str(log) if log.exists() else "",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true", help="run with a real model (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--model", default=None, help="model name passed through to the harness")
    ap.add_argument("--regimes", default=",".join(REGIMES), help="comma list: fha,eocc,sac")
    args = ap.parse_args()

    regimes = [r.strip() for r in args.regimes.split(",")]
    tasks = load_tasks()
    print(f"{len(tasks)} tasks x {len(regimes)} regimes ({'real model' if args.real else 'dry-run smoke'})\n")

    results = []
    for task in tasks:
        for regime in regimes:
            row = run_one(task, regime, args.real, args.model)
            mark = "PASS" if row["passed"] else "FAIL"
            print(f"  [{mark}] {row['task']:16} {regime:5} peak_ctx={row['peak_live_context_tokens']}")
            results.append(row)

    out = ROOT / "evals" / "results.json"
    out.write_text(json.dumps(results, indent=2))

    # summary per regime
    print("\nSummary (accuracy / avg peak context):")
    for regime in regimes:
        rows = [r for r in results if r["regime"] == regime]
        if not rows:
            continue
        acc = sum(r["passed"] for r in rows) / len(rows)
        peak = sum(r["peak_live_context_tokens"] for r in rows) / len(rows)
        print(f"  {regime:5}  acc={acc:.0%}  avg_peak_ctx={peak:.0f} tokens")
    print(f"\nresults -> {out}")


if __name__ == "__main__":
    main()
