# v0.1.0 — Phase 1: CLI Release

**Release date:** 2026-05-23  
**Tag:** `v0.1.0`  
**License:** [Apache License 2.0](https://github.com/steppsr/HarvesterDeploymentTool/blob/main/LICENSE)

## Summary

First stable release of **Harvester Deployment Tool** — a Python CLI that upgrades [Chia](https://www.chia.net/) harvesters on Ubuntu from a Windows controller over SSH. Phase 1 focuses on a reliable, repeatable deployment pipeline with fleet orchestration, live logging, and JSON run summaries. A desktop GUI is planned for Phase 2.

This release was validated against a six-harvester home lab (git-based upgrades to Chia `latest` / 2.7.1).

---

## Highlights

- **Agentless SSH orchestration** — no daemon on harvesters; uses existing `sshd` and your SSH keys
- **Fleet inventory** — YAML config with per-host overrides and `harvesters.example.yaml` template
- **Four CLI commands** — `test-ssh`, `status`, `doctor`, `deploy`
- **Parallel deploys** — `--parallel N` with per-host live log prefixes
- **Recovery mode** — resumes with `install.sh` if a prior run removed venvs but did not finish
- **Git tree hardening** — submodule reset, `mozilla-ca/` handling, and pragmatic clean checks before install
- **SSL fix automation** — runs `chia init --fix-ssl-permissions` when `chia init` reports permission warnings
- **Run artifacts** — timestamped `deployments/<id>/summary.json` with per-step status and version before/after

---

## Installation

**Requirements:** Windows 10/11, Python 3.11+, Ubuntu harvesters with Chia at `~/chia-blockchain`, SSH key auth.

```powershell
git clone https://github.com/steppsr/HarvesterDeploymentTool.git
cd HarvesterDeploymentTool
git checkout v0.1.0

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
harvester-deploy --help
```

Configure inventory (not included in git):

```powershell
copy config\harvesters.example.yaml config\harvesters.yaml
# Edit config\harvesters.yaml — see README.md
```

Full setup (SSH keys, testing workflow, deploy examples): [README.md](https://github.com/steppsr/HarvesterDeploymentTool/blob/v0.1.0/README.md)

---

## CLI reference

| Command | Description |
|---------|-------------|
| `harvester-deploy test-ssh` | Verify SSH connectivity (`--target` optional) |
| `harvester-deploy status` | Report `chia version` per host |
| `harvester-deploy doctor` | SSH, chia root, git status, version checks |
| `harvester-deploy deploy` | Run upgrade recipe |

**Common `deploy` options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--target`, `-t` | `all` | Host `id`, comma-separated ids, or `all` |
| `--parallel`, `-p` | `2` | Max concurrent deployments |
| `--dry-run` | off | List steps without connecting |
| `--recipe`, `-r` | `chia-upgrade-default` | Recipe name |
| `--config`, `-c` | `config/harvesters.yaml` | Inventory path |

**Exit codes:** `0` all success · `1` all failed · `2` partial failure

---

## Deployment recipe (`chia-upgrade-default`)

Executed remotely in order:

1. **precheck** — chia root exists; git repository  
2. **backup_config** — backup `config.yaml` in repo if present  
3. **stop_services** — `chia stop` (or safe fallbacks when venv/CLI missing)  
4. **remove_venvs** — remove `venv`, `.penv`, `.venv`  
5. **git_update** — `git fetch`, checkout `latest`, hard reset with submodules  
6. **git_clean_check** — submodule sync, clean untracked files, verify tree ready for install  
7. **install** — `sh install.sh` (long-running; streamed)  
8. **chia_init** — `chia init`; optional `--fix-ssl-permissions`  
9. **start_harvester** — `chia start harvester`  
10. **postcheck** — `chia version` recorded in summary  

Manual reference: [How to Upgrade Chia.md](https://github.com/steppsr/HarvesterDeploymentTool/blob/v0.1.0/How%20to%20Upgrade%20Chia.md)

---

## Architecture

Layered Python package (`src/harvester_deploy/`):

- **Domain** — harvester model, job/step state  
- **SSH** — asyncssh sessions with streamed output  
- **Recipes** — deployment engine and step implementations  
- **Orchestrator** — parallel runs with semaphore  
- **Persistence** — YAML inventory (Pydantic)  
- **Reporting** — Rich console + JSON summaries  

Design details: [ARCHITECTURE.md](https://github.com/steppsr/HarvesterDeploymentTool/blob/v0.1.0/ARCHITECTURE.md)

---

## Dependencies

| Package | Purpose |
|---------|---------|
| asyncssh ≥2.14 | SSH connections and remote commands |
| typer ≥0.12 | CLI |
| rich ≥13 | Terminal UI |
| pydantic ≥2 | Config validation |
| PyYAML ≥6 | Inventory and recipes |

---

## Security notes

- **SSH keys only** — passwords are not stored; use `config/harvesters.yaml` locally (gitignored)  
- **LAN use case** — restrict `sshd` to your controller IP if desired  
- **Destructive deploy** — stops Chia and removes venvs; always test one host and use `--dry-run` first  
- Never commit `config/harvesters.yaml` or private keys  

---

## Known limitations (Phase 1)

- **No pre-upgrade version gate** — deploy runs the full recipe even if already on `origin/latest` (check manually with `git rev-list`; see README)  
- **Config backup** — backs up repo `config.yaml` only; live config under `~/.chia/mainnet/config/` is not copied automatically  
- **Controller platform** — developed and tested on Windows 11; harvesters are Ubuntu  
- **Upgrade method** — git + `install.sh` on `latest` branch only (no installer-only path in this release)  
- **No GUI** — terminal-only; Phase 2 planned  

---

## What's next (Phase 2)

- Desktop dashboard (PySide6) with per-harvester cards and live log panes  
- Harvester CRUD and **Test SSH** in the UI  
- SQLite deployment history  
- Same core library — no rewrite of the deployment engine  

---

## Files in this release

- Application source: `src/harvester_deploy/`  
- Example inventory: `config/harvesters.example.yaml`  
- Recipe: `config/recipes/chia-upgrade-default.yaml`  
- Documentation: `README.md`, `ARCHITECTURE.md`, `How to Upgrade Chia.md`  
- License: `LICENSE` (Apache-2.0)  

**Not included in git:** `config/harvesters.yaml`, `deployments/` (local run output)

---

## Full changelog

### Added

- Initial `harvester-deploy` CLI (`test-ssh`, `status`, `doctor`, `deploy`)  
- YAML fleet inventory with defaults and per-host overrides  
- `chia-upgrade-default` deployment recipe (10 steps)  
- Parallel orchestration with configurable concurrency  
- Live per-harvester log streaming to the console  
- JSON deployment summaries under `deployments/<timestamp>/`  
- Recovery mode for interrupted upgrades (skip git when venv absent)  
- Robust Chia stop when `activate`/venv missing (`pkill -x`, no `pkill -f` self-match)  
- Git clean check with submodule reset and `mozilla-ca/` handling  
- Automatic `chia init --fix-ssl-permissions` on SSL warnings  
- Comma-separated `--target` (e.g. `tarkin,vader`)  
- Apache 2.0 license, README, architecture docs  

### Changed

- N/A (initial release)

### Fixed

- N/A (initial release)

### Security

- Local inventory and deployment logs excluded via `.gitignore`  

---

## Links

- **Repository:** https://github.com/steppsr/HarvesterDeploymentTool  
- **Issues:** https://github.com/steppsr/HarvesterDeploymentTool/issues  
- **Documentation:** https://github.com/steppsr/HarvesterDeploymentTool/blob/main/README.md  

---

**Thank you** for trying Harvester Deployment Tool. Bug reports and feature requests are welcome on GitHub Issues.
