"""Measure the safety validator against an adversarial data set.

Reads a JSONL data set (rows: id, command, technique, should_block) and classifies
every command with the validator. Nothing is ever executed.

Four numbers are reported:
- attacks flagged:  attack rows (should_block true) whose verdict is WARN or BLOCK;
- attacks blocked:  attack rows whose verdict is BLOCK          (headline metric);
- benign flagged:   benign rows (should_block false) whose verdict is WARN or BLOCK;
- benign blocked:   benign rows whose verdict is BLOCK          (headline metric).

Usage:
    python scripts/validator_benchmark.py                      # v1 data set, default output
    python scripts/validator_benchmark.py --data eval/adversarial_v2.jsonl --out PATH
    python scripts/validator_benchmark.py --data eval/adversarial_v2.jsonl --check

Writes the JSON report to --out and a Markdown report next to it (same name, .md).
--check compares the headline metrics with the thresholds for this data set in
benchmarks/validator_thresholds.toml.
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
    attacks_flagged = [r for r in attacks if r["verdict"] != "SAFE"]
    attacks_blocked = [r for r in attacks if r["verdict"] == "BLOCK"]
    benign_flagged = [r for r in benign if r["verdict"] != "SAFE"]
    benign_blocked = [r for r in benign if r["verdict"] == "BLOCK"]

    by_technique: dict[str, list[dict]] = defaultdict(list)
    for r in attacks:
        by_technique[r["technique"]].append(r)
    per_technique = {}
    for technique in sorted(by_technique):
        group = by_technique[technique]
        n_flagged = sum(r["verdict"] != "SAFE" for r in group)
        n_blocked = sum(r["verdict"] == "BLOCK" for r in group)
        per_technique[technique] = {
            "total": len(group),
            "flagged": n_flagged,
            "blocked": n_blocked,
            "flag_rate": _rate(n_flagged, len(group)),
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
        "attacks_flagged": len(attacks_flagged),
        "attacks_blocked": len(attacks_blocked),
        "attack_flag_rate": _rate(len(attacks_flagged), len(attacks)),
        "attack_block_rate": _rate(len(attacks_blocked), len(attacks)),
        "benign_flagged": len(benign_flagged),
        "benign_blocked": len(benign_blocked),
        "benign_flag_rate": _rate(len(benign_flagged), len(benign)),
        "benign_block_rate": _rate(len(benign_blocked), len(benign)),
        "per_technique": per_technique,
        "attacks_not_blocked": [r for r in attacks if r["verdict"] != "BLOCK"],
        "benign_flagged_rows": benign_flagged,
        "results": results,
    }


def load_thresholds(path: Path, dataset: Path) -> dict:
    """Return the [datasets.*] table of the TOML file whose `data` path is `dataset`."""
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    target = dataset.resolve()
    for name, table in data.get("datasets", {}).items():
        if (ROOT / table["data"]).resolve() == target:
            return {
                "name": name,
                "min_attack_block_rate": float(table["min_attack_block_rate"]),
                "max_benign_blocked": int(table["max_benign_blocked"]),
            }
    raise KeyError(f"no [datasets.*] entry in {path} has data = {dataset}")


def check_thresholds(report: dict, thresholds: dict) -> list[str]:
    """Return a list of failure messages (empty when every threshold is met)."""
    failures = []
    if report["attack_block_rate"] < thresholds["min_attack_block_rate"]:
        failures.append(
            f"attack block rate {report['attack_block_rate']:.2%} is below "
            f"min_attack_block_rate {thresholds['min_attack_block_rate']:.2%}"
        )
    if report["benign_blocked"] > thresholds["max_benign_blocked"]:
        failures.append(
            f"{report['benign_blocked']} benign rows blocked, more than "
            f"max_benign_blocked {thresholds['max_benign_blocked']}"
        )
    return failures


def _cell(text: str) -> str:
    """Make a command safe to show inside a Markdown table cell."""
    return "`" + text.replace("\n", "\\n").replace("|", "\\|").replace("`", "'") + "`"


def _count(part: int, whole: int, rate: float) -> str:
    return f"{part}/{whole} ({rate:.1%})"


def render_markdown(report: dict, dataset_name: str) -> str:
    """Human-readable version of the report."""
    r = report
    lines = [
        f"# Validator benchmark ({r['layers']} layer, {dataset_name})",
        "",
        f"Generated {r['generated_at']} with sagecli {r['sagecli_version']}, "
        f"Python {r['python']} on {r['platform']}.",
        "",
        "Flagged = verdict WARN or BLOCK. Blocked = verdict BLOCK. "
        "Headline metrics are the two BLOCKED rows.",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        "| **Attacks blocked** | "
        f"{_count(r['attacks_blocked'], r['attacks'], r['attack_block_rate'])} |",
        "| Attacks flagged | "
        f"{_count(r['attacks_flagged'], r['attacks'], r['attack_flag_rate'])} |",
        "| **Benign blocked** | "
        f"{_count(r['benign_blocked'], r['benign'], r['benign_block_rate'])} |",
        "| Benign flagged | "
        f"{_count(r['benign_flagged'], r['benign'], r['benign_flag_rate'])} |",
        "",
        "## Per technique (attacks)",
        "",
        "| Technique | Blocked | Flagged |",
        "| --- | --- | --- |",
    ]
    for technique, stats in r["per_technique"].items():
        lines.append(
            f"| {technique} | {stats['blocked']}/{stats['total']} ({stats['block_rate']:.0%}) | "
            f"{stats['flagged']}/{stats['total']} ({stats['flag_rate']:.0%}) |"
        )
    lines += ["", f"## Attacks not blocked ({len(r['attacks_not_blocked'])})", ""]
    if r["attacks_not_blocked"]:
        lines += ["| ID | Technique | Verdict | Command |", "| --- | --- | --- | --- |"]
        lines += [f"| {x['id']} | {x['technique']} | {x['verdict']} | {_cell(x['command'])} |"
                  for x in r["attacks_not_blocked"]]
    else:
        lines.append("None.")
    lines += ["", f"## Benign rows flagged ({len(r['benign_flagged_rows'])})", ""]
    if r["benign_flagged_rows"]:
        lines += ["| ID | Verdict | Rules | Command |", "| --- | --- | --- | --- |"]
        lines += [f"| {x['id']} | {x['verdict']} | {', '.join(x['rules'])} | "
                  f"{_cell(x['command'])} |" for x in r["benign_flagged_rows"]]
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def print_summary(report: dict, dataset_name: str) -> None:
    r = report
    print(f"Validator benchmark, layers={r['layers']}, data={dataset_name}")
    print(f"  attacks blocked: {_count(r['attacks_blocked'], r['attacks'], r['attack_block_rate'])}"
          f"   flagged: {_count(r['attacks_flagged'], r['attacks'], r['attack_flag_rate'])}")
    print(f"  benign blocked:  {_count(r['benign_blocked'], r['benign'], r['benign_block_rate'])}"
          f"   flagged: {_count(r['benign_flagged'], r['benign'], r['benign_flag_rate'])}")
    for technique, stats in r["per_technique"].items():
        print(f"    {technique:<28} blocked {stats['blocked']:>3}/{stats['total']:<3}"
              f" flagged {stats['flagged']:>3}/{stats['total']}")
    print(f"  attacks not blocked: {len(r['attacks_not_blocked'])}")
    for x in r["attacks_not_blocked"]:
        print(f"    {x['id']} [{x['technique']}] {x['verdict']} {x['command']!r}")
    for x in r["benign_flagged_rows"]:
        print(f"  benign flagged {x['id']} {x['verdict']} {x['rules']} {x['command']!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--layers", choices=LAYERS, default="regex",
                        help="validator layers to use (structural/both arrive in Phase 2)")
    parser.add_argument("--data", "--dataset", dest="dataset", type=Path,
                        default=DEFAULT_DATASET,
                        help="JSONL data set (default: eval/adversarial.jsonl)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="JSON report path; the .md report is written next to it")
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS,
                        help="TOML file with a [datasets.NAME] table per data set")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 when this data set's thresholds are not met")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.layers not in IMPLEMENTED_LAYERS:
        print(f"error: --layers {args.layers} is not implemented until Phase 2", file=sys.stderr)
        return 2
    if not args.dataset.is_file():
        print(f"error: data set not found: {args.dataset}", file=sys.stderr)
        return 2
    thresholds = None
    if args.check:
        try:
            thresholds = load_thresholds(args.thresholds, args.dataset)
        except (KeyError, OSError, tomllib.TOMLDecodeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    report = run_benchmark(load_rows(args.dataset), args.layers)
    report["data"] = args.dataset.name
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path = args.out.with_suffix(".md")
    md_path.write_text(render_markdown(report, args.dataset.name), encoding="utf-8")
    print_summary(report, args.dataset.name)
    print(f"wrote {args.out} and {md_path}")

    if thresholds is not None:
        failures = check_thresholds(report, thresholds)
        for failure in failures:
            print(f"THRESHOLD FAILED [{thresholds['name']}]: {failure}", file=sys.stderr)
        if failures:
            return 1
        print(f"thresholds met [{thresholds['name']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
