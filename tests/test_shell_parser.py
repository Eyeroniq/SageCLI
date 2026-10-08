"""Tests for the bashlex structural parser. Nothing is executed."""

from __future__ import annotations

from sagecli.shell_parser import parse_script


def _programs(commands) -> list[str]:
    return [c.program for c in commands]


def test_simple_command_argv_and_program() -> None:
    result = parse_script("rm -rf /tmp/x")
    assert result.ok
    assert result.commands[0].argv == ("rm", "-rf", "/tmp/x")
    assert result.commands[0].program == "rm"


def test_quotes_and_backslashes_are_removed() -> None:
    result = parse_script('"rm" -rf "$HOME"')
    assert result.ok
    assert result.commands[0].argv == ("rm", "-rf", "$HOME")


def test_pipeline_stages_are_grouped() -> None:
    result = parse_script("echo x | xargs rm")
    assert result.ok
    assert any([s.program for s in pipeline] == ["echo", "xargs"]
               for pipeline in result.pipelines)


def test_recurses_into_command_substitution() -> None:
    result = parse_script("ls $(whoami)")
    assert "whoami" in _programs(result.commands)


def test_reparses_bash_c_payload() -> None:
    result = parse_script('bash -c "rm -rf /"')
    rms = [c for c in result.commands if c.program == "rm"]
    assert rms and "/" in rms[0].argv


def test_reparses_find_exec_payload() -> None:
    result = parse_script("find . -exec rm -rf {} ;")
    assert "rm" in _programs(result.commands)


def test_redirect_is_captured() -> None:
    result = parse_script("echo x > /etc/passwd")
    redirects = result.commands[0].redirects
    assert any(r.type in (">", ">>") and r.target == "/etc/passwd" for r in redirects)


def test_malformed_input_reports_malformed() -> None:
    assert parse_script(")").status == "malformed"


def test_unsupported_syntax_is_not_malformed() -> None:
    # Arithmetic expansion is not supported by bashlex; it must not look malformed.
    assert parse_script("echo $((1 + 2))").status != "malformed"
