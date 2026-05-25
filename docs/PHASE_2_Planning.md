# Phase 2 Questions

### Scope and success (what "done" means)

| Number | Question | Answer |
| --- | --- | --- |
| 1.1 | Is Phase 2 Windows-only, or should it run on Linux/macOS too someday? | Cross-platform so it runs on Windows, Linux/macOS |
| 1.2 | Must the GUI replace the CLI for daily use, or complement it (power users keep CLI)? | GUI should compliment the CLI |
| 1.3 | What is the minimum v1 GUI? (e.g. dashboard + deploy + logs only, no history?) | dashboard + deploy + logs |
| 1.4 | Success criterion: only you, or other Chia farmers on GitHub? | only me |

### Technology (already leaning one way)

| Number | Question | Answer |
| --- | --- | --- |
| 2.1 | GUI framework? | PySide6 |
| 2.2 | How is the app distributed? | PyInstaller |
| 2.3 | Async model? | Qt thread + signal from existing asyncio orchestrator |
| 2.4 | Single process or spawn CLI subprocess for deploy? | Single process with asyncio |

### Layout and information architecture

| Number | Question | Answer |
| --- | --- | --- |
| 3.1 | Main screen layout? | Grid of cards. Most users won't have that many harvesters. |
| 3.2 | Where do live logs live? | click node to open log panel |
| 3.3 | How to show farmer (JABBA) vs harvesters? | badge on card |
| 3.4 | Show fleet summary from farmer (chia farm summary) in GUI? | Dedicated fleet panel on farmer |
| 3.5 | Package-only nodes (JABBA): what actions in UI? | deploy  not supported with explanation |

### Inventory (nodes in config)

| Number | Question | Answer |
| --- | --- | --- |
| 4.1 | Edit inventory in GUI or YAML only? | Edit inventory in GUI |
| 4.2 | On Add node, required fields? | id, host, role, ssh_user, key path, farmer_host (harvesters), chia_root, chia_config_dir. |
| 4.3 | Test SSH on save only or also “Test” button? | Both |
| 4.4 | Where is config saved? | GUI also writes SQLite and syncs YAML |
| 4.5 | Validation rules in UI? | Yes, duplicate ids, invalid role, farmer_host only on harvesters, etc |
| 4.6 | Import/export YAML for backup/sharing? | Not at this time |

### Deploy and operations (core workflows)

| Number | Question | Answer |
| --- | --- | --- |
| 5.1 | Deploy targets in UI? | Match CLI |
| 5.2 | Expose --parallel, --dry-run, --force? | Advanced Dialog |
| 5.3 | Cancel mid-deploy? | No cancel v1 |
| 5.4 | Confirm before deploy? | Yes, confirm before deploy with modal checklist |
| 5.5 | Refresh status on open vs manual “Refresh fleet”? | manual + startup for v1 |
| 5.6 | Run doctor / test-ssh from GUI? | buttons on cards |
| 5.7 | Upgrade available indicator? | yes |

### Live monitoring during deploy

| Number | Question | Answer |
| --- | --- | --- |
| 6.1 | Progress model? | current recipe step name + indeterminate bar |
| 6.2 | Log viewer: autoscroll, pause, copy, save? | autoscroll v1, others can wait |
| 6.3 | Color per node in log (prefix)? | match CLI |
| 6.4 | Notification when all deploys finish? | in-app only |
| 6.5 | Partial failure UX? | summary table + highlight failed cards red |

### History and persistence (SQLite)

| Number | Question | Answer |
| --- | --- | --- |
| 7.1 | What goes in SQLite? | deploy runs only for v1 |
| 7.2 | Keep JSON in deployments/ too? | CLI compatibility |
| 7.3 | History UI? | timeline per node |
| 7.4 | Retention? | keep all forever |
| 7.5 | Show skipped (up to date) runs in history? | yes |

### Security and credentials

| Number | Question | Answer |
| --- | --- | --- |
| 8.1 | SSH key path in UI — file picker? | default ~/.ssh/id_ed25519 |
| 8.2 | keyring for key passphrase? | Yes we should add for GUI v1 |
| 8.3 | Warn if harvesters.yaml is world-readable? | low priority |
| 8.4 | Secrets in repo — document only or GUI “open config folder”? | GUI open config folder |


### Package / farmer edge cases (your real fleet)

| Number | Question | Answer |
| --- | --- | --- |
| 9.1 | JABBA never git-deploy in UI — OK? | Show "Package install -- upgrade via .deb" help link/text |
| 9.2 | Future deb upgrade recipe — Phase 2 or later? | later |
| 9.3 | Per-node install_mode on card? | yes, badge |


### Packaging, updates, and project

| Number | Question | Answer |
| --- | --- | --- |
| 10.1 | App name in shell? | Title: **Harvester Deployment Manager**. CLI: `hdm`. GUI launcher (Phase 2): `harvest-deploy` |
| 10.2 | Icon, version in About box tied to pyproject.toml? | Yes |
| 10.3 | Phase 2 release as v0.3.0 or v1.0.0? | v0.3.0 so we can work out bugs & tweaks before the major release |
| 10.4 | Tests for GUI? | Both would be helpful |
| 10.5 | Update ARCHITECTURE.md as Phase 2 spec after decisions? | Yes |


### Suggested phased delivery (after you decide scope)

| Milestone | Delivers |
| --- | --- |
| 2a — Shell | Main window, load YAML, cards with static fields, Refresh status/doctor |
| 2b — Deploy | Deploy one/all, live logs, step progress, summary on completion |
| 2c — Inventory | Add/edit/remove node, Test SSH, save YAML |
| 2d — History | SQLite + runs list + open past summary |
| 2e — Polish | Cancel, notifications, farmer farm summary view, installer |
