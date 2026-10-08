"""Build a before/after table from two validator benchmark JSON reports.

Reads a baseline report (regex-only, frozen) and an "after" report (e.g. the
structural + regex run) and prints a Markdown comparison: overall attack block
and flag rates, benign rows blocked/flagged, per-technique block rate, and the
attacks each run still fails to block. Every number is recomputed from the
`results` array in each file, so it does not matter which key names a report used.

Usage:
    python scripts/compare_validator_runs.py \
        --baseline benchmarks/validator_baseline.json \
        --after benchmarks/validator_after.json \
        --out benchmarks/validator_comparison.md

Nothing is executed and no benchmark is run; this only reads two JSON files.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _rate(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def summarise(report: dict) -> dict:
    """Recompute the headline metrics from a report's per-row `results`."""
    results = report.get("results", [])
    attacks = [r for r in results if r["should_block"]]
    benign = [r for r in results if not r["should_block"]]
    blocked = [r for r in attacks if r["verdict"] == "BLOCK"]
    flagged = [r for r in attacks if r["verdict"] != "SAFE"]

    per_technique: dict[str, dict] = {}
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in attacks:
        groups[row["technique"]].append(row)
    for technique, rows in groups.items():
        n_blocked = sum(r["verdict"] == "BLOCK" for r in rows)
        per_technique[technique] = {"total": len(rows), "blocked": n_blocked,
                                    "block_rate": _rate(n_blocked, len(rows))}

    return {
        "data": report.get("data", "?"),
        "layers": report.get("layers", "?"),
        "attacks": len(attacks),
        "benign": len(benign),
        "attacks_blocked": len(blocked),
        "attacks_flagged": len(flagged),
        "attack_block_rate": _rate(len(blocked), len(attacks)),
        "attack_flag_rate": _rate(len(flagged), len(attacks)),
        "benign_blocked": sum(r["verdict"] == "BLOCK" for r in benign),
        "benign_flagged": sum(r["verdict"] != "SAFE" for r in benign),
        "per_technique": per_technique,
        "misses": [r for r in attacks if r["verdict"] != "BLOCK"],
    }


def _pct(value: float) -> str:
    return f"{value:.1%}"


def _cell(text: str) -> str:
    return "`" + text.replace("\n", "\\n").replace("|", "\\|").replace("`", "'") + "`"


def render_markdown(before: dict, after: dict) -> str:
    lines = [
        "# Validator before / after",
        "",
        f"Baseline: `{before['layers']}` layer. After: `{after['layers']}` layer. "
        f"Data set: `{after['data']}`.",
        "",
        "| Metric | Before | After |",
        "| --- | --- | --- |",
        f"| Attacks blocked | {before['attacks_blocked']}/{before['attacks']} "
        f"({_pct(before['attack_block_rate'])}) | {after['attacks_blocked']}/{after['attacks']} "
        f"({_pct(after['attack_block_rate'])}) |",
        f"| Attacks flagged | {before['attacks_flagged']}/{before['attacks']} "
        f"({_pct(before['attack_flag_rate'])}) | {after['attacks_flagged']}/{after['attacks']} "
        f"({_pct(after['attack_flag_rate'])}) |",
        f"| Benign blocked | {before['benign_blocked']}/{before['benign']} | "
        f"{after['benign_blocked']}/{after['benign']} |",
        f"| Benign flagged | {before['benign_flagged']}/{before['benign']} | "
        f"{after['benign_flagged']}/{after['benign']} |",
        "",
        "## Per technique (attack block rate)",
        "",
        "| Technique | Before | After |",
        "| --- | --- | --- |",
    ]
    techniques = sorted(set(before["per_technique"]) | set(after["per_technique"]))
    for technique in techniques:
        b = before["per_technique"].get(technique)
        a = after["per_technique"].get(technique)
        b_text = f"{b['blocked']}/{b['total']} ({_pct(b['block_rate'])})" if b else "-"
        a_text = f"{a['blocked']}/{a['total']} ({_pct(a['block_rate'])})" if a else "-"
        lines.append(f"| {technique} | {b_text} | {a_text} |")

    lines += ["", f"## Attacks still not blocked after ({len(after['misses'])})", ""]
    if after["misses"]:
        lines += ["| ID | Technique | Verdict | Command |", "| --- | --- | --- | --- |"]
        lines += [f"| {m['id']} | {m['technique']} | {m['verdict']} | {_cell(m['command'])} |"
                  for m in after["misses"]]
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--baseline", type=Path,
                        default=ROOT / "benchmarks" / "validator_baseline.json")
    parser.add_argument("--after", type=Path,
                        default=ROOT / "benchmarks" / "validator_after.json")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "benchmarks" / "validator_comparison.md")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for path in (args.baseline, args.after):
        if not path.is_file():
            print(f"error: file not found: {path}")
            return 2
    before = summarise(json.loads(args.baseline.read_text(encoding="utf-8")))
    after = summarise(json.loads(args.after.read_text(encoding="utf-8")))
    markdown = render_markdown(before, after)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
