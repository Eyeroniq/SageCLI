"""Tests for scripts/compare_validator_runs.py. Reads two JSON files, runs nothing."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compare_validator_runs.py"
_spec = importlib.util.spec_from_file_location("compare_validator_runs", SCRIPT)
compare = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compare)


def _report(layers: str, rows: list[dict]) -> dict:
    return {"layers": layers, "data": "demo.jsonl", "results": rows}


BASELINE_ROWS = [
    {"id": "a1", "technique": "rm", "command": "rm -rf /", "should_block": True,
     "verdict": "BLOCK", "rules": ["rm_recursive_dangerous_target"]},
    {"id": "a2", "technique": "xargs", "command": "echo -rf / | xargs rm",
     "should_block": True, "verdict": "WARN", "rules": ["rm_recursive"]},
    {"id": "b1", "technique": "benign", "command": "ls -la", "should_block": False,
     "verdict": "SAFE", "rules": []},
]

AFTER_ROWS = [
    {"id": "a1", "technique": "rm", "command": "rm -rf /", "should_block": True,
     "verdict": "BLOCK", "rules": ["rm_recursive_dangerous_target"]},
    {"id": "a2", "technique": "xargs", "command": "echo -rf / | xargs rm",
     "should_block": True, "verdict": "BLOCK", "rules": ["rm_recursive_dangerous_target"]},
    {"id": "b1", "technique": "benign", "command": "ls -la", "should_block": False,
     "verdict": "SAFE", "rules": []},
]


def test_summarise_recomputes_from_results():
    summary = compare.summarise(_report("regex", BASELINE_ROWS))
    assert summary["attacks"] == 2
    assert summary["attacks_blocked"] == 1
    assert summary["benign"] == 1
    assert summary["benign_blocked"] == 0
    assert [m["id"] for m in summary["misses"]] == ["a2"]
    assert summary["per_technique"]["xargs"]["block_rate"] == 0.0


def test_main_writes_before_after_table(tmp_path):
    baseline = tmp_path / "baseline.json"
    after = tmp_path / "after.json"
    out = tmp_path / "comparison.md"
    baseline.write_text(json.dumps(_report("regex", BASELINE_ROWS)), encoding="utf-8")
    after.write_text(json.dumps(_report("both", AFTER_ROWS)), encoding="utf-8")
    code = compare.main(["--baseline", str(baseline), "--after", str(after), "--out", str(out)])
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "Validator before / after" in text
    assert "Attacks blocked | 1/2" in text
    assert "| 2/2" in text  # after blocks both attacks
    assert "Attacks still not blocked after (0)" in text


def test_main_missing_file_is_usage_error(tmp_path):
    assert compare.main(["--baseline", str(tmp_path / "no.json"),
                         "--after", str(tmp_path / "no2.json")]) == 2
