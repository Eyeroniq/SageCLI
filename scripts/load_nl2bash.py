"""Convert the public NL2Bash dataset into SageCLI's prompts.jsonl format (optional).

NL2Bash (https://github.com/TellinaTool/nl2bash) ships parallel files: natural-
language descriptions and their Bash commands, one per line. This loader zips them
into rows with the fields eval_accuracy.py expects. The dataset is NOT vendored into
this repository; download it yourself and cite it. `expected_risk` is filled in from
the validator's own verdict (so it is a starting point, not ground truth), and
`safe_to_run` defaults to false because these commands are not curated for a fixture.

Usage:
    python scripts/load_nl2bash.py --nl all.nl --cm all.cm --out eval/nl2bash.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sagecli.validator import validate


def convert(nl_path: Path, cm_path: Path, limit: int | None = None) -> list[dict]:
    requests = nl_path.read_text(encoding="utf-8").splitlines()
    commands = cm_path.read_text(encoding="utf-8").splitlines()
    if len(requests) != len(commands):
        raise ValueError(f"line count mismatch: {len(requests)} requests, {len(commands)} commands")
    rows = []
    for index, (request, command) in enumerate(zip(requests, commands, strict=True), start=1):
        request, command = request.strip(), command.strip()
        if not request or not command:
            continue
        rows.append({
            "id": f"nl2bash-{index:05d}",
            "request": request,
            "reference_command": command,
            "category": "nl2bash",
            "expected_risk": validate(command).risk.name,
            "safe_to_run": False,
        })
        if limit and len(rows) >= limit:
            break
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--nl", type=Path, required=True, help="file of natural-language requests")
    parser.add_argument("--cm", type=Path, required=True, help="file of Bash commands")
    parser.add_argument("--out", type=Path, required=True, help="output JSONL path")
    parser.add_argument("--limit", type=int, default=None, help="keep at most this many rows")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for path in (args.nl, args.cm):
        if not path.is_file():
            print(f"error: file not found: {path}", file=sys.stderr)
            return 2
    rows = convert(args.nl, args.cm, args.limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
