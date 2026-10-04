"""Shared fixtures. The LLM is always mocked: no model file or llama-cpp-python is needed."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest


@dataclass
class FakeEngine:
    """Stands in for sagecli.engine.Engine in CLI tests."""

    command: str = "ls -la"
    explanation: str = "Lists all files, including hidden ones."
    requests: list[str] = field(default_factory=list)

    def generate_command(self, request: str) -> str:
        self.requests.append(request)
        return self.command

    def explain(self, command: str) -> str:
        return self.explanation


class FakeLlama:
    """Mimics the llama_cpp.Llama __call__ API."""

    def __init__(self, text: str = "ls -la", tokens: int = 3) -> None:
        self.text = text
        self.tokens = tokens
        self.calls: list[dict] = []

    def __call__(self, prompt: str, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        return {"choices": [{"text": self.text}], "usage": {"completion_tokens": self.tokens}}


@pytest.fixture
def fake_engine() -> FakeEngine:
    return FakeEngine()
