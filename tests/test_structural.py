"""Tests for the structural (bashlex) validator layer and its combination with regex."""

from __future__ import annotations

import pytest

from sagecli.validator import Risk, validate

# Attacks the regex layer alone misses but the structural layer catches:
# path canonicalisation, arguments arriving through xargs, and $ENV mapping.
STRUCTURAL_BLOCK = [
    "rm -rf /.",
    "rm -rf //",
    "rm -rf /tmp/..",
    "rm -rf /var/lib",
    "rm -rf $(pwd)/..",
    'echo "-rf /" | xargs rm',
    'echo "if=/dev/zero of=/dev/sda" | xargs dd',
    'echo "-R 777 /" | xargs chmod',
    'echo "-9 1" | xargs kill',
    "echo /dev/sda | xargs shred",
    "printf '%s\\n' / | xargs -I{} rm -rf {}",
    "perl -e 'system(\"rm -rf $ENV{HOME}\")'",
]

# Benign look-alikes that must NOT be blocked by the structural layer.
STRUCTURAL_NOT_BLOCKED = [
    ("rm -rf /tmp/mydir", Risk.WARN),
    ("rm -rf ./build", Risk.WARN),
    ('rm -rf "$HOME/.cache/pip"', Risk.WARN),
    ("mkfs.ext4 ./disk.img", Risk.WARN),
    ("echo a b | xargs echo", Risk.SAFE),
    ("ls | xargs wc -l", Risk.SAFE),
    ("chmod -R 755 ./site", Risk.SAFE),
]


@pytest.mark.parametrize("command", STRUCTURAL_BLOCK)
def test_structural_layer_blocks(command: str) -> None:
    result = validate(command)
    assert result.risk is Risk.BLOCK, (command, result.rules)


@pytest.mark.parametrize(("command", "risk"), STRUCTURAL_NOT_BLOCKED)
def test_structural_layer_does_not_overblock(command: str, risk: Risk) -> None:
    result = validate(command)
    assert result.risk is risk, (command, result.rules)


def test_malformed_command_raises_to_warn() -> None:
    result = validate(")")
    assert result.risk is Risk.WARN
    assert "could_not_parse_structure" in result.rules


def test_mkfs_on_a_regular_file_is_only_warn() -> None:
    assert validate("mkfs.ext4 ./disk.img").risk is Risk.WARN
    assert validate("mkfs.ext4 /dev/sda1").risk is Risk.BLOCK


def test_layers_select_which_checks_run() -> None:
    # /var/lib is reachable only through the structural canonicalisation layer.
    assert validate("rm -rf /var/lib", layers="regex").risk is Risk.WARN
    assert validate("rm -rf /var/lib", layers="structural").risk is Risk.BLOCK
    assert validate("rm -rf /var/lib", layers="both").risk is Risk.BLOCK
