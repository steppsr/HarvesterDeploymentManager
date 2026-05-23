from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from harvester_deploy.domain.models import (
    DeployJob,
    Harvester,
    JobState,
    LogCallback,
    StepResult,
    StepStatus,
)
from harvester_deploy.persistence.config import default_recipe_path
from harvester_deploy.ssh.client import SshSession

# Run from chia_root. set +e — pkill returns non-zero when no processes exist.
_CHIA_STOP = """\
set +e
if [ -f ./activate ]; then
  . ./activate
  chia stop -d all
  deactivate 2>/dev/null
elif [ -x venv/bin/chia ]; then
  venv/bin/chia stop -d all
elif command -v chia >/dev/null 2>&1; then
  chia stop -d all
else
  echo "No chia CLI found; stopping by process name if still running"
  # Use -x not -f: -f matches this script's own ssh bash command line and kills it.
  pkill -x chia_harvester 2>/dev/null
  pkill -x chia_daemon 2>/dev/null
fi
exit 0
"""

_CHIA_VERSION = """\
if [ -f ./activate ]; then
  . ./activate
  chia version
  deactivate 2>/dev/null || true
elif [ -x venv/bin/chia ]; then
  venv/bin/chia version
elif command -v chia >/dev/null 2>&1; then
  chia version
else
  echo "unknown (venv not installed yet)"
fi
"""


@dataclass
class RecipeStep:
    id: str
    description: str


@dataclass
class Recipe:
    name: str
    description: str
    steps: list[RecipeStep]


def load_recipe(name: str = "chia-upgrade-default") -> Recipe:
    path = default_recipe_path(name)
    if not path.is_file():
        raise FileNotFoundError(f"Recipe not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    steps = [
        RecipeStep(id=s["id"], description=s.get("description", s["id"]))
        for s in raw["steps"]
    ]
    return Recipe(
        name=raw.get("name", name),
        description=raw.get("description", ""),
        steps=steps,
    )


async def _chia_version(session: SshSession) -> str:
    try:
        _, stdout, _ = await session.run(
            f"{session.shell_prelude()}{_CHIA_VERSION}",
            check=False,
            timeout=60,
        )
        lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
        for line in reversed(lines):
            if line and not line.startswith("unknown"):
                return line
        return lines[-1] if lines else "unknown"
    except Exception:
        return "unknown"


def _git_tree_ready_for_install(status_output: str) -> bool:
    """Allow install when tracked tree is clean; mozilla-ca/ alone is OK (recreated by submodules)."""
    if "nothing to commit, working tree clean" in status_output:
        return True
    blocked = ("modified:", "Changes not staged", "Changes to be committed", "unmerged:")
    if any(marker in status_output for marker in blocked):
        return False
    if (
        "mozilla-ca/" in status_output
        and "nothing added to commit but untracked files present" in status_output
    ):
        return True
    return False


def _chia_init_needs_ssl_fix(output: str) -> bool:
    text = output.lower()
    return "fix-ssl-permissions" in text or "unprotected ssl" in text


async def _skip_git_steps(session: SshSession) -> bool:
    """True when a prior run removed venvs but never finished install.sh."""
    _, stdout, _ = await session.run(
        f"{session.shell_prelude()}"
        "if [ ! -f ./activate ] && [ ! -d venv ] && [ ! -d .venv ]; then echo skip; else echo full; fi",
        check=True,
        timeout=30,
    )
    return stdout.strip() == "skip"


async def _run_step(
    session: SshSession,
    harvester: Harvester,
    step_id: str,
    *,
    dry_run: bool,
) -> StepResult:
    if dry_run:
        return StepResult(step_id=step_id, status=StepStatus.SKIPPED, message="dry-run")

    branch = harvester.git_branch
    prelude = session.shell_prelude()
    activate = harvester.activate_cmd

    try:
        if step_id == "precheck":
            await session.run(f"{prelude}test -d . && git rev-parse --is-inside-work-tree", check=True)

        elif step_id == "backup_config":
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            await session.run(
                f"{prelude}"
                f"mkdir -p ~/chia-backups/{ts} && "
                f"cp -a config.yaml ~/chia-backups/{ts}/ 2>/dev/null || "
                f"echo 'warning: config.yaml not found, continuing'",
                check=True,
            )

        elif step_id == "stop_services":
            root = harvester.chia_root
            code, _, _ = await session.run(
                f"cd {root}\n{_CHIA_STOP}",
                check=False,
                timeout=120,
            )
            if code not in (0, None) and code != -1:
                raise RuntimeError(f"stop_services failed (exit {code})")

        elif step_id == "remove_venvs":
            await session.run(
                f"{prelude}rm -rf venv .penv .venv",
                check=True,
            )

        elif step_id == "git_update":
            await session.run(
                f"{prelude}"
                f"git fetch && git checkout {branch} && "
                f"git reset --hard FETCH_HEAD --recurse-submodules && "
                f"git submodule update --init --recursive",
                check=True,
                timeout=300,
            )

        elif step_id == "git_clean_check":
            # Submodule cleanup first; submodule update can recreate mozilla-ca/.
            await session.run(
                f"{prelude}"
                f"git submodule foreach --recursive git reset --hard && "
                f"git submodule foreach --recursive git clean -fd && "
                f"git submodule update --init --recursive && "
                f"git clean -fd && "
                f"rm -rf mozilla-ca",
                check=True,
                timeout=300,
            )
            _, stdout, _ = await session.run(f"{prelude}git status", check=True)
            if not _git_tree_ready_for_install(stdout):
                raise RuntimeError(
                    "Git working tree is not ready for install. "
                    f"git status:\n{stdout}"
                )

        elif step_id == "install":
            await session.run(
                f"{prelude}sh install.sh",
                check=True,
                timeout=3600,
            )

        elif step_id == "chia_init":
            _, stdout, stderr = await session.run(
                f"{prelude}{activate}\nchia init\n",
                check=True,
                timeout=300,
            )
            combined = f"{stdout}\n{stderr}"
            if _chia_init_needs_ssl_fix(combined):
                await session.run(
                    f"{prelude}{activate}\nchia init --fix-ssl-permissions\n",
                    check=True,
                    timeout=120,
                )
                return StepResult(
                    step_id=step_id,
                    status=StepStatus.SUCCESS,
                    message="chia init completed; SSL permissions fixed",
                )

        elif step_id == "start_harvester":
            await session.run(
                f"{prelude}{activate}\nchia start harvester\n",
                check=True,
                timeout=120,
            )

        elif step_id == "postcheck":
            version = await _chia_version(session)
            return StepResult(
                step_id=step_id,
                status=StepStatus.SUCCESS,
                message=f"chia version: {version}",
                output=version,
            )

        else:
            raise ValueError(f"Unknown step: {step_id}")

        return StepResult(step_id=step_id, status=StepStatus.SUCCESS)

    except Exception as exc:
        return StepResult(
            step_id=step_id,
            status=StepStatus.FAILED,
            message=str(exc),
        )


