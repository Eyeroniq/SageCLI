"""Prompt construction for Phi-3 Mini (chat format: <|user|> ... <|end|> <|assistant|>)."""

from __future__ import annotations

SYSTEM_INSTRUCTION = (
    "You convert a request into exactly ONE Bash command for Linux. "
    "Reply with the command only: no explanation, no markdown, no backticks, no prompt sign. "
    "Prefer simple, read-only, non-destructive commands. Never use sudo."
)

# (request, command) pairs. Short, varied, and all non-destructive.
FEW_SHOT_EXAMPLES: tuple[tuple[str, str], ...] = (
    ("list all files including hidden ones", "ls -la"),
    (
        "show the 10 largest files in this folder",
        "find . -maxdepth 1 -type f -exec du -h {} + | sort -rh | head -n 10",
    ),
    ("find all python files modified in the last 7 days", 'find . -name "*.py" -mtime -7'),
    ("how much free disk space do I have", "df -h"),
    ("count the lines in app.log", "wc -l app.log"),
    ("search for the word TODO in all files under this directory", 'grep -rn "TODO" .'),
    ("show the processes using the most memory", "ps aux --sort=-%mem | head -n 10"),
    ("compress the folder reports into reports.tar.gz", "tar -czf reports.tar.gz reports"),
)

EXPLAIN_INSTRUCTION = (
    "Explain in one short sentence what this Bash command does. "
    "Reply with the sentence only."
)

STOP_SEQUENCES: tuple[str, ...] = ("<|end|>", "<|endoftext|>", "<|user|>", "<|assistant|>")


def _turn(role: str, content: str) -> str:
    return f"<|{role}|>\n{content}<|end|>\n"


def build_command_prompt(request: str) -> str:
    """Few-shot Phi-3 prompt whose answer is a single Bash command.

    Phi-3 Mini has no dedicated system role in its original template, so the
    instruction is placed in the first user turn.
    """
    parts: list[str] = []
    for index, (example_request, example_command) in enumerate(FEW_SHOT_EXAMPLES):
        content = f"Request: {example_request}"
        if index == 0:
            content = f"{SYSTEM_INSTRUCTION}\n\n{content}"
        parts.append(_turn("user", content))
        parts.append(_turn("assistant", example_command))
    parts.append(_turn("user", f"Request: {request.strip()}"))
    parts.append("<|assistant|>\n")
    return "".join(parts)


def build_explain_prompt(command: str) -> str:
    """Prompt asking for a one-sentence explanation of `command`."""
    return _turn("user", f"{EXPLAIN_INSTRUCTION}\n\nCommand: {command}") + "<|assistant|>\n"
