"""Measure the safety validator against the adversarial data set.

Reads eval/adversarial.jsonl (rows: id, command, technique, should_block) and
classifies every command with the validator. Nothing is ever executed.

Counting rules:
- an attack row (should_block true) is DETECTED when the verdict is not SAFE;
  the BLOCK-only rate is reported separately;
- a benign row (should_block false) is a FALSE POSITIVE when the verdict is not SAFE.

Usage:
    python scripts/validator_benchmark.py                      # regex layer, default output
    python scripts/validator_benchmark.py --layers regex --out benchmarks/validator_baseline.json
    python scripts/validator_benchmark.py --check              # exit 1 if thresholds fail

Writes the JSON report to --out and a Markdown report next to it (same name, .md).
Exit codes: 0 ok, 1 thresholds not met (only with --check), 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import tomllib
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from sagecli import __version__
from sagecli.validator import Risk, validate

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "eval" / "adversarial.jsonl"
DEFAULT_OUT = ROOT / "benchmarks" / "validator_results.json"
DEFAULT_THRESHOLDS = ROOT / "benchmarks" / "validator_thresholds.toml"
LAYERS = ("regex", "structural", "both")
IMPLEMENTED_LAYERS = ("regex",)


def load_rows(path: Path) -> list[dict]:
    """Read the JSONL data set and check that every row has the expected fields."""
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        missing = {"id", "command", "technique", "should_block"} - row.keys()
        if missing:
            raise ValueError(f"{path}:{number}: missing fields {sorted(missing)}")
        rows.append(row)
    return rows


def classify(command: str, layers: str) -> tuple[Risk, tuple[str, ...]]:
    """Return (risk, rule names) for one command using the selected validator layers."""
    if layers not in IMPLEMENTED_LAYERS:
        raise NotImplementedError(f"--layers {layers} is not implemented until Phase 2")
    result = validate(command)
    return result.risk, result.rules


def _rate(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


def run_benchmark(rows: list[dict], layers: str) -> dict:
    """Classify every row and build the report dictionary."""
    results = []
    for row in rows:
        risk, rules = classify(row["command"], layers)
        results.append({
            "id": row["id"],
            "technique": row["technique"],
            "command": row["command"],
            "should_block": bool(row["should_block"]),
            "verdict": risk.name,
            "rules": list(rules),
        })

    attacks = [r for r in results if r["should_block"]]
    benign = [r for r in results if not r["should_block"]]
    detected = [r for r in attacks if r["verdict"] != "SAFE"]
    blocked = [r for r in attacks if r["verdict"] == "BLOCK"]
    false_positives = [r for r in benign if r["verdict"] != "SAFE"]

    by_technique: dict[str, list[dict]] = defaultdict(list)
    for r in attacks:
        by_technique[r["technique"]].append(r)
    per_technique = {}
    for technique in sorted(by_technique):
        group = by_technique[technique]
        n_detected = sum(r["verdict"] != "SAFE" for r in group)
        n_blocked = sum(r["verdict"] == "BLOCK" for r in group)
        per_technique[technique] = {
            "total": len(group),
            "detected": n_detected,
            "blocked": n_blocked,
            "detection_rate": _rate(n_detected, len(group)),
            "block_rate": _rate(n_blocked, len(group)),
        }

    return {
        "layers": layers,
        "sagecli_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "attacks": len(attacks),
        "benign": len(benign),
        "detected": len(detected),
        "blocked": len(blocked),
        "detection_rate": _rate(len(detected), len(attacks)),
        "block_rate": _rate(len(blocked), len(attacks)),
        "false_positives": len(false_positives),
        "false_positive_rate": _rate(len(false_positives), len(benign)),
        "per_technique": per_technique,
        "misses": [r for r in attacks if r["verdict"] == "SAFE"],
        "false_positive_rows": false_positives,
        "results": results,
    }


def load_thresholds(path: Path) -> dict:
    """Read min_detection_rate and max_false_positives from the TOML config file."""
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    return {
        "min_detection_rate": float(data["min_detection_rate"]),
        "max_false_positives": int(data["max_false_positives"]),
    }


def check_thresholds(report: dict, thresholds: dict) -> list[str]:
    """Return a list of failure messages (empty when every threshold is met)."""
    failures = []
    if report["detection_rate"] < thresholds["min_detection_rate"]:
        failures.append(
            f"detection rate {report['detection_rate']:.2%} is below "
            f"min_detection_rate {thresholds['min_detection_rate']:.2%}"
        )
    if report["false_positives"] > thresholds["max_false_positives"]:
        failures.append(
            f"{report['false_positives']} false positives exceed "
            f"max_false_positives {thresholds['max_false_positives']}"
        )
    return failures


def _cell(text: str) -> str:
    """Make a command safe to show inside a Markdown table cell."""
    return "`" + text.replace("\n", "\\n").replace("|", "\\|").replace("`", "'") + "`"


def render_markdown(report: dict) -> str:
    """Human-readable version of the report."""
    lines = [
        f"# Validator benchmark ({report['layers']} layer)",
        "",
        f"Generated {report['generated_at']} with sagecli {report['sagecli_version']}, "
        f"Python {report['python']} on {report['platform']}.",
        "",
        "Detected = verdict is not SAFE. Blocked = verdict is BLOCK.",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Attacks detected | {report['detected']}/{report['attacks']} "
        f"({report['detection_rate']:.1%}) |",
        f"| Attacks blocked | {report['blocked']}/{report['attacks']} "
        f"({report['block_rate']:.1%}) |",
        f"| False positives | {report['false_positives']}/{report['benign']} "
        f"({report['false_positive_rate']:.1%}) |",
        "",
        "## Per technique",
        "",
        "| Technique | Detected | Blocked |",
        "| --- | --- | --- |",
    ]
    for technique, stats in report["per_technique"].items():
        lines.append(
            f"| {technique} | {stats['detected']}/{stats['total']} "
            f"({stats['detection_rate']:.0%}) | {stats['blocked']}/{stats['total']} "
            f"({stats['block_rate']:.0%}) |"
        )
    lines += ["", f"## Missed attacks ({len(report['misses'])})", ""]
    if report["misses"]:
        lines += ["| ID | Technique | Command |", "| --- | --- | --- |"]
        lines += [f"| {r['id']} | {r['technique']} | {_cell(r['command'])} |"
                  for r in report["misses"]]
    else:
        lines.append("None.")
    lines += ["", f"## False positives ({len(report['false_positive_rows'])})", ""]
    if report["false_positive_rows"]:
        lines += ["| ID | Command | Verdict | Rules |", "| --- | --- | --- | --- |"]
        lines += [f"| {r['id']} | {_cell(r['command'])} | {r['verdict']} | "
                  f"{', '.join(r['rules'])} |" for r in report["false_positive_rows"]]
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def print_summary(report: dict) -> None:
    print(f"Validator benchmark, layers={report['layers']}")
    print(f"  detection: {report['detected']}/{report['attacks']} ({report['detection_rate']:.1%})"
          f"   block-only: {report['blocked']}/{report['attacks']} ({report['block_rate']:.1%})")
    print(f"  false positives: {report['false_positives']}/{report['benign']} "
          f"({report['false_positive_rate']:.1%})")
    for technique, stats in report["per_technique"].items():
        print(f"    {technique:<28} detected {stats['detected']:>3}/{stats['total']:<3}"
              f" blocked {stats['blocked']:>3}/{stats['total']}")
    print(f"  missed attacks: {len(report['misses'])}")
    for r in report["misses"]:
        print(f"    {r['id']} [{r['technique']}] {r['command']!r}")
    for r in report["false_positive_rows"]:
        print(f"  false positive {r['id']} {r['verdict']} {r['rules']} {r['command']!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--layers", choices=LAYERS, default="regex",
                        help="validator layers to use (structural/both arrive in Phase 2)")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET,
                        help="JSONL data set (default: eval/adversarial.jsonl)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="JSON report path; the .md report is written next to it")
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS,
                        help="TOML file with min_detection_rate and max_false_positives")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 when the thresholds are not met")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.layers not in IMPLEMENTED_LAYERS:
        print(f"error: --layers {args.layers} is not implemented until Phase 2", file=sys.stderr)
        return 2
    if not args.dataset.is_file():
        print(f"error: data set not found: {args.dataset}", file=sys.stderr)
        return 2

    report = run_benchmark(load_rows(args.dataset), args.layers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path = args.out.with_suffix(".md")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print_summary(report)
    print(f"wrote {args.out} and {md_path}")

    if args.check:
        failures = check_thresholds(report, load_thresholds(args.thresholds))
        for failure in failures:
            print(f"THRESHOLD FAILED: {failure}", file=sys.stderr)
        if failures:
            return 1
        print("thresholds met")
    return 0


if __name__ == "__main__":
    sys.exit(main())
