# Harvester Deployment Manager — Architecture

A modular, **Python-centric controller** on Windows 11 orchestrates **agentless SSH** upgrades on six Ubuntu harvesters on the local LAN. Phase 1 delivers a reusable library and CLI; Phase 2 adds a desktop GUI that reuses the same core—no rewrite.

**Related docs:** `How to Upgrade Chia.md` (manual upgrade steps), `docs/PHASE_2_Planning.md` (Phase 2 decisions), `Architecture.html` (visual summary).

---

## Goals


| Phase       | Goal                                                                                                                    |
| ----------- | ----------------------------------------------------------------------------------------------------------------------- |
| **Phase 1** | From Windows: SSH to one or all harvesters, run the upgrade pipeline, stream progress, report per-host success/failure. |
| **Phase 2** | **Harvester Deployment Manager** (GUI): dashboard, deploy, live logs; complements CLI. See [Phase 2](#phase-2--harvester-deployment-manager-gui). |
| **Phase 3** | Improve observability and operator polish: telemetry, health checks, settings, theming, session restore, richer logs. |


**Scale today:** 6 harvesters (see [Inventory](#harvester-inventory)). Design for adding hosts without code changes.

---

## Architecture overview

### Pattern: Pull-based controller (agentless)

```text
┌─────────────────────────────────────────────────────────┐
│  Windows 11 — Controller                                │
│  ┌─────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ CLI /   │→ │ Orchestrator │→ │ Deployment       │  │
│  │ GUI     │  │ (concurrency)│  │ Engine (recipe)  │  │
│  └─────────┘  └──────────────┘  └────────┬─────────┘  │
│         │              │                  │           │
│         └──────────────┴──────────────────┘           │
│                        │ SSH (exec, stream, SFTP)     │
└────────────────────────┼────────────────────────────┘
                         │ LAN
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    Ubuntu +        Ubuntu +        Ubuntu +
    chia-blockchain chia-blockchain chia-blockchain
    (6 harvesters — no agent daemon)
```

- **Controller:** config, orchestration, monitoring, logging, UI (Phase 2).
- **Harvesters:** only `sshd` and existing Chia install; no deployment agent.
- **Communication:** SSH with key-based auth; stream `stdout`/`stderr` for live logs.

### Layered modules (Phase 1 = library; Phase 2 = GUI on top)


| Layer                 | Responsibility                                                          |
| --------------------- | ----------------------------------------------------------------------- |
| **CLI / GUI**         | User commands, layout, buttons                                          |
| **Orchestrator**      | Run jobs on one or many hosts; concurrency limit; cancel where possible |
| **Deployment engine** | Execute recipe steps; emit events                                       |
| **SSH transport**     | Connect, exec, stream output, optional SFTP                             |
| **Domain**            | `Harvester`, `DeployJob`, `Step`, `JobState`, events                    |
| **Persistence**       | Inventory (YAML); history (SQLite in Phase 2)                           |


Phase 1 must be implemented as **library + thin CLI**, not a one-off script, so Phase 2 does not duplicate logic.

### Job and step state (drives CLI and per-harvester UI)

**Per harvester (inventory):** `idle` | `reachable` | `unreachable` — from periodic or on-demand health checks.

**Per deployment job:**

```text
idle → connecting → running_step → success
                              └→ failed
                              └→ cancelled
```

**Events** (subscribe in CLI or GUI): `StepStarted`, `StepFinished`, `LogLine`, `JobCompleted`, `VersionChanged`.

---

## Technology stack


| Area              | Choice                            | Notes                                                       |
| ----------------- | --------------------------------- | ----------------------------------------------------------- |
| Language          | Python 3.11+                      | Aligns with Chia; runs on Windows controller                |
| Packaging         | `pyproject.toml` (`uv` or Poetry) |                                                             |
| Phase 1 CLI       | Typer                             | `deploy`, `status`, `doctor`, `test-ssh`                    |
| SSH               | **asyncssh** + asyncio            | Strong streaming for long `install.sh` runs                 |
| Config validation | Pydantic                          | Load `harvesters.yaml`                                      |
| Phase 1 inventory | YAML                              | Git-friendly; secrets outside repo                          |
| Phase 2 GUI       | **PySide6**                       | Six live log panels; non-blocking via asyncio/thread bridge |
| Phase 2 history   | SQLite                            | Deployments, errors, timestamps                             |
| Secrets           | `keyring`                         | Windows Credential Manager for key passphrases if needed    |


**Defer until recipes are stable:** Ansible playbooks (optional call from Python later). Avoid K8s, CI servers, or harvester-side agents for this scale.

---

## Harvester inventory

### What to list per harvester

Split into **you already know**, **confirm once per machine**, and **optional but useful**.

#### Required (minimum to automate your upgrade flow)


| Field                | Purpose                                    | Your fleet                                         |
| -------------------- | ------------------------------------------ | -------------------------------------------------- |
| `id`                 | Stable key for CLI/GUI (`--target tarkin`) | See table below                                    |
| `display_name`       | Human label in UI                          | Same as id, title case                             |
| `host`               | SSH target (IP or DNS)                     | LAN IPs below                                      |
| `ssh_port`           | SSH port                                   | Default `22` unless changed                        |
| `ssh_user`           | Linux login                                | `steve` (all six)                                  |
| `ssh_key_path`       | Private key on Windows controller          | **Confirm** — e.g. `%USERPROFILE%\.ssh\id_ed25519` |
| `chia_root`          | Repo directory on harvester                | Default `~/chia-blockchain`                        |
| `last_known_version` | Baseline for reports / drift               | `2.7.0` on all six today                           |


#### Strongly recommended (same upgrade on every host)


| Field          | Purpose                                | Default for your recipe               |
| -------------- | -------------------------------------- | ------------------------------------- |
| `activate_cmd` | Enter venv before Chia commands        | `. ./activate` (run from `chia_root`) |
| `git_branch`   | Checkout target                        | `latest`                              |
| `upgrade_mode` | How code is updated                    | `git` (matches your manual flow)      |
| `enabled`      | Skip in `deploy --target all` if false | `true`                                |


#### Optional (health checks, ops, Phase 2 polish)


| Field                    | Purpose                                                                     |
| ------------------------ | --------------------------------------------------------------------------- |
| `farmer_host`            | Post-upgrade: verify harvester sees farmer (if you use a shared farmer)     |
| `tags`                   | e.g. `rack-a`, `nvme`                                                       |
| `notes`                  | Free text                                                                   |
| `systemd_harvester_unit` | Only if you use systemd instead of `chia start` (your manual flow does not) |
| `backup_dir`             | Where pre-upgrade config backups go on remote host                          |
| `max_parallel_group`     | Override global concurrency for fragile hosts                               |


**Do not store in git:** private key passphrases, passwords. Use `keyring` or OS store; reference key path only in YAML.

### Known harvesters (2026-05-22)


| id          | display_name | host          | last_known_version |
| ----------- | ------------ | ------------- | ------------------ |
| `tarkin`    | TARKIN       | 192.168.1.137 | 2.7.0              |
| `kinnakeet` | KINNAKEET    | 192.168.1.145 | 2.7.0              |
| `vader`     | VADER        | 192.168.1.234 | 2.7.0              |
| `lando`     | LANDO        | 192.168.1.235 | 2.7.0              |
| `wedge`     | WEDGE        | 192.168.1.237 | 2.7.0              |
| `padme`     | PADME        | 192.168.1.249 | 2.7.0              |


### SSH connectivity (verified 2026-05-22)

Test from Windows controller (`ssh steve@192.168.1.137`):


| Finding                    | Value                                                                                                         |
| -------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Login                      | `steve` works                                                                                                 |
| Auth today                 | **Password** (prompted after host key accept)                                                                 |
| Auth target for automation | **SSH key** (no password in scripts)                                                                          |
| OS (TARKIN)                | Ubuntu 24.04.2 LTS, kernel 6.8.0-53-generic                                                                   |
| Remote hostname            | `tarkin` (shell prompt `steve@tarkin`)                                                                        |
| Host key                   | ED25519 — `SHA256:SeHPMrJIwmroMXacoef/AFj1LL2wV4b20AthhUpY0Aw` (in Windows `known_hosts` after first connect) |
| Controller LAN IP          | `192.168.1.183` (from harvester `Last login` line)                                                            |


**Before Phase 1 coding:** set up key-based login for `steve` on all six hosts (see [SSH key setup](#ssh-key-setup-windows--harvesters)). Password-only SSH blocks unattended deploy/monitor loops.

Optional per-host field `hostname` (e.g. `tarkin` on 192.168.1.137) for display and log labels; automation still uses `host` IP.

Confirm `chia_root` exists on TARKIN: `ls ~/chia-blockchain` over SSH.

### Example `config/harvesters.example.yaml`

```yaml
defaults:
  ssh_port: 22
  ssh_user: steve
  ssh_key_path: ~/.ssh/id_ed25519
  chia_root: ~/chia-blockchain
  activate_cmd: ". ./activate"
  git_branch: latest
  upgrade_mode: git
  enabled: true

harvesters:
  - id: tarkin
    display_name: TARKIN
    host: 192.168.1.137
    last_known_version: "2.7.0"

  - id: kinnakeet
    display_name: KINNAKEET
    host: 192.168.1.145
    last_known_version: "2.7.0"

  - id: vader
    display_name: VADER
    host: 192.168.1.234
    last_known_version: "2.7.0"

  - id: lando
    display_name: LANDO
    host: 192.168.1.235
    last_known_version: "2.7.0"

  - id: wedge
    display_name: WEDGE
    host: 192.168.1.237
    last_known_version: "2.7.0"

  - id: padme
    display_name: PADME
    host: 192.168.1.249
    last_known_version: "2.7.0"
```

---

## Deployment recipe (from manual process)

Source: `How to Upgrade Chia.md`. Encoded as a **versioned pipeline** the deployment engine runs over SSH (single shell session or step-per-connection—implementation detail).


| Step | id                | Remote actions (summary)                                                                 |
| ---- | ----------------- | ---------------------------------------------------------------------------------------- |
| 1    | `precheck`        | SSH OK; `cd $chia_root`; `git status` / disk sanity                                      |
| 2    | `backup_config`   | Copy `config.yaml` (and certs if present) to timestamped backup dir                      |
| 3    | `stop_services`   | `. ./activate` → `chia stop -d all` → `deactivate`                                       |
| 4    | `remove_venvs`    | `rm -rf venv .penv .venv` (from `chia_root`)                                             |
| 5    | `git_update`      | `git fetch` → `git checkout latest` → `git reset --hard FETCH_HEAD --recurse-submodules` |
| 6    | `git_clean_check` | `git status` — fail if dirty tree (uncommitted changes / wrong `RELEASE.dev0`)           |
| 7    | `install`         | `sh install.sh` (long-running; stream output)                                            |
| 8    | `activate`        | `. ./activate`                                                                           |
| 9    | `chia_init`       | `chia init`; if SSL permission warnings, `chia init --fix-ssl-permissions`               |
| 10   | `start_harvester` | `chia start harvester`                                                                   |
| 11   | `postcheck`       | `chia version`; confirm harvester process / farmer connectivity if configured            |


**CLI flags (Phase 1):**

- `deploy --target all|tarkin|...` — default all enabled hosts
- `--parallel 2` — cap concurrent upgrades (default 2)
- `--dry-run` — print steps without mutating remotes
- `--recipe default` — future: alternate recipes
- `--quiet` / `-q` — suppress step logs; final table/panels only

**Outputs:** console stream per host; JSON summary under `deployments/<timestamp>/`; exit code 0 / partial / full failure.

---

## Phased implementation

### Phase 1 — Library + CLI

**Deliverables**

- Package layout under `src/harvester_deploy/` (domain, ssh, recipes, orchestrator, persistence, cli)
- `config/harvesters.yaml` (from example; gitignore real file if it holds secrets)
- Commands: `deploy`, `status`, `doctor`, `test-ssh`
- Recipe: `config/recipes/chia-upgrade-default.yaml` mirroring table above

**Success criteria**

1. Upgrade **one** harvester from Windows with live log stream.
2. Upgrade **all six** with `--parallel 2`; summary shows before/after version per host.
3. Failed run reports failing step + remote log snippet.

### Phase 1.5 — Complete

- Skip deploy when already on `origin/latest` (`--force`)
- Backup `~/.chia/mainnet/config`
- Farmer / harvester roles, target groups, package-install detection
- `chia farm summary` on farmer nodes only

### CLI — `--quiet` (v0.2.1+)

| Item | Status |
| ---- | ------ |
| **`--quiet` / `-q`** on `test-ssh`, `status`, `doctor`, `deploy` | **Done** |

- **Default:** stream intermediate lines via `ConsoleReporter` (`{id} \| step / remote output`).
- **`--quiet`:** `on_log` is omitted; only the final Rich table (or doctor panels) is printed. `deploy` still writes JSON under `deployments/`.

**Example** — `hdm status --quiet` should print only the status table (no per-host SSH/git/chia log lines):

```text
                           Node status
┏━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┓
┃ ID        ┃ Role      ┃ Install ┃ Host      ┃ Version ┃ Behind ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━┩
│ jabba     │ farmer    │ package │ jabba     │ 2.7.1   │ -      │
│ tarkin    │ harvester │ source  │ tarkin    │ 2.7.1   │ 0      │
...
└───────────┴───────────┴─────────┴───────────┴─────────┴────────┘
```

**Implementation:** `log_callback(quiet)` in `reporting/console.py` returns `None` for `on_log` when quiet.

---

## Phase 2 — Harvester Deployment Manager (GUI)

**Source of decisions:** [docs/PHASE_2_Planning.md](docs/PHASE_2_Planning.md)

### Product summary

| Topic | Decision |
|-------|----------|
| **Audience** | Personal tool (author only for v1) |
| **Platform** | Cross-platform (Windows, Linux, macOS) — develop on Windows 11 first |
| **CLI relationship** | GUI **complements** `hdm`; both use the same Python core |
| **App title** | **Harvester Deployment Manager** |
| **CLI entrypoint** | `hdm` via `pip install` (short command for scripting) |
| **GUI entrypoint** | `harvest-deploy` via PyInstaller and/or `pip install` (Phase 2) |
| **Release target** | **v0.3.0** (iterate before a future v1.0 “major” GUI release) |

### MVP scope (v0.3.0)

Minimum shippable GUI (**history follows in later Phase 2 milestones**):

- **Dashboard** — grid of node cards
- **Deploy** — one / groups / all (match CLI targets)
- **Live logs** — dedicated Logs tab with per-node focus

Inventory CRUD, SQLite history, and PyInstaller polish follow in later milestones below.

### Technology

| Area | Choice |
|------|--------|
| UI framework | **PySide6** |
| Distribution | **PyInstaller** `.exe` (plus dev install from source) |
| Concurrency | **Single process**; `asyncio` orchestrator on a **Qt background thread**; signals/slots to UI |
| Core reuse | No subprocess CLI; call `harvester_deploy` library directly |
| SSH passphrases | **`keyring`** in GUI v1 (milestone 2c) |
| About / version | Icon + version from `pyproject.toml` |

### UI layout

- **Nodes tab** — action bar + grid of cards; filters: All / Harvesters / Farmers / Mainnet / Testnet
- **Badges** on each card: network (`mainnet` / `testnet`), role (`harvester` / `farmer`), install mode (`source` / `package`)
- **Logs tab** — per-card **Log** button focuses one node’s output (autoscroll v1)
- **Fleet summary tab** — farmer `chia farm summary`; Deploy disabled on package installs with “Package install — upgrade via .deb”
- **Upgrade available** — show commits behind `origin/latest` on card when &gt; 0

### Operations (deploy and refresh)

| Feature | v0.3.0 behavior |
|---------|----------------|
| Deploy targets | Same as CLI: `all`, `harvesters`, `farmers`, single node |
| Advanced options | Dialog: parallel, dry-run, force |
| Pre-deploy | **Confirmation modal** with checklist |
| Cancel deploy | **Not in v1** |
| Refresh | **On startup** + manual **Refresh fleet** |
| Per-card actions | **Doctor**, **Test SSH**, **History**, **Log**, **Deploy** |
| Deploy complete | In-app notification; summary table; failed cards **red** |
| Progress | Current recipe **step name** + **indeterminate** bar |

### Inventory and config (milestone 2c)

| Topic | Decision |
|-------|----------|
| Edit in GUI | Yes — add / edit / remove nodes |
| Required fields | `id`, `host`, `role`, `ssh_user`, `ssh_key_path`, `chia_root`, `chia_config_dir`; `farmer_host` for harvesters |
| Test SSH | On save and standalone Test button |
| Validation | Duplicate ids, valid role, farmer_host only on harvesters |
| Import/export YAML | Import from chosen YAML file; no export UI |
| Storage | **SQLite** canonical; **sync to `harvesters.yaml`** on save for CLI |
| SSH key | File picker; default `~/.ssh/id_ed25519`; **keyring** for passphrase |
| Utilities | **Choose config file**, **Open config folder** |

### History (milestone 2d)

| Topic | Decision |
|-------|----------|
| SQLite | Deploy runs metadata |
| JSON | Keep `deployments/*.json` for CLI |
| UI | Timeline **per node** |
| Retention | Keep all runs; include **skipped** (up-to-date) deploys |

### Out of scope for Phase 2 v1

- Cancel mid-deploy; deb/apt upgrade recipe; YAML export; log pause/copy/save; OS toasts

### Implementation milestones

| Milestone | Version | Delivers |
|-----------|---------|----------|
| **2a — Shell** | v0.3.0 | **Done** — main window, cards, badges, filters, refresh/doctor/test-ssh (`harvest-deploy`) |
| **2b — Deploy** | v0.3.0 | **Done** — deploy wizard, confirm modal, live log panel, progress bar, summary dialog, per-card deploy |
| **2c — Inventory** | v0.3.1 | **Done** — CRUD, validation, SQLite + YAML sync, keyring, open config folder |
| **2d — History** | v0.3.2 | **Done** — deploy runs in SQLite, per-node timeline, JSON import |
| **2e — Polish** | v0.3.3 | **Done** — farmer fleet summary tab, Mainnet/Testnet badges + filters, log/history actions, icon, clean PyInstaller build, smoke tests |

### Phase 2 success criteria

1. UI responsive during `install.sh`.
2. Deploy one / harvesters / farmers / all with live logs.
3. JABBA shown as farmer/package; deploy disabled; fleet summary available.
4. (2c+) Add 7th node from GUI.
5. (2d+) Per-node deploy history timeline.
6. Packaged Windows `.exe` starts empty and uses a persistent user config/data folder.

### Phase 3 — Observability and operator polish

**Source of decisions:** `docs/PHASE_3_Planning.md`

| Milestone | Version | Delivers |
|-----------|---------|----------|
| **3a — Fleet telemetry** | v0.3.5 | **Done** — parse farmer `chia farm summary`, 120s refresh, status-bar metrics, node-card plots/size/IP |
| **3b — Themes and preferences** | v0.3.5 | **Done** — Light/Dark mode, persisted theme choice, top-right toggle, session restore for theme/window state |
| **3c — Operator polish and diagnostics** | v0.3.5 | **Done** — ping + SSH health checks, unhealthy card borders, Fleet summary formatting, filtered log tools, Settings menu, configurable refresh interval |

### Phase 3 success criteria

1. Farmer summaries populate both the Fleet summary tab and the footer telemetry.
2. Node cards surface per-node health problems quickly via refresh-driven ping/SSH diagnostics.
3. The GUI remembers core operator preferences such as theme, refresh interval, and window state.
4. Logs tab tools operate on the visible filtered subset instead of the full buffer.
5. Phase 3 remains additive: deploy and inventory workflows continue to use the same stable core engine.

### Planned package layout (Phase 2)

```text
src/harvester_deploy/
  gui/                 # new — harvest-deploy entry, main_window, widgets, workers.py
  persistence/
    db.py              # new — SQLite
assets/                # app icon assets
%LOCALAPPDATA%/HarvesterDeploymentManager/
  config/harvesters.yaml
  data/hdm.db
  deployments/
```

---

## Project layout (current)

```text
HarvesterDeploymentManager/
  pyproject.toml
  assets/                  # app icon source files
  config/
  src/harvester_deploy/
    gui/                 # PySide6 — harvest-deploy
  scripts/               # icon + build helpers
  deployments/
  tests/
  docs/
    PHASE_2_Planning.md
    PHASE_3_Planning.md
    PHASE_4_Planning.md
    ARCHITECTURE.md
    RELEASE_v0.1.0.md
    RELEASE_v0.2.0.md
    RELEASE_v0.3.4.md
    RELEASE_v0.3.5.md
```

---

## SSH key setup (Windows → harvesters)

Use existing key: `C:\Users\stepp\.ssh\id_ed25519` (do **not** overwrite). Install only the **public** key: `id_ed25519.pub` — never pipe `id_ed25519` (private) to the server.

Connect by **hostname** on the LAN (e.g. `tarkin`) or by IP; both work if DNS/mDNS resolves.


| id        | SSH target (`host`) | IP (fallback) | Key setup |
| --------- | ------------------- | ------------- | --------- |
| tarkin    | `tarkin`            | 192.168.1.137 | Done      |
| kinnakeet | `kinnakeet`         | 192.168.1.145 | Pending   |
| vader     | `vader`             | 192.168.1.234 | Pending   |
| lando     | `lando`             | 192.168.1.235 | Pending   |
| wedge     | `wedge`             | 192.168.1.237 | Pending   |
| padme     | `padme`             | 192.168.1.249 | Pending   |


**Per harvester (repeat for kinnakeet, vader, lando, wedge, padme):**

```powershell
# 1) Install public key (password once; use .pub not private key)
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh steve@HOSTNAME "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

# 2) Verify — must NOT prompt for steve@ password
ssh -i $env:USERPROFILE\.ssh\id_ed25519 steve@HOSTNAME "hostname && ls ~/chia-blockchain"
```

Replace `HOSTNAME` with each row above (e.g. `kinnakeet`). First visit may ask `yes` to trust the host key.

**If a hostname does not resolve**, use the IP in place of `HOSTNAME` for that machine only.

**Optional (after all six work):** disable password auth in `/etc/ssh/sshd_config` on each host.

---

## Security and operations

- SSH **key auth** for automation; passwords not stored in the app
- Restrict `sshd` to controller IP (`192.168.1.183`) on harvesters if desired
- Run remote commands as a **non-root** user that owns `chia-blockchain`
- **Backup** `config.yaml` before every upgrade (step 2)
- Limit concurrency (2–3 max) to reduce LAN load and debugging pain
- Version-control app and recipes; never commit private keys or passwords
- Rollback: manual for v1 (restore backup + git checkout previous tag); automate later if needed

---

## Alternatives considered


| Option                        | Verdict                                                |
| ----------------------------- | ------------------------------------------------------ |
| Ansible playbooks             | Later, if steps need idempotency; call from Python     |
| Ansible AWX / Jenkins         | Overkill for 6 LAN hosts                               |
| .NET + SSH.NET + WPF          | Fine on Windows; weaker fit for Chia shell workflows   |
| Local web UI (FastAPI + HTMX) | Optional future; PySide6 preferred for six live panels |
| Harvester agents              | Unnecessary for current scale                          |


---

## Why this fits

- **Phase 1 / 1.5** — proven CLI and library on a real six-harvester + farmer fleet
- **Phase 2** — PySide6 front-end on the same engine; CLI remains for scripting
- **Phase 3** — observability and operator polish on top of the same engine: telemetry, health, settings, theming, and log tooling
- **Personal scope** — the app now covers daily-use GUI workflows for inventory, deploy, history, telemetry, and packaged Windows distribution

**Current status:** Phase 2 is complete through milestone **2e** and Phase 3 is complete through **3c**. Next work moves into Phase 4 planning for package/deb upgrade workflows, deploy cancel investigation, controller platform expansion, and broader future ideas.