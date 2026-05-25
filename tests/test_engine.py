"""Recipe engine helpers."""

from __future__ import annotations

import asyncio
import sys

from harvester_deploy.domain.models import Harvester
from harvester_deploy.recipes import engine


def test_upgrade_needed_skips_when_refs_match(monkeypatch) -> None:
    harvester = Harvester(id="padme", display_name="PADME", host="padme")

    async def fake_git_head_refs(session, branch):
        return "abc12345", "abc12345", "origin/latest"

    async def fake_git_commits_behind(session, branch):
        return 2

    monkeypatch.setattr(engine, "_git_head_refs", fake_git_head_refs)
    monkeypatch.setattr(engine, "_git_commits_behind", fake_git_commits_behind)

    needed, message = asyncio.run(engine._upgrade_needed(object(), harvester))

    assert not needed
    assert "already up to date with origin/latest" in message


def test_upgrade_needed_when_head_differs_from_remote(monkeypatch) -> None:
    harvester = Harvester(id="padme", display_name="PADME", host="padme")

    async def fake_git_head_refs(session, branch):
        return "abc12345", "def67890", "origin/latest"

    async def fake_git_commits_behind(session, branch):
        return 0

    monkeypatch.setattr(engine, "_git_head_refs", fake_git_head_refs)
    monkeypatch.setattr(engine, "_git_commits_behind", fake_git_commits_behind)

    needed, message = asyncio.run(engine._upgrade_needed(object(), harvester))

    assert needed
    assert "local HEAD differs from origin/latest" in message


def test_health_summary_combinations() -> None:
    assert engine._health_summary(ping_ok=True, ssh_ok=True) == ""
    assert engine._health_summary(ping_ok=False, ssh_ok=True) == "PING failed"
    assert engine._health_summary(ping_ok=True, ssh_ok=False) == "SSH failed"
    assert (
        engine._health_summary(ping_ok=False, ssh_ok=False)
        == "PING failed; SSH failed"
    )


def test_ping_host_success(monkeypatch) -> None:
    class FakeProc:
        returncode = 0

        async def communicate(self):
            return b"reply", b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        assert args[0] == "ping"
        if sys.platform.startswith("win"):
            assert "-n" in args
        else:
            assert "-c" in args
        return FakeProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    ok, detail = asyncio.run(engine._ping_host("example"))

    assert ok is True
    assert detail == "ok"
