"""Sandboxed preview of a command (Linux only).

A preview runs a command against a throwaway *copy* of the current directory so
the user can see what it would do before confirming it for real. The working
copy is writable; the rest of the host is not reachable (or is read-only), there
is no network, and a hard timeout kills the command.

Backends, in order of preference:

- **bwrap** (bubblewrap): a user-namespace sandbox. The whole filesystem is bound
  read-only, the working copy is bound read-write, networking is unshared.
- **docker**: a throwaway container with only the working copy bind-mounted at
  ``/work``, ``--network none`` and cpu/memory caps. The host filesystem is not
  mounted, so it is not reachable at all.
- none: if neither is installed, the preview is skipped with a clear message. It is
  never silently skipped and never silently run for real.

This reduces risk; it is **not** a security boundary against a determined attacker
(bubblewrap namespaces are not a full VM). BLOCK commands are never previewed.

Everything here is unit-testable with the process runner and the executor injected,
so the tests pass without bwrap or Docker installed.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sagecli.executor import ensure_linux

DEFAULT_TIMEOUT = 5.0
DEFAULT_SIZE_LIMIT_MB = 50
DEFAULT_DOCKER_IMAGE = "debian:stable-slim"
_OUTPUT_LIMIT = 4000  # characters of stdout/stderr kept in the result

# A process runner: (args, timeout) -> object with returncode, stdout, stderr.
Runner = Callable[[list[str], float], subprocess.CompletedProcess[str]]


@dataclass
class PreviewResult:
    """What a sandboxed preview produced."""

    backend: str | None
    ran: bool = False
    returncode: int | None = None
    timed_out: bool = False
    stdout: str = ""
    stderr: str = ""
    created: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    skipped_reason: str | None = None


def available_backend() -> str | None:
    """Return the preferred installed backend name, or None."""
    if shutil.which("bwrap"):
        return "bwrap"
    if shutil.which("docker"):
        return "docker"
    return None


def _default_runner(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def _dir_size(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            total += path.stat().st_size
    return total


def _snapshot(root: Path) -> dict[str, str]:
    """Map each file's relative path to a digest of its contents."""
    snapshot: dict[str, str] = {}
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            digest = hashlib.sha1(path.read_bytes()).hexdigest()
            snapshot[str(path.relative_to(root))] = digest
    return snapshot


def _diff(before: dict[str, str], after: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    created = sorted(p for p in after if p not in before)
    deleted = sorted(p for p in before if p not in after)
    modified = sorted(p for p in before if p in after and before[p] != after[p])
    return created, modified, deleted


def _bwrap_args(work: Path, command: str) -> list[str]:
    return [
        "bwrap",
        "--ro-bind", "/", "/",
        "--dev", "/dev",
        "--proc", "/proc",
        "--bind", str(work), str(work),
        "--chdir", str(work),
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--", "/bin/bash", "-c", command,
    ]


def _docker_args(work: Path, command: str, image: str) -> list[str]:
    return [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", "256m",
        "--cpus", "1",
        "--pids-limit", "256",
        "-v", f"{work}:/work:rw",
        "-w", "/work",
        image,
        "bash", "-c", command,
    ]


def _build_args(backend: str, work: Path, command: str) -> list[str]:
    if backend == "bwrap":
        return _bwrap_args(work, command)
    if backend == "docker":
        image = os.environ.get("SAGE_SANDBOX_IMAGE", DEFAULT_DOCKER_IMAGE)
        return _docker_args(work, command, image)
    raise ValueError(f"unknown sandbox backend: {backend}")


def _truncate(text: str) -> str:
    if len(text) <= _OUTPUT_LIMIT:
        return text
    return text[:_OUTPUT_LIMIT] + "\n... (output truncated)"


def preview(
    command: str,
    cwd: str | os.PathLike[str] | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    size_limit_mb: int = DEFAULT_SIZE_LIMIT_MB,
    backend: str | None = None,
    runner: Runner | None = None,
) -> PreviewResult:
    """Run `command` in a sandbox against a copy of `cwd` and report the effect.

    `backend` and `runner` are injectable so the flow can be tested without a real
    sandbox. Raises `UnsupportedPlatformError` on non-Linux platforms.
    """
    ensure_linux()
    backend = backend or available_backend()
    if backend is None:
        return PreviewResult(None, skipped_reason=(
            "No sandbox backend found. Install bubblewrap (bwrap) or Docker to use --preview."))

    source = Path(cwd) if cwd is not None else Path.cwd()
    size_mb = _dir_size(source) / (1024 * 1024)
    if size_mb > size_limit_mb:
        return PreviewResult(backend, skipped_reason=(
            f"Directory is {size_mb:.0f} MB, above the {size_limit_mb} MB preview limit."))

    runner = runner or _default_runner
    temp_root = Path(tempfile.mkdtemp(prefix="sage-preview-"))
    work = temp_root / "work"
    try:
        shutil.copytree(source, work, symlinks=True, ignore=shutil.ignore_patterns(".git"))
        before = _snapshot(work)
        args = _build_args(backend, work, command)
        result = PreviewResult(backend, ran=True)
        try:
            completed = runner(args, timeout)
        except subprocess.TimeoutExpired as exc:
            result.timed_out = True
            result.returncode = 124
            result.stdout = _truncate(_as_text(exc.stdout))
            result.stderr = _truncate(_as_text(exc.stderr))
        else:
            result.returncode = completed.returncode
            result.stdout = _truncate(completed.stdout or "")
            result.stderr = _truncate(completed.stderr or "")
        after = _snapshot(work)
        result.created, result.modified, result.deleted = _diff(before, after)
        return result
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)
