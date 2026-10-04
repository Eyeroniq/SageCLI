"""Run a confirmed command with /bin/bash and a timeout. Linux only."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from dataclasses import dataclass

TIMEOUT_EXIT_CODE = 124  # same convention as coreutils `timeout`


class UnsupportedPlatformError(RuntimeError):
    def __init__(self, platform: str) -> None:
        super().__init__(
            f"Refusing to execute on platform '{platform}': SageCLI only runs commands on Linux. "
            "Use --dry-run to only generate and check commands."
        )


@dataclass(frozen=True)
class ExecutionResult:
    returncode: int
    timed_out: bool = False


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def ensure_linux() -> None:
    if not is_linux():
        raise UnsupportedPlatformError(sys.platform)


def run_command(command: str, timeout: float = 60.0, shell: str = "/bin/bash") -> ExecutionResult:
    """Run `command` with `shell -c`, streaming output to the terminal.

    The child gets its own process group so that, on timeout, the whole tree
    (not only the shell) is killed.
    """
    ensure_linux()
    process = subprocess.Popen([shell, "-c", command], start_new_session=True)
    try:
        return ExecutionResult(returncode=process.wait(timeout=timeout))
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:  # pragma: no cover - already gone
            pass
        process.wait()
        return ExecutionResult(returncode=TIMEOUT_EXIT_CODE, timed_out=True)
    except KeyboardInterrupt:
        try:
            os.killpg(process.pid, signal.SIGINT)
        except ProcessLookupError:  # pragma: no cover
            pass
        process.wait()
        raise
