## Summary

Phase 3 release series: **Harvester Deployment Manager** extends the Phase 2 GUI with fleet telemetry, operator diagnostics, theme/preferences support, session restore, and richer day-to-day monitoring tools.

Since **v0.3.4**, the project has moved from a GUI-focused deploy/inventory app into a more complete operator dashboard with farmer-summary parsing, footer telemetry, health-aware fleet refresh, configurable auto-refresh, and more polished Logs and Fleet summary tabs.

## Highlights

- **Fleet telemetry** — parse farmer `chia farm summary` into footer metrics and node-card telemetry
- **Health-aware refresh** — integrated **PING** + **SSH** checks during fleet refresh with clear unhealthy card borders
- **Theme and preferences** — Light/Dark mode, top-right theme toggle, Settings menu, configurable refresh interval
- **Session restore** — remember theme, window size, maximized/fullscreen state, and other GUI preferences
- **Richer Logs tab** — filtered actions for **Clear**, **Select All**, **Deselect All**, **Copy to Clipboard**, and **Save as**
- **Fleet summary polish** — formatted farmer summary output, clearer grouping, and consistent action-bar header styling

## Upgrade from v0.3.4

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

- Node cards show **network**, **role**, and **install-mode** badges
- Node cards now also show parsed telemetry: **plots**, **size**, and **IP**
- Fleet refresh runs **PING** + **SSH** health checks and marks unhealthy nodes with a thick red border
- Footer telemetry shows **Mainnet** / **Testnet** metrics only when the current fleet actually has nodes for that network

### Fleet summary and telemetry

- Farmer `chia farm summary` output is still available as the raw operator view
- Parsed summary data feeds:
  - footer metrics
  - node-card telemetry
  - network-specific fleet monitoring
- Fleet summary content now uses readable formatting for labels, values, plot counts, plot sizes, and farmer sections

### Logs, settings, and preferences

- Logs tab includes a dedicated action bar and filtered log actions
- Settings menu provides a configurable fleet auto-refresh interval
- Theme choice and window/session state persist between launches

## Packaged Windows app

- Built with `scripts\build-gui.ps1`
- Uses persistent app folders under `%LOCALAPPDATA%\HarvesterDeploymentManager`
- Remembers theme, refresh interval, chosen config path, and window/session state
- Continues to start with **no predefined nodes** on a truly clean first run

## Known limitations

- Cancel mid-deploy is still out of scope
- Package-based nodes (`.deb` / PATH installs) support `status` and `doctor`, but not git/source `deploy`
- Windows controller remains the primary tested packaged target; Linux/macOS controller work is still future scope
- Local/controller-side Windows Chia nodes (for example ARTOO) are not yet modeled separately from SSH-managed Linux nodes
- Guided provisioning of brand new harvester machines is not yet implemented

## What’s next

- Package/deb upgrade workflow for package-install nodes
- Safe deploy-cancel design and investigation
- Linux/macOS controller validation
- In-app documentation / “How to” ideas and future local-node considerations

## Changelog

### Added

- Farmer-summary parsing and network telemetry model
- Footer telemetry populated from farmer summaries
- Node-card telemetry for plots, size, and IP
- Refresh-time **PING** + **SSH** health checks
- Unhealthy node highlighting on cards
- Light/Dark theme support and persisted theme preference
- Settings menu and refresh-interval dialog
- Session restore for theme and window state
- Filtered log tools in the Logs tab

### Changed

- Fleet summary moved from plain text only to a formatted operator view while preserving the underlying summary structure
- Logs tab now uses an action-bar layout consistent with the other tabs
- Footer telemetry now hides unused network sections and avoids placeholder values when no data exists yet
- Window/session restore now remembers actual window mode (`normal`, `maximized`, `fullscreen`)

### Fixed

- Theme-related Fleet summary colors now re-render immediately on theme change instead of waiting for the next refresh
- Multiline log entries now keep a consistent node prefix per displayed line
- Footer styling now renders as a single continuous status bar surface
- Auto-refresh/UI failure handling no longer leaves the Nodes tab action bar locked

## Links

- Repository: https://github.com/steppsr/HarvesterDeploymentManager
- README: https://github.com/steppsr/HarvesterDeploymentManager/blob/main/README.md
- Architecture: https://github.com/steppsr/HarvesterDeploymentManager/blob/main/ARCHITECTURE.md
