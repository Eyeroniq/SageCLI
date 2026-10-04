"""Configuration: model location, generation settings, execution limits, allowlists."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

MODEL_ENV_VAR = "SAGE_MODEL_PATH"
TIMEOUT_ENV_VAR = "SAGE_TIMEOUT"
MODEL_FILENAME = "Phi-3-mini-4k-instruct-q4.gguf"
DEFAULT_MODEL_PATH = Path("models") / MODEL_FILENAME
DOWNLOAD_SCRIPT = "scripts/download_model.sh"

DEFAULT_TIMEOUT_SECONDS = 60


def _default_threads() -> int:
    return os.cpu_count() or 4


@dataclass(frozen=True)
class GenerationSettings:
    """Settings passed to llama.cpp. Kept small: one short command is the whole answer."""

    temperature: float = 0.1
    top_p: float = 0.9
    max_tokens: int = 96
    explain_max_tokens: int = 64
    n_ctx: int = 1024
    n_threads: int = field(default_factory=_default_threads)
    seed: int = 42


def resolve_model_path(cli_value: str | os.PathLike[str] | None = None) -> Path:
    """Pick the model path: `--model` flag, then $SAGE_MODEL_PATH, then the default."""
    if cli_value:
        return Path(cli_value).expanduser()
    env_value = os.environ.get(MODEL_ENV_VAR)
    if env_value:
        return Path(env_value).expanduser()
    return DEFAULT_MODEL_PATH


def resolve_timeout(cli_value: float | None = None) -> float:
    """Execution timeout: `--timeout` flag, then $SAGE_TIMEOUT, then the default."""
    if cli_value is not None:
        return float(cli_value)
    env_value = os.environ.get(TIMEOUT_ENV_VAR)
    if env_value:
        try:
            return float(env_value)
        except ValueError:
            pass
    return float(DEFAULT_TIMEOUT_SECONDS)


def load_allowlist(path: str | os.PathLike[str]) -> frozenset[str]:
    """Read an allowlist file: one binary name per line, `#` starts a comment.

    Paths are reduced to their basename, so `/usr/bin/ls` and `ls` are the same entry.
    """
    names: set[str] = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry:
            names.add(entry.rsplit("/", 1)[-1])
    return frozenset(names)
