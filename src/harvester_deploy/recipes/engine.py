from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from harvester_deploy.domain.models import (
    DeployJob,
    Harvester,
    InstallMode,
    JobState,
    LogCallback,
    NodeRole,
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
  pkill -x chia_farmer 2>/dev/null
  pkill -x chia_daemon 2>/dev/null
  pkill -x chia_full_node 2>/dev/null
fi
exit 0
"""

_CHIA_VERSION_SOURCE = """\
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

_CHIA_VERSION_PACKAGE = "command -v chia >/dev/null 2>&1 && chia version || echo unknown"


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


async def _remote_path_exists(session: SshSession, path: str) -> bool:
    expanded = await session.expand_remote_path(path)
    _, stdout, _ = await session.run(
        f'if [ -d "{expanded}" ]; then echo yes; else echo no; fi',
        check=False,
        timeout=30,
    )
    line = stdout.strip().splitlines()[-1] if stdout.strip() else "no"
    return line == "yes"


async def _chia_on_path(session: SshSession) -> bool:
    _, stdout, _ = await session.run(
        "command -v chia >/dev/null 2>&1 && echo yes || echo no",
        check=False,
        timeout=30,
    )
    line = stdout.strip().splitlines()[-1] if stdout.strip() else "no"
    return line == "yes"


async def detect_install_mode(session: SshSession, harvester: Harvester) -> InstallMode:
    """Source git clone at chia_root, or package install (chia on PATH only)."""
    if await _remote_path_exists(session, harvester.chia_root):
        try:
            await _validate_chia_root(session, harvester)
            return InstallMode.SOURCE
        except RuntimeError:
            if await _chia_on_path(session):
                return InstallMode.PACKAGE
            return InstallMode.UNKNOWN
    if await _chia_on_path(session):
        _, stdout, _ = await session.run(_CHIA_VERSION_PACKAGE, check=False, timeout=30)
        ver = stdout.strip().splitlines()[-1] if stdout.strip() else ""
        if ver and "unknown" not in ver.lower():
            return InstallMode.PACKAGE
    return InstallMode.UNKNOWN


async def _run_chia_cli(
    session: SshSession,
    harvester: Harvester,
    command: str,
    *,
    mode: InstallMode | None = None,
    timeout: float = 60,
) -> tuple[int, str, str]:
    install = mode or await detect_install_mode(session, harvester)
    if install == InstallMode.SOURCE:
        script = session.with_venv(command)
    elif install == InstallMode.PACKAGE:
        script = command
    else:
        raise RuntimeError(
            f"Chia CLI not available on {harvester.host}. "
            f"No directory at {harvester.chia_root} and 'chia' not on PATH."
        )
    return await session.run(script, check=False, timeout=timeout)


async def _chia_version(session: SshSession, harvester: Harvester) -> str:
    try:
        mode = await detect_install_mode(session, harvester)
        if mode == InstallMode.SOURCE:
            _, stdout, _ = await session.run(
                f"{session.shell_prelude()}{_CHIA_VERSION_SOURCE}",
                check=False,
                timeout=60,
            )
        elif mode == InstallMode.PACKAGE:
            _, stdout, _ = await session.run(_CHIA_VERSION_PACKAGE, check=False, timeout=60)
        else:
            return "unknown"
        lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
        for line in reversed(lines):
            if line and not line.startswith("unknown"):
                return line
        return lines[-1] if lines else "unknown"
    except Exception:
        return "unknown"


_PACKAGE_DEPLOY_MSG = (
    "Detected a package install: 'chia' works on PATH but chia_root is not a git clone. "
    "This deploy recipe requires a source tree (git + install.sh). "
    "Upgrade via your OS package manager (.deb), or clone Chia to chia_root for source upgrades."
)


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


_CHIA_ROOT_HINT = (
    "This recipe requires a git clone at chia_root (typically ~/chia-blockchain) "
    "installed from source with install.sh. Nodes using only the .deb/GUI package "
    "without a source tree are not supported — set chia_root to your clone path or "
    "exclude that host from deploy targets."
)


async def _validate_chia_root(session: SshSession, harvester: Harvester) -> None:
    """Fail fast with a clear message if chia_root is missing or not a git repo."""
    root = await session.expand_remote_path(harvester.chia_root)
    _, stdout, _ = await session.run(
        f'if [ -d "{root}" ]; then echo exists; else echo missing; fi',
        check=False,
        timeout=30,
    )
    last = stdout.strip().splitlines()[-1] if stdout.strip() else "missing"
    if last != "exists":
        raise RuntimeError(
            f"chia_root does not exist: {harvester.chia_root} ({root}). {_CHIA_ROOT_HINT}"
        )

    if harvester.upgrade_mode == "git":
        _, git_out, _ = await session.run(
            f'cd "{root}" && git rev-parse --is-inside-work-tree >/dev/null 2>&1 '
            f"&& echo git_ok || echo not_git",
            check=False,
            timeout=30,
        )
        git_line = git_out.strip().splitlines()[-1] if git_out.strip() else "not_git"
        if git_line != "git_ok":
            raise RuntimeError(
                f"chia_root exists at {root} but is not a git repository. {_CHIA_ROOT_HINT}"
            )


async def _git_commits_behind(session: SshSession, branch: str) -> int:
    _, stdout, _ = await session.run(
        f"{session.shell_prelude()}"
        "git fetch -q 2>/dev/null || git fetch -q\n"
        f"count=$(git rev-list HEAD..origin/{branch} --count 2>/dev/null || true)\n"
        f"if [ -z \"$count\" ]; then count=$(git rev-list HEAD..{branch} --count 2>/dev/null || echo 999); fi\n"
        "echo \"$count\"",
        check=False,
        timeout=120,
    )
    line = stdout.strip().splitlines()[-1] if stdout.strip() else "999"
    try:
        return int(line)
    except ValueError:
        return 999


async def _upgrade_needed(session: SshSession, harvester: Harvester) -> tuple[bool, str]:
    if harvester.upgrade_mode != "git":
        return True, f"upgrade_mode={harvester.upgrade_mode}"
    behind = await _git_commits_behind(session, harvester.git_branch)
    remote = f"origin/{harvester.git_branch}"
    if behind > 0:
        return True, f"{behind} commit(s) behind {remote}"
    return False, f"already up to date with {remote}"


async def _check_farmer_host(session: SshSession, harvester: Harvester) -> tuple[bool, str]:
    host = harvester.farmer_host
    if not host:
        return True, "no farmer_host configured"
    _, dns_out, _ = await session.run(
        f"getent hosts {host} >/dev/null 2>&1 && echo dns_ok || echo dns_fail",
        check=False,
        timeout=30,
    )
    if "dns_fail" in dns_out:
        return False, f"farmer_host '{host}' does not resolve"

    if harvester.role == NodeRole.FARMER:
        _, summary, _ = await _run_chia_cli(
            session,
            harvester,
            "chia farm summary 2>&1 | head -40",
            timeout=90,
        )
        low = summary.lower()
        if "farming" in low or "sync" in low:
            return True, f"farmer node running ({host})"
        return False, "farm summary did not show farming/sync status"

    # Harvesters: farm summary is farmer-only; check harvester process instead.
    _, proc_out, _ = await _run_chia_cli(
        session,
        harvester,
        "pgrep -x chia_harvester >/dev/null 2>&1 && echo running || echo stopped",
        timeout=30,
    )
    if "running" in proc_out:
        return True, f"harvester process running; farmer {host} resolves"
    return False, f"harvester process not running (farmer {host} resolves)"


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
    force: bool = False,
) -> StepResult:
    if dry_run:
        return StepResult(step_id=step_id, status=StepStatus.SKIPPED, message="dry-run")

    branch = harvester.git_branch
    prelude = session.shell_prelude()
    activate = harvester.activate_cmd

    try:
        if step_id == "precheck":
            mode = await detect_install_mode(session, harvester)
            if mode == InstallMode.PACKAGE:
                raise RuntimeError(_PACKAGE_DEPLOY_MSG)
            if mode != InstallMode.SOURCE:
                raise RuntimeError(
                    f"Cannot deploy: chia_root missing at {harvester.chia_root} "
                    f"and 'chia' not available on PATH. {_CHIA_ROOT_HINT}"
                )
            await _validate_chia_root(session, harvester)

        elif step_id == "upgrade_check":
            if force:
                return StepResult(
                    step_id=step_id,
                    status=StepStatus.SKIPPED,
                    message="skipped (--force)",
                )
            needed, msg = await _upgrade_needed(session, harvester)
            if not needed:
                return StepResult(
                    step_id=step_id,
                    status=StepStatus.SUCCESS,
                    message=f"no upgrade needed: {msg}",
                    output="skip",
                )
            return StepResult(
                step_id=step_id,
                status=StepStatus.SUCCESS,
                message=f"upgrade needed: {msg}",
            )

        elif step_id == "backup_config":
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            cfg = await session.expand_remote_path(harvester.chia_config_dir)
            await session.run(
                f"{prelude}"
                f'backup=~/chia-backups/{ts}; mkdir -p "$backup/mainnet-config" "$backup/repo" && '
                f'if [ -d "{cfg}" ]; then cp -a "{cfg}/." "$backup/mainnet-config/" && '
                f'echo "backed up {cfg}"; else echo "warning: {cfg} not found"; fi && '
                f'cp -a config.yaml "$backup/repo/" 2>/dev/null || '
                f'echo "warning: repo config.yaml not found"',
                check=True,
            )

        elif step_id == "stop_services":
            root = await session.expand_remote_path(harvester.chia_root)
            code, _, _ = await session.run(
                f'cd "{root}"\n{_CHIA_STOP}',
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

        elif step_id in ("start_services", "start_harvester"):
            svc = harvester.start_service
            await session.run(
                f"{prelude}{activate}\nchia start {svc}\n",
                check=True,
                timeout=180,
            )

        elif step_id == "postcheck":
            version = await _chia_version(session, harvester)
            warnings: list[str] = []
            if harvester.farmer_host:
                ok, farmer_msg = await _check_farmer_host(session, harvester)
                if not ok:
                    warnings.append(farmer_msg)
                elif farmer_msg:
                    pass  # logged via session.run output
            message = f"chia version: {version}"
            if warnings:
                message += f" (warning: {'; '.join(warnings)})"
            status = StepStatus.SUCCESS if not warnings else StepStatus.SUCCESS
            return StepResult(
                step_id=step_id,
                status=status,
                message=message,
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
    force: bool = False,
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
        job.version_before = await _chia_version(session, harvester)
        skip_git = await _skip_git_steps(session)
        if skip_git and on_log:
            on_log(
                harvester.id,
                "Recovery mode: no activate/venv — skipping git_update and git_clean_check",
            )

        for step_index, step in enumerate(recipe.steps):
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
                role = harvester.role_label
                on_log(
                    harvester.id,
                    f"--- step: {step.id} — {step.description} [{role}]",
                )
            result = await _run_step(
                session, harvester, step.id, dry_run=False, force=force
            )
            job.steps.append(result)
            if result.status == StepStatus.FAILED:
                job.state = JobState.FAILED
                job.error = f"Step '{result.step_id}' failed: {result.message}"
                break
            if (
                step.id == "upgrade_check"
                and result.output == "skip"
                and not force
            ):
                job.skipped_upgrade = True
                job.state = JobState.SUCCESS
                job.version_after = job.version_before
                if on_log:
                    on_log(harvester.id, f"Skipping deploy: {result.message}")
                for remaining in recipe.steps[step_index + 1 :]:
                    job.steps.append(
                        StepResult(
                            step_id=remaining.id,
                            status=StepStatus.SKIPPED,
                            message="upgrade not required",
                        )
                    )
                break
        else:
            job.version_after = await _chia_version(session, harvester)
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
        mode = await detect_install_mode(session, harvester)
        version = await _chia_version(session, harvester)
        summary = ""
        if harvester.role == NodeRole.FARMER:
            if mode == InstallMode.PACKAGE:
                summary_cmd = "chia farm summary 2>&1"
            else:
                summary_cmd = "chia farm summary 2>&1"
            _, stdout, _ = await _run_chia_cli(
                session, harvester, summary_cmd, mode=mode, timeout=120
            )
            summary = stdout.strip()
        else:
            _, proc_out, _ = await _run_chia_cli(
                session,
                harvester,
                "pgrep -x chia_harvester >/dev/null 2>&1 && echo harvester: running || echo harvester: stopped",
                mode=mode,
                timeout=30,
            )
            summary = proc_out.strip().splitlines()[-1] if proc_out.strip() else ""
        behind = "-"
        if mode == InstallMode.SOURCE:
            try:
                behind = str(await _git_commits_behind(session, harvester.git_branch))
            except Exception:
                behind = "?"
        return {
            "id": harvester.id,
            "host": harvester.host,
            "role": harvester.role_label,
            "install_mode": mode.value,
            "version": version,
            "commits_behind": behind,
            "summary": summary,
        }
    finally:
        await session.close()


async def run_doctor(harvester: Harvester, on_log: LogCallback | None = None) -> dict:
    checks: dict[str, str] = {
        "id": harvester.id,
        "host": harvester.host,
        "role": harvester.role_label,
    }
    session = SshSession(harvester, on_log=on_log)
    try:
        await session.connect()
        checks["ssh"] = "ok"
        mode = await detect_install_mode(session, harvester)
        checks["install_mode"] = mode.value

        if mode == InstallMode.SOURCE:
            checks["chia_root"] = f"ok ({harvester.chia_root})"
            checks["git_repo"] = "ok"
            prelude = session.shell_prelude()
            try:
                _, stdout, _ = await session.run(f"{prelude}git status", check=True)
                if "nothing to commit, working tree clean" in stdout:
                    checks["git_clean"] = "ok"
                else:
                    checks["git_clean"] = "dirty (upgrade may change RELEASE)"
            except Exception as exc:
                checks["git_clean"] = f"fail: {exc}"
            try:
                checks["git_behind"] = str(
                    await _git_commits_behind(session, harvester.git_branch)
                )
            except Exception as exc:
                checks["git_behind"] = f"fail: {exc}"
        elif mode == InstallMode.PACKAGE:
            checks["chia_root"] = (
                f"not used (no source tree at {harvester.chia_root}); chia on PATH"
            )
            checks["git_repo"] = "n/a (package install)"
            checks["git_clean"] = "n/a"
            checks["git_behind"] = "n/a"
            checks["deploy"] = "not supported (use package upgrade or add source clone)"
        else:
            checks["chia_root"] = f"fail: missing {harvester.chia_root}, chia not on PATH"
            checks["git_repo"] = "not checked"
            checks["git_clean"] = "skipped"
            checks["git_behind"] = "skipped"

        checks["version"] = await _chia_version(session, harvester)

        if harvester.role == NodeRole.FARMER and mode in (
            InstallMode.SOURCE,
            InstallMode.PACKAGE,
        ):
            try:
                _, farm_out, _ = await _run_chia_cli(
                    session,
                    harvester,
                    "chia farm summary 2>&1 | head -5",
                    mode=mode,
                    timeout=90,
                )
                first = farm_out.strip().splitlines()[0] if farm_out.strip() else "empty"
                checks["farm_summary"] = first[:80]
            except Exception as exc:
                checks["farm_summary"] = f"fail: {exc}"
        elif harvester.role == NodeRole.HARVESTER and mode in (
            InstallMode.SOURCE,
            InstallMode.PACKAGE,
        ):
            try:
                _, proc_out, _ = await _run_chia_cli(
                    session,
                    harvester,
                    "pgrep -x chia_harvester >/dev/null 2>&1 && echo running || echo stopped",
                    mode=mode,
                    timeout=30,
                )
                checks["harvester_process"] = (
                    proc_out.strip().splitlines()[-1] if proc_out.strip() else "unknown"
                )
            except Exception as exc:
                checks["harvester_process"] = f"fail: {exc}"
        if harvester.farmer_host:
            checks["farmer_host"] = harvester.farmer_host
        return checks
    except Exception as exc:
        checks["ssh"] = f"fail: {exc}"
        return checks
    finally:
        await session.close()


async def test_ssh(
    harvester: Harvester, on_log: LogCallback | None = None
) -> tuple[bool, str | None]:
    """Return (success, error_message). error_message is set on failure."""
    session = SshSession(harvester, on_log=on_log)
    try:
        await session.connect()
        _, stdout, _ = await session.run("hostname", check=True, timeout=30)
        if on_log:
            on_log(harvester.id, f"hostname: {stdout.strip()}")
        return True, None
    except Exception as exc:
        return False, exc
    finally:
        await session.close()
