# Chia Harvester Deployment Tool — Architecture

A modular, **Python-centric controller** on Windows 11 orchestrates **agentless SSH** upgrades on six Ubuntu harvesters on the local LAN. Phase 1 delivers a reusable library and CLI; Phase 2 adds a desktop GUI that reuses the same core—no rewrite.

**Related docs:** `How to Upgrade Chia.md` (manual upgrade steps), `Architecture.html` (visual summary).

---

## Goals

| Phase | Goal |
|-------|------|
| **Phase 1** | From Windows: SSH to one or all harvesters, run the upgrade pipeline, stream progress, report per-host success/failure. |
| **Phase 2** | GUI: manage harvester inventory, deploy one or all, separate live monitor per harvester, deployment history. |

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

| Layer | Responsibility |
|-------|----------------|
| **CLI / GUI** | User commands, layout, buttons |
| **Orchestrator** | Run jobs on one or many hosts; concurrency limit; cancel where possible |
| **Deployment engine** | Execute recipe steps; emit events |
| **SSH transport** | Connect, exec, stream output, optional SFTP |
| **Domain** | `Harvester`, `DeployJob`, `Step`, `JobState`, events |
| **Persistence** | Inventory (YAML); history (SQLite in Phase 2) |

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

| Area | Choice | Notes |
|------|--------|--------|
| Language | Python 3.11+ | Aligns with Chia; runs on Windows controller |
| Packaging | `pyproject.toml` (`uv` or Poetry) | |
| Phase 1 CLI | Typer | `deploy`, `status`, `doctor`, `test-ssh` |
| SSH | **asyncssh** + asyncio | Strong streaming for long `install.sh` runs |
| Config validation | Pydantic | Load `harvesters.yaml` |
| Phase 1 inventory | YAML | Git-friendly; secrets outside repo |
| Phase 2 GUI | **PySide6** | Six live log panels; non-blocking via asyncio/thread bridge |
| Phase 2 history | SQLite | Deployments, errors, timestamps |
| Secrets | `keyring` | Windows Credential Manager for key passphrases if needed |

**Defer until recipes are stable:** Ansible playbooks (optional call from Python later). Avoid K8s, CI servers, or harvester-side agents for this scale.

---

## Harvester inventory

### What to list per harvester

Split into **you already know**, **confirm once per machine**, and **optional but useful**.

#### Required (minimum to automate your upgrade flow)

| Field | Purpose | Your fleet |
|-------|---------|------------|
| `id` | Stable key for CLI/GUI (`--target tarkin`) | See table below |
| `display_name` | Human label in UI | Same as id, title case |
| `host` | SSH target (IP or DNS) | LAN IPs below |
| `ssh_port` | SSH port | Default `22` unless changed |
| `ssh_user` | Linux login | `steve` (all six) |
| `ssh_key_path` | Private key on Windows controller | **Confirm** — e.g. `%USERPROFILE%\.ssh\id_ed25519` |
| `chia_root` | Repo directory on harvester | Default `~/chia-blockchain` |
| `last_known_version` | Baseline for reports / drift | `2.7.0` on all six today |

#### Strongly recommended (same upgrade on every host)

| Field | Purpose | Default for your recipe |
|-------|---------|-------------------------|
| `activate_cmd` | Enter venv before Chia commands | `. ./activate` (run from `chia_root`) |
| `git_branch` | Checkout target | `latest` |
| `upgrade_mode` | How code is updated | `git` (matches your manual flow) |
| `enabled` | Skip in `deploy --target all` if false | `true` |

#### Optional (health checks, ops, Phase 2 polish)

| Field | Purpose |
|-------|---------|
| `farmer_host` | Post-upgrade: verify harvester sees farmer (if you use a shared farmer) |
| `tags` | e.g. `rack-a`, `nvme` |
| `notes` | Free text |
| `systemd_harvester_unit` | Only if you use systemd instead of `chia start` (your manual flow does not) |
| `backup_dir` | Where pre-upgrade config backups go on remote host |
| `max_parallel_group` | Override global concurrency for fragile hosts |

**Do not store in git:** private key passphrases, passwords. Use `keyring` or OS store; reference key path only in YAML.

### Known harvesters (2026-05-22)

| id | display_name | host | last_known_version |
|----|--------------|------|--------------------|
| `tarkin` | TARKIN | 192.168.1.137 | 2.7.0 |
| `kinnakeet` | KINNAKEET | 192.168.1.145 | 2.7.0 |
| `vader` | VADER | 192.168.1.234 | 2.7.0 |
| `lando` | LANDO | 192.168.1.235 | 2.7.0 |
| `wedge` | WEDGE | 192.168.1.237 | 2.7.0 |
| `padme` | PADME | 192.168.1.249 | 2.7.0 |

### SSH connectivity (verified 2026-05-22)

Test from Windows controller (`ssh steve@192.168.1.137`):

