"""Tests for scripts/eval_accuracy.py in --mock mode. The model is never loaded."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "eval_accuracy.py"
_spec = importlib.util.spec_from_file_location("eval_accuracy", SCRIPT)
evalacc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(evalacc)

ROWS = [
    {"id": "e1", "request": "list files", "reference_command": "ls -la",
     "category": "file_search", "expected_risk": "SAFE", "safe_to_run": True},
    {"id": "e2", "request": "delete build", "reference_command": "rm -rf build",
     "category": "dangerous", "expected_risk": "WARN", "safe_to_run": False},
    {"id": "e3", "request": "wipe root", "reference_command": "rm -rf /",
     "category": "dangerous", "expected_risk": "BLOCK", "safe_to_run": False},
]


def _write_dataset(tmp_path: Path) -> Path:
    path = tmp_path / "prompts.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in ROWS) + "\n", encoding="utf-8")
    return path


def test_normalise_is_flag_order_insensitive():
    assert evalacc.normalise("ls -la") == evalacc.normalise("ls -al")
    assert evalacc.normalise("rm -rf x") == evalacc.normalise("rm -fr x")
    assert evalacc.normalise('grep  -i   "foo"  f') == evalacc.normalise('grep -i foo f')


def test_evaluate_with_reference_engine_is_all_exact():
    engine = evalacc.ReferenceEngine(ROWS)
    results = evalacc.evaluate(ROWS, engine)
    assert all(r["exact_match"] for r in results)
    # The reference verdicts match the data set's expected_risk.
    assert all(r["verdict_agreement"] for r in results)


def test_aggregate_counts():
    report = evalacc.aggregate(evalacc.evaluate(ROWS, evalacc.ReferenceEngine(ROWS)))
    assert report["total"] == 3
    assert report["exact_match_rate"] == 1.0
    assert report["per_category"]["dangerous"]["total"] == 2


def test_main_mock_writes_outputs(tmp_path):
    out = tmp_path / "eval_results.json"
    grading = tmp_path / "manual_grading.csv"
    code = evalacc.main(["--mock", "--data", str(_write_dataset(tmp_path)),
                         "--out", str(out), "--grading", str(grading)])
    assert code == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert len(report["results"]) == 3
    assert out.with_suffix(".md").is_file()
    header = grading.read_text(encoding="utf-8").splitlines()[0]
    assert header.startswith("request,generated,reference")


def test_load_rows_rejects_missing_fields(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"id": "x", "request": "y"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        evalacc.load_rows(bad)


def test_repo_dataset_shape():
    rows = evalacc.load_rows(Path(__file__).resolve().parents[1] / "eval" / "prompts.jsonl")
    assert len(rows) >= 100
    assert len({r["id"] for r in rows}) == len(rows)
    flagged = [r for r in rows if r["expected_risk"] in ("WARN", "BLOCK")]
    assert len(flagged) >= 10
