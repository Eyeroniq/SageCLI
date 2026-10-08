"""Accuracy evaluation harness for the generated commands.

Runs every request in a prompts data set through the engine and reports:

1. exact match after normalisation (whitespace, quote style, short-flag order);
2. validator-verdict agreement with the data set's `expected_risk`;
3. per-request latency, overall and per-category accuracy;
4. (optional, Linux + sandbox) executable equivalence on the `safe_to_run` rows:
   the generated and reference commands run in the sandbox (sagecli.sandbox) on an
   identical fixture directory and their stdout and exit codes are compared.

It also writes `eval/manual_grading.csv` (request, generated, reference, correct)
for a human to fill in, and saves `benchmarks/eval_results.{md,json}`.

`--mock` uses a fake engine that returns each row's reference command, so the
harness itself can be exercised in CI without the model. Accuracy figures are only
meaningful with the real model: run this on your machine.

Usage:
    python scripts/eval_accuracy.py --mock
    python scripts/eval_accuracy.py --model /path/to/model.gguf --threads 4
    python scripts/eval_accuracy.py --equivalence   # add the sandbox comparison
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import re
import shlex
import statistics
import sys
from collections import defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from sagecli import __version__
from sagecli.validator import validate

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "eval" / "prompts.jsonl"
DEFAULT_OUT = ROOT / "benchmarks" / "eval_results.json"
DEFAULT_GRADING = ROOT / "eval" / "manual_grading.csv"
FIELDS = {"id", "request", "reference_command", "category", "expected_risk", "safe_to_run"}


def load_rows(path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        missing = FIELDS - row.keys()
        if missing:
            raise ValueError(f"{path}:{number}: missing fields {sorted(missing)}")
        rows.append(row)
    return rows


def normalise(command: str) -> str:
    """Canonicalise a command for exact-match comparison.

    Collapses whitespace and quote style via shlex, and sorts the letters within
    short flags and the short flags among themselves, so `ls -la` and `ls -al`
    compare equal. Operand order is preserved.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return " ".join(command.split())
    if not tokens:
        return ""
    head, rest = tokens[0], tokens[1:]
    short = re.compile(r"-[A-Za-z]+")
    flags = sorted("-" + "".join(sorted(t[1:])) for t in rest if short.fullmatch(t))
    operands = [t for t in rest if not short.fullmatch(t)]
    return " ".join([head, *flags, *operands])


class ReferenceEngine:
    """A fake engine that returns each request's reference command (for --mock)."""

    def __init__(self, rows: list[dict]) -> None:
        self._by_request = {row["request"]: row["reference_command"] for row in rows}

    def generate_command(self, request: str) -> str:
        return self._by_request.get(request, "")


def build_engine(mock: bool, model: Path | None, threads: int | None, rows: list[dict]):
    if mock:
        return ReferenceEngine(rows)
    from sagecli.config import GenerationSettings
    from sagecli.engine import Engine
    settings = GenerationSettings()
    if threads:
        settings = replace(settings, n_threads=threads)
    return Engine(model, settings=settings)


def evaluate(rows: list[dict], engine) -> list[dict]:
    """Generate and score every row (exact match, verdict agreement, latency)."""
    import time
    results = []
    for row in rows:
        start = time.perf_counter()
        generated = engine.generate_command(row["request"])
        latency = time.perf_counter() - start
        verdict = validate(generated).risk.name if generated else "SAFE"
        results.append({
            "id": row["id"],
            "request": row["request"],
            "category": row["category"],
            "reference_command": row["reference_command"],
            "generated_command": generated,
            "exact_match": normalise(generated) == normalise(row["reference_command"]),
            "expected_risk": row["expected_risk"],
            "verdict": verdict,
            "verdict_agreement": verdict == row["expected_risk"],
            "safe_to_run": bool(row["safe_to_run"]),
            "latency_s": round(latency, 4),
        })
    return results


def run_equivalence(results: list[dict]) -> None:
    """Add `executably_equivalent` to safe_to_run rows using the sandbox (Linux only)."""
    import tempfile

    from sagecli import sandbox
    backend = sandbox.available_backend()
    if backend is None:
        return
    for result in results:
        if not result["safe_to_run"]:
            continue
        with tempfile.TemporaryDirectory() as fixture:
            _make_fixture(Path(fixture))
            ref = sandbox.preview(result["reference_command"], cwd=fixture, backend=backend)
            gen = sandbox.preview(result["generated_command"], cwd=fixture, backend=backend)
        result["executably_equivalent"] = (
            ref.ran and gen.ran and ref.returncode == gen.returncode
            and ref.stdout == gen.stdout)


