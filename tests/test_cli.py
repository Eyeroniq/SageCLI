"""CLI tests with a fake engine and a fake executor: nothing is generated or run for real."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from sagecli import __version__, cli, executor, sandbox

runner = CliRunner()


@pytest.fixture
def runs(monkeypatch: pytest.MonkeyPatch, fake_engine):
    """Patch the engine factory and the executor; return the list of executed commands."""
    executed: list[str] = []
    monkeypatch.setattr(cli, "make_engine", lambda model: fake_engine)
    monkeypatch.setattr(cli.executor, "is_linux", lambda: True)

    def fake_run(command: str, timeout: float = 60.0):
        executed.append(command)
        return executor.ExecutionResult(returncode=0)

    monkeypatch.setattr(cli.executor, "run_command", fake_run)
    return executed


def invoke(*args: str, input: str | None = None):
    return runner.invoke(cli.app, list(args), input=input)


def test_version() -> None:
    result = invoke("--version")
    assert result.exit_code == 0
    assert __version__ in result.output


def test_empty_request_is_usage_error(runs) -> None:
    result = invoke()
    assert result.exit_code == cli.EXIT_USAGE
    assert runs == []


def test_unquoted_words_are_joined(runs, fake_engine) -> None:
    invoke("--dry-run", "list", "all", "files")
    assert fake_engine.requests == ["list all files"]


def test_dry_run_never_executes(runs, fake_engine) -> None:
    result = invoke("--dry-run", "--yes", "list files")
    assert result.exit_code == 0
    assert "ls -la" in result.output and "SAFE" in result.output
    assert "Dry run" in result.output
    assert runs == []


def test_safe_requires_confirmation(runs) -> None:
    declined = invoke("list files", input="n\n")
    assert declined.exit_code == cli.EXIT_ABORTED and runs == []
    accepted = invoke("list files", input="y\n")
    assert accepted.exit_code == 0 and runs == ["ls -la"]


def test_yes_skips_prompt_for_safe(runs) -> None:
    result = invoke("--yes", "list files")
    assert result.exit_code == 0 and runs == ["ls -la"]


def test_block_is_never_executed_even_with_yes(runs, fake_engine) -> None:
    fake_engine.command = "rm -rf /"
    result = invoke("--yes", "delete everything", input="yes\n")
    assert result.exit_code == cli.EXIT_BLOCKED
    assert "BLOCK" in result.output
    assert runs == []


def test_warn_requires_typing_yes(runs, fake_engine) -> None:
    fake_engine.command = "sudo apt update"
    assert invoke("update packages", input="y\n").exit_code == cli.EXIT_ABORTED
    assert invoke("--yes", "update packages", input="\n").exit_code == cli.EXIT_ABORTED
    assert runs == []
    result = invoke("--yes", "update packages", input="yes\n")
    assert result.exit_code == 0 and runs == ["sudo apt update"]


def test_explain_prints_explanation(runs) -> None:
    result = invoke("--dry-run", "--explain", "list files")
    assert "Lists all files" in result.output


def test_preview_runs_sandbox(runs, monkeypatch) -> None:
    captured: list[str] = []

    def fake_preview(command: str):
        captured.append(command)
        return sandbox.PreviewResult(backend="bwrap", ran=True, returncode=0,
                                     stdout="listing\n", created=["new.txt"])

    monkeypatch.setattr(cli.sandbox, "preview", fake_preview)
    result = invoke("--dry-run", "--preview", "list files")
    assert result.exit_code == 0
    assert captured == ["ls -la"]
    assert "Preview [bwrap]" in result.output
    assert "created: new.txt" in result.output


def test_preview_blocked_command_is_not_previewed(runs, fake_engine, monkeypatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(cli.sandbox, "preview", lambda command: called.append(command))
    fake_engine.command = "rm -rf /"
    result = invoke("--preview", "--dry-run", "wipe", )
    assert result.exit_code == cli.EXIT_BLOCKED
    assert called == []


def test_missing_model_message(monkeypatch, tmp_path: Path) -> None:
    result = invoke("--dry-run", "--model", str(tmp_path / "nope.gguf"), "list files")
    assert result.exit_code == cli.EXIT_USAGE
    assert "download_model.sh" in result.output


def test_refuses_to_execute_off_linux(runs, monkeypatch) -> None:
    monkeypatch.setattr(cli.executor, "is_linux", lambda: False)
    result = invoke("--yes", "list files")
    assert result.exit_code == cli.EXIT_UNSUPPORTED_PLATFORM
    assert runs == []


def test_allowlist_blocks_unlisted_binary(runs, fake_engine, tmp_path: Path) -> None:
    allow = tmp_path / "allow.txt"
    allow.write_text("ls\n", encoding="utf-8")
    assert invoke("--yes", "--allowlist", str(allow), "list").exit_code == 0
    fake_engine.command = "cat notes.txt"
    result = invoke("--yes", "--allowlist", str(allow), "show notes")
    assert result.exit_code == cli.EXIT_BLOCKED
    assert runs == ["ls -la"]


def test_empty_generation_aborts(runs, fake_engine) -> None:
    fake_engine.command = ""
    result = invoke("--yes", "???")
    assert result.exit_code == cli.EXIT_ABORTED and runs == []