async def run_upgrade(
    harvester: Harvester,
    recipe: Recipe,
    *,
    dry_run: bool = False,
    on_log: LogCallback | None = None,
) -> DeployJob:
    job = DeployJob(
        harvester=harvester,
        state=JobState.CONNECTING,
        started_at=datetime.now(timezone.utc),
    )

    if dry_run:
        job.state = JobState.RUNNING
        for step in recipe.steps:
            job.steps.append(
                StepResult(step_id=step.id, status=StepStatus.SKIPPED, message="dry-run")
            )
        job.state = JobState.SUCCESS
        job.finished_at = datetime.now(timezone.utc)
        return job

    session = SshSession(harvester, on_log=on_log)
    try:
        await session.connect()
        job.state = JobState.RUNNING
        job.version_before = await _chia_version(session)
        skip_git = await _skip_git_steps(session)
        if skip_git and on_log:
            on_log(
                harvester.id,
                "Recovery mode: no activate/venv — skipping git_update and git_clean_check",
            )

        for step in recipe.steps:
            if skip_git and step.id in ("git_update", "git_clean_check"):
                job.steps.append(
                    StepResult(
                        step_id=step.id,
                        status=StepStatus.SKIPPED,
                        message="recovery: git already updated; venv removed",
                    )
                )
                if on_log:
                    on_log(harvester.id, f"--- step: {step.id} — skipped (recovery)")
                continue
            if on_log:
                on_log(harvester.id, f"--- step: {step.id} — {step.description}")
            result = await _run_step(session, harvester, step.id, dry_run=False)
            job.steps.append(result)
            if result.status == StepStatus.FAILED:
                job.state = JobState.FAILED
                job.error = f"Step '{result.step_id}' failed: {result.message}"
                break
        else:
            job.version_after = await _chia_version(session)
            job.state = JobState.SUCCESS

    except Exception as exc:
        job.state = JobState.FAILED
        job.error = str(exc)
    finally:
        await session.close()
        job.finished_at = datetime.now(timezone.utc)

    return job


async def run_status(harvester: Harvester, on_log: LogCallback | None = None) -> dict:
    session = SshSession(harvester, on_log=on_log)
    try:
        await session.connect()
        version = await _chia_version(session)
        _, stdout, _ = await session.run(
            session.with_venv("chia farm summary 2>/dev/null | head -5 || true"),
            check=False,
            timeout=60,
        )
        return {"id": harvester.id, "host": harvester.host, "version": version, "summary": stdout.strip()}
    finally:
        await session.close()


async def run_doctor(harvester: Harvester, on_log: LogCallback | None = None) -> dict:
    checks: dict[str, str] = {"id": harvester.id, "host": harvester.host}
    session = SshSession(harvester, on_log=on_log)
    try:
        await session.connect()
        checks["ssh"] = "ok"
        prelude = session.shell_prelude()
        try:
            await session.run(f"{prelude}test -d .", check=True)
            checks["chia_root"] = "ok"
        except Exception as exc:
            checks["chia_root"] = f"fail: {exc}"

        try:
            _, stdout, _ = await session.run(f"{prelude}git status", check=True)
            if "nothing to commit, working tree clean" in stdout:
                checks["git_clean"] = "ok"
            else:
                checks["git_clean"] = "dirty (upgrade may change RELEASE)"
        except Exception as exc:
            checks["git_clean"] = f"fail: {exc}"

        checks["version"] = await _chia_version(session)
        return checks
    except Exception as exc:
        checks["ssh"] = f"fail: {exc}"
        return checks
    finally:
        await session.close()


async def test_ssh(harvester: Harvester, on_log: LogCallback | None = None) -> bool:
    session = SshSession(harvester, on_log=on_log)
    try:
        await session.connect()
        _, stdout, _ = await session.run("hostname", check=True, timeout=30)
        if on_log:
            on_log(harvester.id, f"hostname: {stdout.strip()}")
        return True
    except Exception:
        return False
    finally:
        await session.close()
