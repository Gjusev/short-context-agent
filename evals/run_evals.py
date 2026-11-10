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
    "workdir": "tasks/fix-test"                // (informational) workdir template id
  }

The agent's starting files come from evals/fixtures/<id>/fixtures/ — everything
under it is copied into the run's workdir before setup lines run. Files next to
that directory (e.g. deterministic generators) are NOT copied; setup lines can
invoke them by relative path to build large inputs without bloating the repo.

Peak live context is taken from the harness's own JSON summary on stdout
(measured from real token usage), not estimated here.
"""
import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "skills" / "short-context-agent" / "scripts" / "sac_harness.py"
EVALS = Path(__file__).resolve().parent
TASKS_DIR = EVALS / "tasks"
FIXTURES = EVALS / "fixtures"
WORKDIRS = EVALS / "workdirs"
REGIMES = ["fha", "eocc", "sac"]
RUN_TIMEOUT = 1800  # seconds per task x regime harness run


def load_tasks():
    tasks = []
    for p in sorted(TASKS_DIR.glob("*.json")):
        tasks.append(json.loads(p.read_text()))
    return tasks


def copy_fixture(task, workdir):
    """Copy evals/fixtures/<id>/fixtures/* into the workdir (the task's starting files)."""
    src = FIXTURES / task["id"] / "fixtures"
    if not src.is_dir():
        return
    for item in src.iterdir():
        if item.is_dir():
            shutil.copytree(item, workdir / item.name)
        else:
            shutil.copy2(item, workdir / item.name)


def harness_summary(stdout):
    """The harness prints one JSON summary object on stdout; peak_ctx etc. come from there."""
    try:
        return json.loads(stdout[stdout.index("{"):])
    except (ValueError, json.JSONDecodeError):
        return {}


def run_one(task, regime, real, model):
    workdir = WORKDIRS / task["id"] / regime
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.parent.mkdir(parents=True, exist_ok=True)
    workdir.mkdir()
    copy_fixture(task, workdir)

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

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=RUN_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc = None

    # keep the harness's stderr for post-mortems (crashes land there)
    if proc is not None and proc.stderr.strip():
        (workdir / "stderr.txt").write_text(proc.stderr, encoding="utf-8")

    # verify the end state
    verify = subprocess.run(task["verify"], shell=True, cwd=workdir, capture_output=True)
    passed = verify.returncode == 0

    summary = harness_summary(proc.stdout) if proc else {}
    return {
        "task": task["id"],
        "regime": regime,
        "passed": passed,
        "exit_code": proc.returncode if proc else "timeout",
        "harness_error": bool(proc is None or proc.returncode != 0),
        "peak_live_context_tokens": summary.get("peak_ctx", 0),
        "actions": summary.get("actions", 0),
        "compactions": summary.get("compactions", 0),
        "final_answer": bool(summary.get("final")),
        "log": str(log.relative_to(ROOT).as_posix()) if log.exists() else "",
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
            err = " ERR" if row["harness_error"] else ""
            print(f"  [{mark}] {row['task']:16} {regime:5} peak_ctx={row['peak_live_context_tokens']:6} "
                  f"compactions={row['compactions']:3} final={row['final_answer']}{err}", flush=True)
            results.append(row)

    meta = {
        "date": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "real": args.real,
        "model": args.model or ("fake (dry-run)" if not args.real else "harness default"),
        "command": "python3 " + " ".join(sys.argv),
    }
    out = EVALS / "results.json"
    out.write_text(json.dumps({"meta": meta, "results": results}, indent=2))

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
