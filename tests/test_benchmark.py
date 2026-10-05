"""Tests for scripts/benchmark.py with a fake model (no GGUF file or llama-cpp-python)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from conftest import FakeLlama

from sagecli.engine import Engine

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark.py"
_spec = importlib.util.spec_from_file_location("latency_benchmark", SCRIPT)
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)


def test_there_are_20_fixed_prompts():
    assert len(bench.PROMPTS) == 20
    assert len(set(bench.PROMPTS)) == 20


def test_percentile_nearest_rank():
    values = [float(v) for v in range(1, 21)]
    assert bench.percentile(values, 95) == 19.0
    assert bench.percentile(values, 50) == 10.0
    assert bench.percentile([3.0], 95) == 3.0


def test_run_benchmark_with_fake_model(tmp_path):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"fake")
    fake = FakeLlama(text="```bash\ndf -h\n```", tokens=4)
    engine = Engine(model, llm_factory=lambda path, settings: fake)

    report = bench.run_benchmark(engine, bench.PROMPTS[:3])

    assert report["requests"] == 3
    assert len(fake.calls) == 3
    assert report["completion_tokens"] == 12
    assert [r["command"] for r in report["runs"]] == ["df -h"] * 3
    assert report["threads"] == engine.settings.n_threads
    assert report["median_seconds"] >= 0
    assert "Latency benchmark" in bench.render_markdown(report)


def test_main_reports_missing_model(tmp_path, capsys):
    code = bench.main(["--model", str(tmp_path / "missing.gguf"), "--out", str(tmp_path / "r.md")])
    assert code == 2
    assert "Model file not found" in capsys.readouterr().err
    assert not (tmp_path / "r.md").exists()
