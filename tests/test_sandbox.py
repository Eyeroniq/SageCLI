"""Sandbox tests. The process runner is injected, so no bwrap or Docker is needed."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from sagecli import executor, sandbox


@pytest.fixture(autouse=True)
def _force_linux(monkeypatch: pytest.MonkeyPatch):
    """Pretend we are on Linux so preview() does not refuse."""
    monkeypatch.setattr(sandbox, "ensure_linux", lambda: None)


def _make_cwd(tmp_path: Path) -> Path:
    cwd = tmp_path / "project"
    cwd.mkdir()
    (cwd / "keep.txt").write_text("original", encoding="utf-8")
    return cwd


def _work_dir(args: list[str]) -> Path:
    for arg in args:
        candidate = Path(arg)
        if candidate.name == "work" and candidate.is_dir():
            return candidate
    raise AssertionError(f"no work dir in {args}")


def test_available_backend_prefers_bwrap(monkeypatch):
    monkeypatch.setattr(sandbox.shutil, "which", lambda name: "/usr/bin/" + name)
    assert sandbox.available_backend() == "bwrap"
    monkeypatch.setattr(sandbox.shutil, "which", lambda name: "/x/docker" if name == "docker"
                        else None)
    assert sandbox.available_backend() == "docker"
    monkeypatch.setattr(sandbox.shutil, "which", lambda name: None)
    assert sandbox.available_backend() is None


def test_preview_skipped_without_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "available_backend", lambda: None)
    result = sandbox.preview("ls", cwd=_make_cwd(tmp_path))
    assert not result.ran
    assert result.skipped_reason and "bubblewrap" in result.skipped_reason


def test_preview_reports_output_and_created_file(tmp_path):
    def fake_runner(args, timeout):
        (_work_dir(args) / "new.txt").write_text("hello", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "done\n", "")

    result = sandbox.preview("touch new.txt", cwd=_make_cwd(tmp_path),
                             backend="bwrap", runner=fake_runner)
    assert result.ran and result.returncode == 0
    assert result.stdout == "done\n"
    assert result.created == ["new.txt"]
    assert result.modified == [] and result.deleted == []


def test_preview_detects_modified_and_deleted(tmp_path):
    cwd = _make_cwd(tmp_path)
    (cwd / "extra.txt").write_text("x", encoding="utf-8")

    def runner(args, timeout):
        work = _work_dir(args)
        (work / "keep.txt").write_text("changed", encoding="utf-8")
        (work / "extra.txt").unlink()
        return subprocess.CompletedProcess(args, 0, "", "")

    result = sandbox.preview("...", cwd=cwd, backend="bwrap", runner=runner)
    assert result.modified == ["keep.txt"]
    assert result.deleted == ["extra.txt"]


def test_preview_timeout(tmp_path):
    def fake_runner(args, timeout):
        raise subprocess.TimeoutExpired(args, timeout, output="partial", stderr="")

    result = sandbox.preview("sleep 100", cwd=_make_cwd(tmp_path),
                             backend="bwrap", runner=fake_runner)
    assert result.timed_out and result.returncode == 124
    assert result.stdout == "partial"


def test_preview_refuses_large_directory(tmp_path):
    result = sandbox.preview("ls", cwd=_make_cwd(tmp_path), backend="bwrap",
                             size_limit_mb=0, runner=lambda a, t: None)
    assert not result.ran and "limit" in result.skipped_reason


def test_preview_refuses_non_linux(tmp_path, monkeypatch):
    def boom() -> None:
        raise executor.UnsupportedPlatformError("win32")

    monkeypatch.setattr(sandbox, "ensure_linux", boom)
    with pytest.raises(executor.UnsupportedPlatformError):
        sandbox.preview("ls", cwd=_make_cwd(tmp_path), backend="bwrap")


def test_build_args_shapes():
    bwrap = sandbox._build_args("bwrap", Path("/tmp/w"), "ls")
    assert bwrap[0] == "bwrap" and "--unshare-all" in bwrap
    assert bwrap[-3:] == ["/bin/bash", "-c", "ls"]
    docker = sandbox._build_args("docker", Path("/tmp/w"), "ls")
    assert docker[:3] == ["docker", "run", "--rm"] and "--network" in docker
    assert docker[docker.index("--network") + 1] == "none"


@pytest.mark.sandbox
def test_real_bwrap_preview(tmp_path):
    """Integration test: only runs when bwrap is actually installed."""
    if not shutil.which("bwrap"):
        pytest.skip("bwrap not installed")
    cwd = _make_cwd(tmp_path)
    result = sandbox.preview("echo hi > out.txt", cwd=cwd, backend="bwrap")
    assert result.ran and result.returncode == 0
    assert "out.txt" in result.created
    assert not (cwd / "out.txt").exists()  # the real directory is untouched
