"""Every tracked text file must use LF line endings: no carriage returns at all.

The check reads the blobs stored in the git index (`git cat-file --batch`), not the
working tree, so it sees exactly what is committed. A file containing a lone CR is
treated as binary by git (`-text`) and is never normalised by .gitattributes, which is
how a broken validator_thresholds.toml once reached CI.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, input=data, capture_output=True,
                          check=True).stdout


def _tracked_blobs() -> list[tuple[str, bytes]]:
    """(path, content) for every file in the git index."""
    entries = []
    for record in _git("ls-files", "-s", "-z").split(b"\0"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        mode, sha, _stage = meta.split()
        if mode == b"160000":  # submodule
            continue
        entries.append((path.decode("utf-8"), sha))
    out = _git("cat-file", "--batch", data=b"".join(sha + b"\n" for _, sha in entries))
    blobs, pos = [], 0
    for path, _sha in entries:
        header_end = out.index(b"\n", pos)
        size = int(out[pos:header_end].split()[2])
        start = header_end + 1
        blobs.append((path, out[start:start + size]))
        pos = start + size + 1  # skip the newline after each object
    return blobs


def _in_git_checkout() -> bool:
    if shutil.which("git") is None:
        return False
    try:
        _git("rev-parse", "--is-inside-work-tree")
    except (subprocess.CalledProcessError, OSError):
        return False
    return True


@pytest.mark.skipif(not _in_git_checkout(), reason="needs git and a git checkout")
def test_tracked_text_files_have_no_carriage_returns():
    offenders = []
    for path, content in _tracked_blobs():
        if b"\0" in content:  # binary file
            continue
        if b"\r" in content:
            crlf = content.count(b"\r\n")
            lone = content.count(b"\r") - crlf
            offenders.append(f"{path} ({lone} lone CR, {crlf} CRLF)")
    assert not offenders, "files with carriage returns (use LF only): " + ", ".join(offenders)