def _make_fixture(root: Path) -> None:
    """A small, deterministic directory so read-only commands have files to act on."""
    (root / "file.txt").write_text("alpha\nbeta\n\nfoo\n", encoding="utf-8")
    (root / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (root / "numbers.txt").write_text("3\n1\n2\n", encoding="utf-8")
    (root / "a.txt").write_text("x\n", encoding="utf-8")
    (root / "b.txt").write_text("y\n", encoding="utf-8")
    (root / "app.log").write_text("info start\nerror boom\n", encoding="utf-8")
    (root / "main.py").write_text("print('hi')\n", encoding="utf-8")


def _rate(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


def aggregate(results: list[dict]) -> dict:
    exact = [r for r in results if r["exact_match"]]
    agree = [r for r in results if r["verdict_agreement"]]
    latencies = [r["latency_s"] for r in results]
    by_category: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_category[r["category"]].append(r)
    per_category = {
        name: {"total": len(rows), "exact": sum(r["exact_match"] for r in rows),
               "exact_rate": _rate(sum(r["exact_match"] for r in rows), len(rows))}
        for name, rows in sorted(by_category.items())
    }
    equivalence_rows = [r for r in results if "executably_equivalent" in r]
    report = {
        "sagecli_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "total": len(results),
        "exact_matches": len(exact),
        "exact_match_rate": _rate(len(exact), len(results)),
        "verdict_agreements": len(agree),
        "verdict_agreement_rate": _rate(len(agree), len(results)),
        "latency_mean_s": round(statistics.mean(latencies), 4) if latencies else 0.0,
        "latency_median_s": round(statistics.median(latencies), 4) if latencies else 0.0,
        "per_category": per_category,
        "equivalence_checked": len(equivalence_rows),
        "executably_equivalent": sum(r.get("executably_equivalent", False) for r in results),
        "results": results,
    }
    return report


def render_markdown(report: dict) -> str:
    r = report
    lines = [
        "# Accuracy evaluation",
        "",
        f"Generated {r['generated_at']} with sagecli {r['sagecli_version']}, "
        f"Python {r['python']} on {r['platform']}.",
        "",
        "Run with the real model for meaningful numbers; `--mock` only exercises the harness.",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Exact match | {r['exact_matches']}/{r['total']} "
        f"({r['exact_match_rate']:.1%}) |",
        f"| Verdict agreement | {r['verdict_agreements']}/{r['total']} "
        f"({r['verdict_agreement_rate']:.1%}) |",
        f"| Latency mean / median | {r['latency_mean_s']:.3f}s / {r['latency_median_s']:.3f}s |",
        f"| Executable equivalence | {r['executably_equivalent']}/{r['equivalence_checked']} "
        "checked |",
        "",
        "## Per category (exact match)",
        "",
        "| Category | Exact |",
        "| --- | --- |",
    ]
    for name, stats in r["per_category"].items():
        lines.append(f"| {name} | {stats['exact']}/{stats['total']} ({stats['exact_rate']:.0%}) |")
    return "\n".join(lines) + "\n"


def write_grading_csv(results: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["request", "generated", "reference", "correct (y/n)"])
        for r in results:
            writer.writerow([r["request"], r["generated_command"], r["reference_command"], ""])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data", "--dataset", dest="dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--mock", action="store_true",
                        help="use a fake engine returning the reference commands (for CI)")
    parser.add_argument("--model", type=Path, default=None, help="GGUF model path")
    parser.add_argument("--threads", type=int, default=None, help="llama.cpp threads")
    parser.add_argument("--equivalence", action="store_true",
                        help="also compare generated vs reference in the sandbox (Linux)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--grading", type=Path, default=DEFAULT_GRADING)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.dataset.is_file():
        print(f"error: data set not found: {args.dataset}", file=sys.stderr)
        return 2
    rows = load_rows(args.dataset)
    try:
        engine = build_engine(args.mock, args.model, args.threads, rows)
    except Exception as exc:  # EngineError and friends print a friendly message
        print(str(exc), file=sys.stderr)
        return 2

    results = evaluate(rows, engine)
    if args.equivalence:
        run_equivalence(results)
    report = aggregate(results)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.out.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    write_grading_csv(results, args.grading)

    print(f"exact match: {report['exact_matches']}/{report['total']} "
          f"({report['exact_match_rate']:.1%})")
    print(f"verdict agreement: {report['verdict_agreements']}/{report['total']} "
          f"({report['verdict_agreement_rate']:.1%})")
    print(f"wrote {args.out}, {args.out.with_suffix('.md')} and {args.grading}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
