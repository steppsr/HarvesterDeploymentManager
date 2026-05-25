## Summary

First stable release of **Harvester Deployment Tool**: a Python CLI that upgrades [Chia](https://www.chia.net/) harvesters on Ubuntu from a Windows controller over SSH.

Phase 1 delivers a repeatable deployment pipeline with fleet orchestration, live logging, and JSON run summaries. Validated on a six-harvester home lab (git-based upgrades to Chia `latest` / 2.7.1). A desktop GUI is planned for Phase 2.

**License:** [Apache-2.0](https://github.com/steppsr/HarvesterDeploymentManager/blob/main/LICENSE)

## Highlights

- Agentless SSH orchestration (no daemon on harvesters)
- Fleet inventory via YAML (`harvesters.example.yaml` template; local `harvesters.yaml` is gitignored)
- CLI commands: `test-ssh`, `status`, `doctor`, `deploy`
- Parallel deploys with `--parallel` and per-host live log output
- Recovery mode if a prior run removed venvs but did not finish `install.sh`
- Git/submodule cleanup before install (including `mozilla-ca/` handling)
- Automatic `chia init --fix-ssl-permissions` when SSL warnings appear
- JSON summaries under `deployments/<timestamp>/summary.json`

## Requirements

- Windows 10/11 controller (tested on Windows 11)
- Python 3.11+
- Ubuntu harvesters with Chia at `~/chia-blockchain`
- SSH key authentication (passwordless recommended)

## Installation

```powershell
git clone https://github.com/steppsr/HarvesterDeploymentManager.git
cd HarvesterDeploymentManager
git checkout v0.1.0

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .

copy config\harvesters.example.yaml config\harvesters.yaml
```

Edit `config\harvesters.yaml`, then verify:

```powershell
harvester-deploy --help
```

Full documentation: [README.md](https://github.com/steppsr/HarvesterDeploymentManager/blob/v0.1.0/README.md)

## Quick start (recommended)

```powershell
harvester-deploy test-ssh
harvester-deploy status
harvester-deploy doctor
harvester-deploy deploy --target all --parallel 2 --dry-run
harvester-deploy deploy --target my-first-host
```

## CLI commands

| Command | Description |
| --- | --- |
| `harvester-deploy test-ssh` | Verify SSH connectivity |
| `harvester-deploy status` | Show `chia version` per host |
| `harvester-deploy doctor` | Run health checks (SSH, paths, git, version) |
| `harvester-deploy deploy` | Execute the upgrade recipe |

### Deploy options

| Option | Default | Description |
| --- | --- | --- |
| `--target`, `-t` | `all` | Host id, comma-separated ids, or `all` |
| `--parallel`, `-p` | `2` | Maximum concurrent deployments |
| `--dry-run` | off | Print steps only; no remote changes |
| `--recipe`, `-r` | `chia-upgrade-default` | Recipe to run |
| `--config`, `-c` | `config/harvesters.yaml` | Path to inventory file |

**Exit codes:** `0` = all succeeded, `1` = all failed, `2` = partial failure

## Upgrade recipe (`chia-upgrade-default`)

Steps run on each harvester in order:

1. `precheck` - Verify chia root and git repository
2. `backup_config` - Backup `config.yaml` in repo if present
3. `stop_services` - Stop Chia (with fallbacks when venv/CLI is missing)
4. `remove_venvs` - Remove `venv`, `.penv`, `.venv`
5. `git_update` - Fetch, checkout `latest`, hard reset with submodules
6. `git_clean_check` - Sync submodules, clean untracked files, verify tree
7. `install` - Run `install.sh` (long-running; output is streamed)
8. `chia_init` - Run `chia init` (and `--fix-ssl-permissions` if needed)
9. `start_harvester` - Run `chia start harvester`
10. `postcheck` - Record `chia version` in the summary

Manual reference: [How to Upgrade Chia.md](https://github.com/steppsr/HarvesterDeploymentManager/blob/v0.1.0/How%20to%20Upgrade%20Chia.md)

## Dependencies

| Package | Version | Purpose |
| --- | --- | --- |
| asyncssh | >= 2.14 | SSH and remote command execution |
| typer | >= 0.12 | CLI framework |
| rich | >= 13 | Terminal output |
| pydantic | >= 2 | Config validation |
| PyYAML | >= 6 | YAML inventory and recipes |

## Known limitations

- No automatic skip when already on `origin/latest` (check manually before deploy; see README)
- Config backup targets repo `config.yaml` only, not `~/.chia/mainnet/config/` by default
- Windows controller and Ubuntu harvesters only in this release
- Git + `install.sh` on the `latest` branch only
- No graphical UI in v0.1.0 (Phase 2)

## What's next (Phase 2)

- Desktop dashboard (PySide6)
- Harvester cards with status, version, and last deploy time
- Deploy one host or the full fleet from the UI
- Per-harvester live log panes
- SQLite deployment history

## Changelog

### Added

- Initial `harvester-deploy` CLI
- YAML fleet inventory with shared defaults and per-host overrides
- `chia-upgrade-default` recipe (10 steps)
- Parallel orchestration with configurable concurrency
- Live log streaming with per-harvester prefixes
- JSON deployment summaries
- Recovery mode for interrupted upgrades
- Safe Chia stop when `activate` / venv is missing
- Git clean check with submodule and `mozilla-ca/` handling
- Automatic SSL permission fix after `chia init`
- Comma-separated `--target` values
- README, ARCHITECTURE.md, and Apache-2.0 LICENSE

## Links

- Repository: https://github.com/steppsr/HarvesterDeploymentManager
- Report issues: https://github.com/steppsr/HarvesterDeploymentManager/issues
