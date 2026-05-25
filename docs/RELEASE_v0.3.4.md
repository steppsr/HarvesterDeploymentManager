## Summary

Phase 2 GUI release series: **Harvester Deployment Manager** now complements the `hdm` CLI with a full desktop workflow for inventory, deploy, history, and packaged Windows distribution.

Since **v0.2.0**, the project has moved from a CLI-only controller to a daily-use GUI with node cards, deploy workflows, deployment history, SSH-test improvements, packaged `.exe` support, and persistent user config/data folders for installed builds.

## Highlights

- **Desktop GUI** — `harvest-deploy` launcher with a card-based fleet dashboard
- **Tabbed layout** — **Nodes**, **Fleet summary**, and **Logs**
- **Inventory management** — add, edit, remove, validate, import from YAML, choose config file
- **Deploy workflows** — deploy wizard, confirm dialog, live logs, progress, summary dialog
- **Per-node tools** — **Doctor**, **Test SSH**, **History**, **Log**, **Deploy**
- **Deployment history** — SQLite-backed run timeline with JSON import
- **Mainnet / Testnet labels** — badges and filters on node cards
- **Packaged Windows app** — PyInstaller build script, app icon, clean first-run behavior
- **Improved SSH UX** — clearer errors for missing setup, auth failure, unreachable hosts, and encrypted keys

## Upgrade from v0.2.0

```powershell
git pull
python -m pip install -e ".[gui]"
```

For a packaged Windows build:

```powershell
.\scripts\build-gui.ps1
```

If you run the packaged `.exe`, app data lives under:

`%LOCALAPPDATA%\HarvesterDeploymentManager`

That folder contains `config\`, `data\`, `deployments\`, and `settings.yaml`.

## Command names

| Command | Role |
| --- | --- |
| `hdm` | CLI — `test-ssh`, `status`, `doctor`, `deploy` |
| `harvest-deploy` | Desktop GUI launcher |
| `dist\HarvesterDeploymentManager.exe` | Packaged Windows GUI build |

## GUI overview

### Nodes tab

- Card grid with **network**, **role**, and **install-mode** badges
- Filters: **All**, **Harvesters**, **Farmers**, **Mainnet**, **Testnet**
- Per-card actions: **Doctor**, **Test SSH**, **History**, **Log**, **Deploy**
- Upgrade hints when a source install is behind `origin/latest`

### Deploy workflow

- Target selection matching CLI groups (`all`, `harvesters`, `farmers`, single node)
- Advanced options: parallel, dry-run, force
- Confirmation dialog before deploy
- Live per-node log streaming and step progress
- Completion summary with success/failure results

### Inventory and history

- GUI inventory CRUD with validation
- YAML import from a chosen file and **Choose config file…**
- SQLite canonical storage with sync back to `harvesters.yaml`
- Per-node deploy history timeline with JSON import for past runs

## Packaged Windows app

- Built with `scripts\build-gui.ps1`
- Clean PyInstaller rebuild (`build\` and `dist\` removed first)
- Uses persistent app folders under `%LOCALAPPDATA%\HarvesterDeploymentManager`
- Starts with **no predefined nodes** on a truly clean first run
- App icon sourced from `assets\hdm.png` and converted to `assets\hdm.ico` for the `.exe`

## Known limitations

- Cancel mid-deploy is still out of scope
- Package-based nodes (`.deb` / PATH installs) support `status` and `doctor`, but not git/source `deploy`
- YAML export UI is not implemented (save still syncs the active `harvesters.yaml`)
- Log pause/copy/save and OS toast notifications are deferred
- Windows controller remains the primary tested packaged target; Linux/macOS remain future packaging work

## What’s next

- Package/deb upgrade workflow for package-based farmers
- Richer log tools (copy/save/pause)
- Optional deploy cancel support
- Broader cross-platform packaging and validation for Linux/macOS controllers

## Changelog

### Added

- `hdm` CLI entrypoint naming
- PySide6 desktop GUI (`harvest-deploy`)
- Deploy wizard, confirmation modal, and completion summary dialog
- GUI inventory management with SQLite persistence
- Deployment history timeline and JSON import
- Mainnet/Testnet badges and filters
- Farmer fleet summary tab
- App icon support for runtime and packaged build
- PyInstaller spec and Windows build script
- File-picker config selection for packaged builds

### Changed

- GUI layout evolved from a single dashboard/log split to tabs: **Nodes**, **Fleet summary**, **Logs**
- Card actions now use explicit buttons instead of card-click log focus
- Installed builds use `%LOCALAPPDATA%\HarvesterDeploymentManager` instead of temp extraction paths
- Packaged builds now start empty on a true clean first run
- SSH failure handling now distinguishes setup/auth/connectivity/passphrase cases

### Fixed

- `~/.ssh` key passphrase prompt no longer appears for every SSH failure
- Frozen-build config/data paths no longer point at PyInstaller temp extraction folders
- Config import now uses a file picker instead of assuming one fixed YAML path
- Icon generation now derives `.ico` from the canonical `assets\hdm.png`
- Card layout spacing is consistent between source installs and package-install farmers

## Links

- Repository: https://github.com/steppsr/HarvesterDeploymentTool
- README: https://github.com/steppsr/HarvesterDeploymentTool/blob/main/README.md
- Architecture: https://github.com/steppsr/HarvesterDeploymentTool/blob/main/ARCHITECTURE.md
