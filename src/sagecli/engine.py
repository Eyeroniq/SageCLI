"""LLM engine: loads Phi-3 Mini (GGUF, CPU) once and turns requests into Bash commands."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sagecli import prompts
from sagecli.config import DOWNLOAD_SCRIPT, GenerationSettings, resolve_model_path


class EngineError(RuntimeError):
    """Base class for errors the CLI reports as friendly messages."""


class ModelNotFoundError(EngineError):
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(
            f"Model file not found: {path}\n"
            f"Download it with:  bash {DOWNLOAD_SCRIPT}\n"
            "or point to an existing file with --model PATH or the SAGE_MODEL_PATH variable."
        )


class LLMUnavailableError(EngineError):
    def __init__(self) -> None:
        super().__init__(
            "llama-cpp-python is not installed. Install the model runtime with:\n"
            '  pip install -e ".[llm]"'
        )


@dataclass(frozen=True)
class Completion:
    text: str
    completion_tokens: int
    seconds: float


# Factory signature: (model_path, settings) -> object with llama-cpp's __call__ API.
LLMFactory = Callable[[Path, GenerationSettings], Any]


def _llama_factory(model_path: Path, settings: GenerationSettings) -> Any:
    try:
        from llama_cpp import Llama  # imported lazily: optional dependency, slow import
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise LLMUnavailableError() from exc
    return Llama(
        model_path=str(model_path),
        n_ctx=settings.n_ctx,
        n_threads=settings.n_threads,
        seed=settings.seed,
        verbose=False,
    )


_FENCE_RE = re.compile(r"```[\w+-]*[ \t]*\n?(.*?)(?:```|$)", re.DOTALL)
_PREFIX_RE = re.compile(r"^(?:command|bash command|bash|shell|answer)\s*:\s*", re.IGNORECASE)
_PROMPT_SIGN_RE = re.compile(r"^[$#]\s+")


def clean_command(raw: str) -> str:
    """Reduce raw model output to a single command line.

    Strips special tokens, code fences, backticks, "Command:" style prefixes and
    shell prompt signs, then keeps the first non-empty line only.
    """
    text = raw
    for token in prompts.STOP_SEQUENCES:
        text = text.split(token, 1)[0]
    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1)
    for line in text.splitlines():
        line = line.strip()
        line = _PREFIX_RE.sub("", line)
        line = _PROMPT_SIGN_RE.sub("", line)
        if len(line) >= 2 and line[0] == line[-1] == "`":
            line = line.strip("`")
        line = line.strip().strip("`").strip()
        if line:
            return line
    return ""


def clean_explanation(raw: str) -> str:
    """First non-empty line of the model's explanation."""
    text = raw
    for token in prompts.STOP_SEQUENCES:
        text = text.split(token, 1)[0]
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


class Engine:
    """Lazily loads the model on first use and keeps it for the life of the process."""

    def __init__(
        self,
        model_path: str | Path | None = None,
        settings: GenerationSettings | None = None,
        llm_factory: LLMFactory | None = None,
    ) -> None:
        self.model_path = resolve_model_path(model_path)
        self.settings = settings or GenerationSettings()
        self._factory = llm_factory or _llama_factory
        self._llm: Any = None
        self.load_seconds: float | None = None

    @property
    def loaded(self) -> bool:
        return self._llm is not None

    def load(self) -> None:
        if self._llm is not None:
            return
        if not self.model_path.is_file():
            raise ModelNotFoundError(self.model_path)
        start = time.perf_counter()
        self._llm = self._factory(self.model_path, self.settings)
        self.load_seconds = time.perf_counter() - start

    def complete(self, prompt: str, max_tokens: int) -> Completion:
        self.load()
        start = time.perf_counter()
        response = self._llm(
            prompt,
            max_tokens=max_tokens,
            temperature=self.settings.temperature,
            top_p=self.settings.top_p,
            stop=list(prompts.STOP_SEQUENCES),
        )
        seconds = time.perf_counter() - start
        text = response["choices"][0]["text"]
        tokens = int(response.get("usage", {}).get("completion_tokens", 0))
        return Completion(text=text, completion_tokens=tokens, seconds=seconds)

    def generate_command(self, request: str) -> str:
        """Turn a plain-English request into one Bash command (may be "" if the model fails)."""
        completion = self.complete(prompts.build_command_prompt(request), self.settings.max_tokens)
        return clean_command(completion.text)

    def explain(self, command: str) -> str:
        """One-line plain-English explanation of `command`."""
        completion = self.complete(
            prompts.build_explain_prompt(command), self.settings.explain_max_tokens
        )
        return clean_explanation(completion.text)


_default_engine: Engine | None = None


def generate_command(request: str) -> str:
    """Module-level convenience using a process-wide engine with the default model path."""
    global _default_engine
    if _default_engine is None:
        _default_engine = Engine()
    return _default_engine.generate_command(request)
