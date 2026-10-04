"""Command-line interface: `sage "<plain-English request>"`."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from sagecli import __version__, executor
from sagecli.config import load_allowlist, resolve_timeout
from sagecli.engine import Engine, EngineError
from sagecli.validator import Risk, ValidationResult, validate

# Exit codes (a command that actually runs returns its own exit code instead).
EXIT_OK = 0
EXIT_ABORTED = 1
EXIT_USAGE = 2
EXIT_BLOCKED = 3
EXIT_UNSUPPORTED_PLATFORM = 4

RISK_COLORS = {Risk.SAFE: typer.colors.GREEN, Risk.WARN: typer.colors.YELLOW,
               Risk.BLOCK: typer.colors.RED}

app = typer.Typer(
    add_completion=False,
    help="Turn a plain-English request into one Bash command, check it, and run it only "
    "after you confirm. Runs fully offline with a local model.",
)


def make_engine(model_path: Path | None) -> Engine:
    """Engine factory; tests replace this to avoid loading a real model."""
    return Engine(model_path)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"sage {__version__}")
        raise typer.Exit()


def show_result(command: str, result: ValidationResult) -> None:
    typer.echo("Command: " + typer.style(command, bold=True))
    typer.echo("Risk:    " + typer.style(result.risk.name, fg=RISK_COLORS[result.risk], bold=True))
    if result.rules:
        typer.echo("Rules:   " + ", ".join(result.rules))
    if result.risk is not Risk.SAFE:
        typer.echo("Reason:  " + result.reason)


def confirm_execution(risk: Risk, assume_yes: bool) -> bool:
    """Apply the confirmation policy.

    SAFE: normal y/N prompt, skipped by --yes.
    WARN: the user must type `yes` in full; --yes does not skip it.
    BLOCK: never executed (callers stop before reaching this).
    """
    if risk is Risk.BLOCK:
        return False
    if risk is Risk.SAFE:
        if assume_yes:
            return True
        return typer.confirm("Run this command?", default=False)
    if assume_yes:
        typer.secho("--yes only applies to SAFE commands; confirmation is required.",
                    fg=typer.colors.YELLOW)
    answer = typer.prompt("This command is risky. Type 'yes' to run it", default="",
                          show_default=False)
    return answer.strip() == "yes"


@app.command()
def run(
    request: Annotated[
        list[str] | None, typer.Argument(help="What you want to do, in plain English.")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Generate and check the command, never run it.")
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip the confirmation prompt for SAFE commands.")
    ] = False,
    explain: Annotated[
        bool, typer.Option("--explain", help="Also print a one-line explanation.")
    ] = False,
    model: Annotated[
        Path | None,
        typer.Option("--model", help="Path to the GGUF model (default: $SAGE_MODEL_PATH or "
                     "./models/Phi-3-mini-4k-instruct-q4.gguf)."),
    ] = None,
    allowlist: Annotated[
        Path | None,
        typer.Option("--allowlist", help="File with one permitted binary per line; anything "
                     "else is blocked.", exists=True, dir_okay=False, readable=True),
    ] = None,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="Seconds before a running command is killed "
                     "(default: $SAGE_TIMEOUT or 60).", min=1),
    ] = None,
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_version_callback, is_eager=True,
                     help="Show the version and exit."),
    ] = None,
) -> None:
    """Generate one Bash command from REQUEST, check it, and run it after confirmation."""
    text = " ".join(request or []).strip()
    if not text:
        typer.secho('Describe what you want, e.g.  sage "show the 10 largest files here"',
                    fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USAGE)

    allowed = load_allowlist(allowlist) if allowlist else None

    engine = make_engine(model)
    try:
        command = engine.generate_command(text)
    except EngineError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USAGE) from exc

    if not command:
        typer.secho("The model did not produce a command. Try rephrasing the request.",
                    fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_ABORTED)

    result = validate(command, allowlist=allowed)
    show_result(command, result)
    if explain:
        typer.echo("Explain: " + (engine.explain(command) or "(no explanation produced)"))

    if result.risk is Risk.BLOCK:
        typer.secho("Blocked: this command will not be executed.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(EXIT_BLOCKED)
    if dry_run:
        typer.echo("Dry run: not executed.")
        raise typer.Exit(EXIT_OK)
    if not executor.is_linux():
        typer.secho("Execution is only supported on Linux. Use --dry-run on this platform.",
                    fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_UNSUPPORTED_PLATFORM)
    if not confirm_execution(result.risk, yes):
        typer.echo("Aborted.")
        raise typer.Exit(EXIT_ABORTED)

    outcome = executor.run_command(command, timeout=resolve_timeout(timeout))
    if outcome.timed_out:
        typer.secho(f"Command timed out and was killed (exit {outcome.returncode}).",
                    fg=typer.colors.RED, err=True)
    raise typer.Exit(outcome.returncode)


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
