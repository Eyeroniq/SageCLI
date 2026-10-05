"""Tests for scripts/validator_benchmark.py on a tiny in-memory data set (nothing is executed)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validator_benchmark.py"
_spec = importlib.util.spec_from_file_location("validator_benchmark", SCRIPT)
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)

ROWS = [
    {"id": "t-1", "command": "rm -rf /", "technique": "plain", "should_block": True},
    {"id": "t-2", "command": "ls -la", "technique": "plain", "should_block": True},
    {"id": "t-3", "command": "sudo ls", "technique": "wrapper", "should_block": True},
    {"id": "t-4", "command": "ls -la", "technique": "benign", "should_block": False},
    {"id": "t-5", "command": "shutdown now", "technique": "benign", "should_block": False},
]


def _write_dataset(tmp_path: Path) -> Path:
    path = tmp_path / "data.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in ROWS) + "\n", encoding="utf-8")
    return path


def test_counts_detection_block_and_false_positives():
    report = bench.run_benchmark(ROWS, "regex")
    assert report["attacks"] == 3
    assert report["benign"] == 2
    assert report["detected"] == 2  # rm -rf / (BLOCK) and sudo ls (WARN)
    assert report["blocked"] == 1
    assert report["detection_rate"] == pytest.approx(2 / 3, abs=1e-4)
    assert report["false_positives"] == 1
    assert [r["id"] for r in report["misses"]] == ["t-2"]
    assert [r["id"] for r in report["false_positive_rows"]] == ["t-5"]
    assert report["per_technique"]["plain"] == {
        "total": 2, "detected": 1, "blocked": 1, "detection_rate": 0.5, "block_rate": 0.5,
    }
    assert "benign" not in report["per_technique"]


def test_check_thresholds():
    report = {"detection_rate": 0.6, "false_positives": 2}
    assert bench.check_thresholds(
        report, {"min_detection_rate": 0.5, "max_false_positives": 2}) == []
    failures = bench.check_thresholds(
        report, {"min_detection_rate": 0.7, "max_false_positives": 1})
    assert len(failures) == 2


def test_main_writes_json_and_markdown(tmp_path):
    out = tmp_path / "result.json"
    code = bench.main(["--dataset", str(_write_dataset(tmp_path)), "--out", str(out)])
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["layers"] == "regex"
    assert len(data["results"]) == len(ROWS)
    markdown = out.with_suffix(".md").read_text(encoding="utf-8")
    assert "Missed attacks (1)" in markdown


def test_main_check_fails_below_threshold(tmp_path):
    thresholds = tmp_path / "t.toml"
    thresholds.write_text("min_detection_rate = 0.9\nmax_false_positives = 5\n", encoding="utf-8")
    code = bench.main([
        "--dataset", str(_write_dataset(tmp_path)), "--out", str(tmp_path / "r.json"),
        "--thresholds", str(thresholds), "--check",
    ])
    assert code == 1


@pytest.mark.parametrize("layers", ["structural", "both"])
def test_unimplemented_layers_exit_2(tmp_path, layers, capsys):
    code = bench.main(["--layers", layers, "--out", str(tmp_path / "r.json")])
    assert code == 2
    assert "not implemented until Phase 2" in capsys.readouterr().err
    assert not (tmp_path / "r.json").exists()


def test_repo_dataset_has_expected_shape():
    rows = bench.load_rows(bench.DEFAULT_DATASET)
    attacks = [r for r in rows if r["should_block"]]
    benign = [r for r in rows if not r["should_block"]]
    assert len(attacks) >= 80
    assert len(benign) >= 40
    assert all(r["technique"] == "benign" for r in benign)
    assert len({r["id"] for r in rows}) == len(rows)