| Finding | Value |
|---------|--------|
| Login | `steve` works |
| Auth today | **Password** (prompted after host key accept) |
| Auth target for automation | **SSH key** (no password in scripts) |
| OS (TARKIN) | Ubuntu 24.04.2 LTS, kernel 6.8.0-53-generic |
| Remote hostname | `tarkin` (shell prompt `steve@tarkin`) |
| Host key | ED25519 — `SHA256:SeHPMrJIwmroMXacoef/AFj1LL2wV4b20AthhUpY0Aw` (in Windows `known_hosts` after first connect) |
| Controller LAN IP | `192.168.1.183` (from harvester `Last login` line) |

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

| Step | id | Remote actions (summary) |
|------|-----|---------------------------|
| 1 | `precheck` | SSH OK; `cd $chia_root`; `git status` / disk sanity |
| 2 | `backup_config` | Copy `config.yaml` (and certs if present) to timestamped backup dir |
| 3 | `stop_services` | `. ./activate` → `chia stop -d all` → `deactivate` |
| 4 | `remove_venvs` | `rm -rf venv .penv .venv` (from `chia_root`) |
| 5 | `git_update` | `git fetch` → `git checkout latest` → `git reset --hard FETCH_HEAD --recurse-submodules` |
| 6 | `git_clean_check` | `git status` — fail if dirty tree (uncommitted changes / wrong `RELEASE.dev0`) |
| 7 | `install` | `sh install.sh` (long-running; stream output) |
| 8 | `activate` | `. ./activate` |
| 9 | `chia_init` | `chia init`; if SSL permission warnings, `chia init --fix-ssl-permissions` |
| 10 | `start_harvester` | `chia start harvester` |
| 11 | `postcheck` | `chia version`; confirm harvester process / farmer connectivity if configured |

**CLI flags (Phase 1):**

- `deploy --target all|tarkin|...` — default all enabled hosts
- `--parallel 2` — cap concurrent upgrades (default 2)
- `--dry-run` — print steps without mutating remotes
- `--recipe default` — future: alternate recipes

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

### Phase 1.5 (recommended before GUI)

- `status` — version + process state only
- `doctor` — SSH, paths, git clean, optional farmer ping

### Phase 2 — Desktop controller

**Deliverables**

- Harvester CRUD + **Test SSH** on add
- Dashboard: six cards (status, version, last deploy)
- **Deploy one** / **Deploy all**; cancel where SSH session allows
- Per-harvester panel: live log, current step, progress
- SQLite deployment history

**Success criteria**

- UI stays responsive during `install.sh`
- Add 7th harvester via config/UI only

---

## Project layout (target)

```text
HarvesterDeploymentTool/
  pyproject.toml
  config/
    harvesters.example.yaml
    harvesters.yaml              # local; gitignore if needed
    recipes/
      chia-upgrade-default.yaml
  src/harvester_deploy/
    domain/
    ssh/
    recipes/
    orchestrator/
    persistence/
    cli.py
  deployments/                   # run logs + JSON summaries
  tests/
  docs/
    ARCHITECTURE.md
    How to Upgrade Chia.md
```

---

## SSH key setup (Windows → harvesters)

Use existing key: `C:\Users\stepp\.ssh\id_ed25519` (do **not** overwrite). Install only the **public** key: `id_ed25519.pub` — never pipe `id_ed25519` (private) to the server.

Connect by **hostname** on the LAN (e.g. `tarkin`) or by IP; both work if DNS/mDNS resolves.

| id | SSH target (`host`) | IP (fallback) | Key setup |
|----|---------------------|---------------|-----------|
| tarkin | `tarkin` | 192.168.1.137 | Done |
| kinnakeet | `kinnakeet` | 192.168.1.145 | Pending |
| vader | `vader` | 192.168.1.234 | Pending |
| lando | `lando` | 192.168.1.235 | Pending |
| wedge | `wedge` | 192.168.1.237 | Pending |
| padme | `padme` | 192.168.1.249 | Pending |

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

| Option | Verdict |
|--------|---------|
| Ansible playbooks | Later, if steps need idempotency; call from Python |
| Ansible AWX / Jenkins | Overkill for 6 LAN hosts |
| .NET + SSH.NET + WPF | Fine on Windows; weaker fit for Chia shell workflows |
| Local web UI (FastAPI + HTMX) | Optional future; PySide6 preferred for six live panels |
| Harvester agents | Unnecessary for current scale |

---

## Why this fits

- **Phase 1** is a small, testable core aligned with your real upgrade commands
- **Phase 2** is a new front-end, not a fork of scripts
- **Six harvesters** stay simple: no cluster manager, no per-host daemons
- **Extensible:** new recipe, new host row in YAML, optional farmer checks

**Next implementation steps:** set up SSH keys on all six hosts; verify `ssh -i ~/.ssh/id_ed25519 steve@192.168.1.137` without a password prompt; confirm `~/chia-blockchain` on TARKIN; copy `harvesters.example.yaml` → `harvesters.yaml`; implement recipe steps 1–11 against TARKIN, then roll to all.
