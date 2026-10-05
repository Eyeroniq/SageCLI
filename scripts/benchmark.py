"""Latency benchmark for the real model (Linux, needs the GGUF file and llama-cpp-python).

Loads the model once, then turns 20 fixed requests into commands and reports:
cold-start (model load) time, first-request latency, mean / median / p95 latency,
tokens per second, CPU model and thread count. It reports only what it measures.

Usage:
    python scripts/benchmark.py
    python scripts/benchmark.py --model /path/to/model.gguf --threads 4

Writes benchmarks/results.md and benchmarks/results.json (or --out PATH plus .json).
Generated commands are only printed, never executed.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from sagecli import __version__, prompts
from sagecli.config import GenerationSettings
from sagecli.engine import Engine, EngineError, clean_command

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "benchmarks" / "results.md"

PROMPTS = [
    "show the 10 largest files in this folder",
    "list all files including hidden ones",
    "count the lines in every .py file here",
    "find files modified in the last 24 hours",
    "show disk usage of each folder in the current directory",
    "show free memory in human readable form",
    "print the current date and time",
    "search for the word TODO in all text files recursively",
    "show the last 20 lines of app.log",
    "list running processes sorted by memory usage",
    "compress the docs folder into docs.tar.gz",
    "extract archive.tar.gz into the current folder",
    "show my IP addresses",
    "count how many files are in this directory",
    "show the git log as one line per commit",
    "find all empty directories under here",
    "show which process is listening on port 8080",
    "print the number of CPU cores",
    "show the first 5 lines of data.csv",
    "list files larger than 100 MB in this folder",
]


def cpu_model() -> str:
    """CPU model name from /proc/cpuinfo, falling back to the platform module."""
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine() or "unknown"


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile (pct in 0..100) of a non-empty list."""
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def run_benchmark(engine: Engine, requests: list[str]) -> dict:
    """Load the model once, time every request, and return the measurements."""
    start = time.perf_counter()
    engine.load()
    load_seconds = time.perf_counter() - start

    runs = []
    for request in requests:
        completion = engine.complete(
            prompts.build_command_prompt(request), engine.settings.max_tokens
        )
        runs.append({
            "request": request,
            "command": clean_command(completion.text),
            "seconds": round(completion.seconds, 4),
            "completion_tokens": completion.completion_tokens,
        })

    latencies = [r["seconds"] for r in runs]
    total_tokens = sum(r["completion_tokens"] for r in runs)
    total_seconds = sum(latencies)
    return {
        "sagecli_version": __version__,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": str(engine.model_path),
        "cpu_model": cpu_model(),
        "cpu_count": os.cpu_count(),
        "threads": engine.settings.n_threads,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "requests": len(runs),
        "cold_start_seconds": round(load_seconds, 4),
        "first_request_seconds": latencies[0],
        "mean_seconds": round(statistics.mean(latencies), 4),
        "median_seconds": round(statistics.median(latencies), 4),
        "p95_seconds": percentile(latencies, 95),
        "completion_tokens": total_tokens,
        "tokens_per_second": round(total_tokens / total_seconds, 2) if total_seconds else 0.0,
        "runs": runs,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Latency benchmark",
        "",
        f"Generated {report['generated_at']} with sagecli {report['sagecli_version']}.",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| CPU | {report['cpu_model']} ({report['cpu_count']} logical cores) |",
        f"| Threads | {report['threads']} |",
        f"| Platform | {report['platform']}, Python {report['python']} |",
        f"| Model | `{Path(report['model']).name}` |",
        f"| Requests | {report['requests']} |",
        f"| Cold start (model load) | {report['cold_start_seconds']:.2f} s |",
        f"| First request | {report['first_request_seconds']:.2f} s |",
        f"| Mean latency | {report['mean_seconds']:.2f} s |",
        f"| Median latency | {report['median_seconds']:.2f} s |",
        f"| p95 latency | {report['p95_seconds']:.2f} s |",
        f"| Tokens per second | {report['tokens_per_second']:.1f} |",
        "",
        "## Per request",
        "",
        "| Request | Command | Seconds | Tokens |",
        "| --- | --- | --- | --- |",
    ]
    for run in report["runs"]:
        command = run["command"].replace("|", "\\|").replace("`", "'")
        lines.append(f"| {run['request']} | `{command}` | {run['seconds']:.2f} | "
                     f"{run['completion_tokens']} |")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", help="GGUF model path (default: $SAGE_MODEL_PATH or ./models)")
    parser.add_argument("--threads", type=int, help="llama.cpp threads (default: CPU count)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="Markdown report path; JSON is written next to it")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = GenerationSettings()
    if args.threads:
        settings = replace(settings, n_threads=args.threads)
    engine = Engine(args.model, settings=settings)
    try:
        report = run_benchmark(engine, PROMPTS)
    except EngineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_markdown(report), encoding="utf-8")
    json_path = args.out.with_suffix(".json")
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(render_markdown(report))
    print(f"wrote {args.out} and {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
