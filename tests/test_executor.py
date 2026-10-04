"""Executor tests. Nothing is ever really executed: subprocess.Popen is replaced."""

from __future__ import annotations

import subprocess

import pytest

from sagecli import executor


class FakePopen:
    instances: list[FakePopen] = []
    raise_timeout = False

    def __init__(self, args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.pid = 4242
        FakePopen.instances.append(self)

    def wait(self, timeout=None):
        if FakePopen.raise_timeout and timeout is not None:
            raise subprocess.TimeoutExpired(self.args, timeout)
        return 0


@pytest.fixture
def fake_popen(monkeypatch: pytest.MonkeyPatch):
    FakePopen.instances = []
    FakePopen.raise_timeout = False
    monkeypatch.setattr(executor.subprocess, "Popen", FakePopen)
    return FakePopen


@pytest.mark.parametrize("platform", ["win32", "darwin", "cygwin"])
def test_refuses_on_non_linux(monkeypatch, fake_popen, platform: str) -> None:
    monkeypatch.setattr(executor.sys, "platform", platform)
    with pytest.raises(executor.UnsupportedPlatformError):
        executor.run_command("echo hi")
    assert fake_popen.instances == []


def test_runs_with_bash_on_linux(monkeypatch, fake_popen) -> None:
    monkeypatch.setattr(executor.sys, "platform", "linux")
    result = executor.run_command("echo hi", timeout=5)
    assert result.returncode == 0 and not result.timed_out
    (proc,) = fake_popen.instances
    assert proc.args == ["/bin/bash", "-c", "echo hi"]
    assert proc.kwargs["start_new_session"] is True


def test_timeout_kills_process_group(monkeypatch, fake_popen) -> None:
    monkeypatch.setattr(executor.sys, "platform", "linux")
    fake_popen.raise_timeout = True
    killed: list[tuple[int, int]] = []
    monkeypatch.setattr(executor.os, "killpg", lambda pid, sig: killed.append((pid, sig)),
                        raising=False)
    monkeypatch.setattr(executor.signal, "SIGKILL", 9, raising=False)
    result = executor.run_command("sleep 100", timeout=1)
    assert result.timed_out and result.returncode == executor.TIMEOUT_EXIT_CODE
    assert killed == [(4242, 9)]
