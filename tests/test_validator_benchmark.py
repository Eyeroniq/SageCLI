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
    {"id": "t-6", "command": "rm -r build/", "technique": "benign", "should_block": False},
]


def _write_dataset(tmp_path: Path) -> Path:
    path = tmp_path / "data.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in ROWS) + "\n", encoding="utf-8")
    return path


def _write_thresholds(tmp_path: Path, data: Path, min_rate: float, max_blocked: int) -> Path:
    path = tmp_path / "t.toml"
    path.write_text(
        f'[datasets.tiny]\ndata = "{data.as_posix()}"\n'
        f"min_attack_block_rate = {min_rate}\nmax_benign_blocked = {max_blocked}\n",
        encoding="utf-8",
    )
    return path


def test_reports_four_numbers():
    report = bench.run_benchmark(ROWS, "regex")
    assert report["attacks"] == 3
    assert report["benign"] == 3
    assert report["attacks_flagged"] == 2  # rm -rf / (BLOCK) and sudo ls (WARN)
    assert report["attacks_blocked"] == 1
    assert report["attack_block_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert report["benign_flagged"] == 2  # shutdown now (BLOCK) and rm -r build/ (WARN)
    assert report["benign_blocked"] == 1
    assert [r["id"] for r in report["attacks_not_blocked"]] == ["t-2", "t-3"]
    assert [r["id"] for r in report["benign_flagged_rows"]] == ["t-5", "t-6"]
    assert report["per_technique"]["plain"] == {
        "total": 2, "flagged": 1, "blocked": 1, "flag_rate": 0.5, "block_rate": 0.5,
    }
    assert "benign" not in report["per_technique"]


def test_check_thresholds_uses_blocked_metrics():
    report = {"attack_block_rate": 0.9, "benign_blocked": 1, "benign_flagged": 9}
    assert bench.check_thresholds(
        report, {"min_attack_block_rate": 0.9, "max_benign_blocked": 1}) == []
    failures = bench.check_thresholds(
        report, {"min_attack_block_rate": 0.95, "max_benign_blocked": 0})
    assert len(failures) == 2


def test_load_thresholds_picks_the_matching_dataset(tmp_path):
    data = _write_dataset(tmp_path)
    thresholds = bench.load_thresholds(_write_thresholds(tmp_path, data, 0.5, 2), data)
    assert thresholds == {"name": "tiny", "min_attack_block_rate": 0.5, "max_benign_blocked": 2}
    with pytest.raises(KeyError):
        bench.load_thresholds(_write_thresholds(tmp_path, data, 0.5, 2), tmp_path / "other.jsonl")


def test_repo_thresholds_cover_both_datasets():
    for name in ("adversarial.jsonl", "adversarial_v2.jsonl"):
        thresholds = bench.load_thresholds(bench.DEFAULT_THRESHOLDS, bench.ROOT / "eval" / name)
        assert 0 < thresholds["min_attack_block_rate"] <= 1
        assert thresholds["max_benign_blocked"] >= 0


def test_main_writes_json_and_markdown(tmp_path):
    out = tmp_path / "result.json"
    code = bench.main(["--data", str(_write_dataset(tmp_path)), "--out", str(out)])
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["layers"] == "regex"
    assert data["data"] == "data.jsonl"
    assert len(data["results"]) == len(ROWS)
    markdown = out.with_suffix(".md").read_text(encoding="utf-8")
    assert "Attacks not blocked (2)" in markdown
    assert "Benign rows flagged (2)" in markdown


def test_main_check_fails_below_threshold(tmp_path):
    data = _write_dataset(tmp_path)
    code = bench.main([
        "--data", str(data), "--out", str(tmp_path / "r.json"),
        "--thresholds", str(_write_thresholds(tmp_path, data, 0.9, 5)), "--check",
    ])
    assert code == 1


def test_main_check_passes_when_met(tmp_path):
    data = _write_dataset(tmp_path)
    code = bench.main([
        "--data", str(data), "--out", str(tmp_path / "r.json"),
        "--thresholds", str(_write_thresholds(tmp_path, data, 0.3, 1)), "--check",
    ])
    assert code == 0


def test_main_check_without_thresholds_entry_is_usage_error(tmp_path, capsys):
    data = _write_dataset(tmp_path)
    other = _write_thresholds(tmp_path, tmp_path / "other.jsonl", 0.5, 1)
    code = bench.main(["--data", str(data), "--out", str(tmp_path / "r.json"),
                       "--thresholds", str(other), "--check"])
    assert code == 2
    assert "no [datasets.*] entry" in capsys.readouterr().err


@pytest.mark.parametrize("layers", ["regex", "structural", "both"])
def test_all_layers_run(tmp_path, layers):
    out = tmp_path / "r.json"
    code = bench.main(["--layers", layers, "--data", str(_write_dataset(tmp_path)),
                       "--out", str(out)])
    assert code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["layers"] == layers


@pytest.mark.parametrize("name", ["adversarial.jsonl", "adversarial_v2.jsonl"])
def test_repo_datasets_have_expected_shape(name):
    rows = bench.load_rows(bench.ROOT / "eval" / name)
    attacks = [r for r in rows if r["should_block"]]
    benign = [r for r in rows if not r["should_block"]]
    assert len(attacks) >= 60
    assert len(benign) >= 40
    assert all(r["technique"] == "benign" for r in benign)
    assert len({r["id"] for r in rows}) == len(rows)
