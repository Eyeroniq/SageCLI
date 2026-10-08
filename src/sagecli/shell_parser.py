"""Structural shell parsing with bashlex.

This module turns a Bash command string into a flat list of *simple commands*
(a program name, its arguments and its redirections) plus the *pipelines* they
belong to. It recurses into every place where more commands can hide: pipelines,
lists (``;`` ``&&`` ``||`` ``&``), compounds (``if`` / ``while`` / subshells),
command and process substitutions (``$(...)``, backticks, ``<(...)``), the string
payloads of ``bash -c`` / ``sh -c`` / ``eval`` / here-strings to a shell, and the
payload of ``find -exec``.

``bashlex`` is a real Bash parser, so it undoes quoting and backslash tricks for
us: ``bashlex`` reports the ``word`` of ``r""m`` as ``rm`` and of ``"$HOME"`` as
``$HOME``. The validator's structural layer (``sagecli.validator``) consumes the
result; the regex layer stays as a second, independent check.

``bashlex`` cannot parse all of Bash. ``parse_script`` never raises: it returns a
``ParseResult`` whose ``status`` is one of:

- ``"ok"``        - parsed; ``commands`` / ``pipelines`` are populated;
- ``"malformed"`` - a genuine syntax error (unbalanced quotes, stray operator);
- ``"unsupported"``- valid Bash the parser does not implement (e.g. ``$((...))``,
  ``[[ ... ]]``); the structural layer then falls back to the regex layer;
- ``"unavailable"``- ``bashlex`` is not installed.

The validator treats ``"malformed"`` as a reason to raise the verdict to WARN, but
treats ``"unsupported"`` as a silent fall-back, so that common constructs the
parser lacks (arithmetic especially) do not flood safe commands with warnings.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field

try:  # bashlex is a core dependency, but degrade gracefully if it is missing.
    import bashlex
    import bashlex.errors

    _PARSING_ERROR: type[Exception] = bashlex.errors.ParsingError
except Exception:  # pragma: no cover - only hit when bashlex is absent
    bashlex = None  # type: ignore[assignment]
    _PARSING_ERROR = SyntaxError

_MAX_DEPTH = 8


@dataclass(frozen=True)
class Redirect:
    """One redirection attached to a simple command."""

    type: str  # the operator, e.g. ">", ">>", "<", "<<<"
    target: str  # the word it points at (a filename, or the here-string body)


@dataclass(frozen=True)
class SimpleCommand:
    """A single command: its words (program first) and its redirections."""

    argv: tuple[str, ...]
    redirects: tuple[Redirect, ...] = ()

    @property
    def program(self) -> str:
        """Basename of the command name, or ``""`` for an empty command."""
        return posixpath.basename(self.argv[0]) if self.argv else ""


@dataclass
class ParseResult:
    """Outcome of parsing one command string."""

    status: str  # "ok" | "malformed" | "unsupported" | "unavailable"
    commands: list[SimpleCommand] = field(default_factory=list)
    pipelines: list[list[SimpleCommand]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok"


# Programs whose string arguments are themselves commands to re-parse.
_SHELLS = frozenset({"sh", "bash", "dash", "zsh", "ksh", "mksh", "ash", "busybox"})


def parse_script(command: str, _depth: int = 0) -> ParseResult:
    """Parse ``command`` into simple commands and pipelines. Never raises."""
    if bashlex is None:
        return ParseResult("unavailable")
    if _depth > _MAX_DEPTH:
        return ParseResult("ok")
    try:
        trees = bashlex.parse(command)
    except _PARSING_ERROR:
        return ParseResult("malformed")
    except Exception:
        # Valid Bash the parser does not support (e.g. $((...)), [[ ]]) raises
        # NotImplementedError; fall back to the regex layer, no structural check.
        return ParseResult("unsupported")

    result = ParseResult("ok")
    for tree in trees:
        _walk(tree, result, pipeline=None, depth=_depth)
    return result


def _walk(node: object, result: ParseResult, pipeline: list | None, depth: int) -> None:
    """Recursively collect simple commands from a bashlex AST node."""
    kind = getattr(node, "kind", None)
    if kind == "command":
        _handle_command(node, result, pipeline, depth)
    elif kind == "pipeline":
        stages: list[SimpleCommand] = []
        result.pipelines.append(stages)
        for part in getattr(node, "parts", []):
            if getattr(part, "kind", None) != "pipe":
                _walk(part, result, stages, depth)
    elif kind in ("list", "compound", "if", "for", "while", "until", "case",
                  "pattern", "function"):
        for part in getattr(node, "parts", []):
            _walk(part, result, None, depth)
        for part in getattr(node, "list", []):  # compound carries .list
            _walk(part, result, None, depth)
    elif kind in ("commandsubstitution", "processsubstitution"):
        inner = getattr(node, "command", None)
        if inner is not None:
            _walk(inner, result, None, depth)
    elif kind == "word":
        for part in getattr(node, "parts", []):
            _walk(part, result, None, depth)


def _handle_command(node: object, result: ParseResult, pipeline: list | None,
                    depth: int) -> None:
    words: list[str] = []
    redirects: list[Redirect] = []
    for part in getattr(node, "parts", []):
        pkind = getattr(part, "kind", None)
        if pkind == "word":
            words.append(getattr(part, "word", ""))
            for sub in getattr(part, "parts", []):
                _walk(sub, result, None, depth)  # $(...) etc. inside a word
        elif pkind == "redirect":
            redirects.append(_build_redirect(part, result, depth))
        # assignments (VAR=value prefixes) are not part of argv

    command = SimpleCommand(tuple(words), tuple(redirects))
    if command.argv:
        result.commands.append(command)
        if pipeline is not None:
            pipeline.append(command)
        else:
            result.pipelines.append([command])
    _reparse_payloads(command, redirects, result, depth)


def _build_redirect(part: object, result: ParseResult, depth: int) -> Redirect:
    rtype = str(getattr(part, "type", ""))
    output = getattr(part, "output", None)
    target = ""
    if hasattr(output, "word"):
        target = getattr(output, "word", "")
        for sub in getattr(output, "parts", []):
            _walk(sub, result, None, depth)
    elif output is not None:
        target = str(output)
    return Redirect(rtype, target)


def _reparse_payloads(command: SimpleCommand, redirects: list[Redirect],
                      result: ParseResult, depth: int) -> None:
    """Re-parse strings that the shell will execute as further commands."""
    prog, args = command.program, list(command.argv[1:])
    payloads: list[str] = []

    if prog in _SHELLS or prog == "su":
        for i, arg in enumerate(args):
            if arg.startswith("-") and "c" in arg.lstrip("-") and i + 1 < len(args):
                payloads.append(args[i + 1])
                break
        payloads += [r.target for r in redirects if r.type == "<<<"]
    elif prog == "eval":
        payloads.append(" ".join(args))
    elif prog == "find":
        for i, arg in enumerate(args):
            if arg in ("-exec", "-execdir", "-ok") and i + 1 < len(args):
                rest = args[i + 1:]
                end = next((j for j, a in enumerate(rest) if a in (";", "+", "\\;")),
                           len(rest))
                payloads.append(" ".join(rest[:end]))

    for payload in payloads:
        if payload.strip():
            nested = parse_script(payload, _depth=depth + 1)
            result.commands.extend(nested.commands)
            result.pipelines.extend(nested.pipelines)
