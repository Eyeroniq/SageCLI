from __future__ import annotations

from pathlib import Path

import pytest
from conftest import FakeLlama

from sagecli import config, engine, prompts


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ls -la", "ls -la"),
        ("  ls -la  \n", "ls -la"),
        ("```bash\nls -la\n```", "ls -la"),
        ("```\ndf -h\n```\nThis shows disk space.", "df -h"),
        ("`du -sh .`", "du -sh ."),
        ("Command: wc -l app.log", "wc -l app.log"),
        ("command: wc -l app.log", "wc -l app.log"),
        ("$ ls", "ls"),
        ("ls -la\ncd /tmp", "ls -la"),
        ("\n\nfind . -name '*.py'\nExplanation: finds files", "find . -name '*.py'"),
        ("ls<|end|>garbage", "ls"),
        ("", ""),
        ("```\n```", ""),
    ],
)
def test_clean_command(raw: str, expected: str) -> None:
    assert engine.clean_command(raw) == expected


def test_prompt_uses_phi3_chat_format() -> None:
    prompt = prompts.build_command_prompt("show disk usage")
    assert prompt.startswith("<|user|>\n" + prompts.SYSTEM_INSTRUCTION)
    assert prompt.endswith("<|user|>\nRequest: show disk usage<|end|>\n<|assistant|>\n")
    assert prompt.count("<|assistant|>") == len(prompts.FEW_SHOT_EXAMPLES) + 1
    assert 5 <= len(prompts.FEW_SHOT_EXAMPLES) <= 8


def test_model_is_loaded_lazily_and_once(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"fake")
    fake = FakeLlama(text="```bash\ndf -h\n```")
    calls: list[Path] = []

    def factory(path, settings):
        calls.append(path)
        return fake

    eng = engine.Engine(model, llm_factory=factory)
    assert not eng.loaded and calls == []
    assert eng.generate_command("free disk space") == "df -h"
    assert eng.generate_command("again") == "df -h"
    assert calls == [model]
    kwargs = fake.calls[0]
    assert kwargs["temperature"] <= 0.2
    assert kwargs["max_tokens"] <= 128
    assert "<|end|>" in kwargs["stop"]


def test_missing_model_gives_friendly_error(tmp_path: Path) -> None:
    eng = engine.Engine(tmp_path / "missing.gguf", llm_factory=lambda p, s: FakeLlama())
    with pytest.raises(engine.ModelNotFoundError) as info:
        eng.generate_command("anything")
    assert "download_model.sh" in str(info.value)


def test_explain_returns_first_line(tmp_path: Path) -> None:
    model = tmp_path / "m.gguf"
    model.write_bytes(b"x")
    eng = engine.Engine(model, llm_factory=lambda p, s: FakeLlama(text="Shows disk usage.\nMore"))
    assert eng.explain("df -h") == "Shows disk usage."


def test_model_path_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(config.MODEL_ENV_VAR, raising=False)
    assert config.resolve_model_path() == config.DEFAULT_MODEL_PATH
    monkeypatch.setenv(config.MODEL_ENV_VAR, "/opt/m.gguf")
    assert config.resolve_model_path() == Path("/opt/m.gguf")
    assert config.resolve_model_path("/cli/m.gguf") == Path("/cli/m.gguf")


def test_generation_settings_defaults() -> None:
    settings = config.GenerationSettings()
    assert settings.n_threads >= 1
    assert settings.n_ctx <= 2048
    assert settings.temperature <= 0.2


def test_allowlist_file(tmp_path: Path) -> None:
    path = tmp_path / "allow.txt"
    path.write_text("# comment\nls\n/usr/bin/grep  # trailing\n\n", encoding="utf-8")
    assert config.load_allowlist(path) == frozenset({"ls", "grep"})
