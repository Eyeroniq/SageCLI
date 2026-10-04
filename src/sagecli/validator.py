"""Safety layer: classify a Bash command as SAFE, WARN or BLOCK.

Initial version with a handful of rules; the full rule set arrives in step 1.2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum


class Risk(IntEnum):
    SAFE = 0
    WARN = 1
    BLOCK = 2


@dataclass(frozen=True)
class ValidationResult:
    risk: Risk
    rules: tuple[str, ...] = ()
    reason: str = "No risky pattern found."
    segments: tuple[str, ...] = field(default=())

    @property
    def blocked(self) -> bool:
        return self.risk is Risk.BLOCK


_RULES: tuple[tuple[str, Risk, re.Pattern[str], str], ...] = (
    ("rm_recursive_root", Risk.BLOCK, re.compile(r"\brm\s+-\w*r\w*\s+(?:/|~|\*)(?:\s|$)"),
     "Recursive deletion of the root, home or every file."),
    ("mkfs", Risk.BLOCK, re.compile(r"\bmkfs(?:\.\w+)?\b"), "Formats a filesystem."),
    ("sudo", Risk.WARN, re.compile(r"^\s*sudo\b"), "Runs with root privileges."),
)


def validate(command: str, allowlist: frozenset[str] | None = None) -> ValidationResult:
    matched = [(name, risk, reason) for name, risk, pattern, reason in _RULES
               if pattern.search(command)]
    words = command.split()
    if allowlist is not None and (not words or words[0].rsplit("/", 1)[-1] not in allowlist):
        matched.append(("not_in_allowlist", Risk.BLOCK, "Command is not in the allowlist."))
    if not matched:
        return ValidationResult(Risk.SAFE, segments=(command,))
    top = max(risk for _, risk, _ in matched)
    reasons = [reason for _, risk, reason in matched if risk == top]
    return ValidationResult(top, tuple(name for name, _, _ in matched), " ".join(reasons),
                            (command,))
