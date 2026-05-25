# Harvester Deployment Manager

Deploy [Chia](https://www.chia.net/) upgrades from a **Windows 11** controller to **Ubuntu** machines on your local network over **SSH** — dedicated harvesters and your **farmer** node (e.g. JABBA). Use the **`hdm`** CLI for scripting or **`harvest-deploy`** for the desktop dashboard (Phase 2).

## Features

- Fleet inventory via YAML (`config/harvesters.yaml`) — harvesters and farmer nodes
- Target groups: `all`, `harvesters`, `farmers`, or by id (`--target jabba` or `tarkin,padme`)
- Commands: `test-ssh`, `status`, `doctor`, `deploy`
- **Skip when current** — `upgrade_check` compares to `origin/latest` before stopping Chia (`--force` to override)
- **Config backup** — copies `~/.chia/mainnet/config` (and repo `config.yaml` when present)
- **Farmer check** — optional `farmer_host` post-deploy connectivity via DNS + `chia farm summary`
- **Role-aware start** — `chia start harvester` vs `chia start farmer` per node
- Git-based upgrade recipe (`git checkout latest`, `install.sh`, `chia init`, start)
- Parallel deployments, live logs, JSON summaries under `deployments/`
- Recovery mode for interrupted upgrades; automatic `chia init --fix-ssl-permissions`

- **`--quiet` / `-q`** — suppress per-step log lines; show only the final table or doctor panels

## Requirements


| Component     | Version                                           |
| ------------- | ------------------------------------------------- |
| Controller OS | Windows 10/11 (developed on Windows 11)           |
| Python        | 3.11+                                             |
| Harvesters    | Ubuntu with Chia installed at `~/chia-blockchain` |
| Network       | LAN; SSH port 22 (default)                        |
| Auth          | SSH key (passwordless login recommended)          |

### Supported install types

| Install method | `deploy` | `status` / `doctor` |
| -------------- | -------- | ------------------- |
| **Source** — git clone at `chia_root` + `install.sh` | Yes | Yes |
| **Package** — `.deb`/GUI, `chia` on PATH, no `chia_root` tree | No (clear error at precheck) | Yes (`chia version`, `chia farm summary`) |

The tool auto-detects **source** vs **package** per host. **`chia farm summary` runs on farmer nodes only** (full fleet view). Harvester nodes report version, git drift, and harvester process status instead.

```powershell
hdm doctor --target jabba
hdm status --target jabba
```

## Download and install

### 1. Clone the repository

```powershell
git clone https://github.com/steppsr/HarvesterDeploymentManager.git
cd HarvesterDeploymentManager
```

### 2. Create a virtual environment (recommended)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install the package

CLI only:

```powershell
python -m pip install -e .
```

CLI + GUI:

```powershell
python -m pip install -e ".[gui]"
```

Verify:

```powershell
hdm --help
harvest-deploy --help
```

### Command names

| Command | Role |
| ------- | ---- |
| `hdm` | CLI — `test-ssh`, `status`, `doctor`, `deploy` |
| `harvest-deploy` | Desktop GUI — fleet dashboard (milestone 2a+) |

The pip package name stays `harvester-deploy`.

### Desktop GUI (milestone 2a)

```powershell
harvest-deploy
```

- Grid of **node cards** (network + role + install-mode badges)
- Filter: **All** / **Harvesters** / **Farmers** / **Mainnet** / **Testnet**
- **Refresh fleet** on startup and from the **Nodes** tab (same data as `hdm status`)
- Per card: **Doctor**, **Test SSH**, **History**, **Log**, **Deploy**
- **Upgrade available** hint when git is behind `origin/latest`

**Milestone 2b** adds **Deploy…** (targets + advanced options), confirm dialog, **Logs** tab, per-card **Log**, per-card **Deploy**, and a completion summary.

**Milestone 2c** adds **Fleet → Manage inventory…** — add, edit, and remove nodes; validation; **Test SSH** in the editor; optional **keyring** passphrases; saves to SQLite (`data/hdm.db`) and syncs `config/harvesters.yaml` for the CLI. **Choose config file…** and **Import from YAML…** use a file picker; **Open config folder** opens the active config directory in Explorer.

**Milestone 2d** adds **deploy history** — each deploy (and dry run) is stored in SQLite; **Fleet → Deploy history…** or per-card **History** shows a timeline per node (including skipped up-to-date runs). Past `deployments/*/summary.json` files can be imported on first open or via **Import JSON…**. The CLI still writes JSON summaries for scripting.

**Milestone 2e** adds **Mainnet / Testnet** badges on cards, **Show** filters (including Mainnet only / Testnet only), tabbed layout (**Nodes** / **Fleet summary** / **Logs**), app icon, clean PyInstaller builds, and a true empty first-run experience for the packaged `.exe`.

### Mainnet / Testnet per node

Set `network: mainnet` or `network: testnet` in `harvesters.yaml` (or in **Manage inventory**). This is for **badges and filters only** — it does not change `chia_config_dir` (most installs keep `~/.chia/mainnet/config` even on testnet). Nodes without `network` default to **mainnet**.

### Build Windows GUI executable

```powershell
pip install -e ".[gui]"
pip install pyinstaller
.\scripts\build-gui.ps1
```

Output: `dist\HarvesterDeploymentManager.exe`. Run `python scripts\make_icon.py` first if icons are missing.

**Installed app config** (not the PyInstaller temp folder):

| Path | Purpose |
|------|---------|
| `%LOCALAPPDATA%\HarvesterDeploymentManager\config\harvesters.yaml` | Default YAML location (starts missing on a brand-new install until you import or save inventory) |
| `%LOCALAPPDATA%\HarvesterDeploymentManager\data\hdm.db` | Fleet inventory SQLite — **still used if you delete YAML but leave the DB** |
| `%LOCALAPPDATA%\HarvesterDeploymentManager\settings.yaml` | Optional path you picked with **Choose config file…** or **Import from YAML…** (not your dev repo unless you chose that file) |

The packaged `.exe` starts with **no predefined nodes**. To use an existing fleet file, choose **Fleet → Choose config file…** or **Manage inventory → Import from YAML…** and point at your `harvesters.yaml`.

The release `.exe` does **not** embed your local development path. To fully reset the installed app, delete the whole `%LOCALAPPDATA%\HarvesterDeploymentManager` folder, then start the exe again.

## SSH setup (one-time per harvester)

The tool does **not** store passwords. Use an SSH key on your Windows machine.

### 1. Use an existing key or create one

```powershell
# Only if you do not already have a key:
ssh-keygen -t ed25519 -C "hdm@your-pc"
```

Default path: `C:\Users\<you>\.ssh\id_ed25519`

Do **not** overwrite an existing key if other systems use it.

### 2. Copy the **public** key to each harvester

Use the `.pub` file only:

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh YOUR_USER@HARVESTER_HOST "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

Replace `YOUR_USER` and `HARVESTER_HOST` (hostname or IP). Enter your password once per host.

### 3. Verify passwordless login

```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519 YOUR_USER@HARVESTER_HOST "hostname && ls ~/chia-blockchain"
```

You should **not** be prompted for `YOUR_USER@...` password.

### 4. Trust host keys

The first connection to each host may ask to accept the host fingerprint. Type `yes`.

## Configuration

### 1. Create your local inventory

`config/harvesters.yaml` is **gitignored** (it contains your LAN hosts). Copy the example:

```powershell
copy config\harvesters.example.yaml config\harvesters.yaml
```

### 2. Edit `config/harvesters.yaml`

Set under `defaults` (or per host):


| Field             | Description                                                |
| ----------------- | ---------------------------------------------------------- |
| `ssh_user`        | Linux user (e.g. `steve`)                                  |
| `ssh_key_path`    | Private key path (e.g. `~/.ssh/id_ed25519`)                |
| `chia_root`       | Chia git repo (usually `~/chia-blockchain`)                |
| `chia_config_dir` | Live config dir (default `~/.chia/mainnet/config`)         |
| `git_branch`      | Release branch (usually `latest`)                          |
| `role`            | `harvester` (default) or `farmer`                          |
| `farmer_host`     | Farmer hostname for post-deploy check (harvesters only)    |

Per node, set `id`, `display_name`, `host`, and `last_known_version`.

**Farmer node example** (starts full node with `chia start farmer`):

```yaml
  - id: jabba
    display_name: JABBA
    host: jabba
    role: farmer
```

**Harvester with farmer check:**

```yaml
  - id: tarkin
    host: tarkin
    role: harvester
    farmer_host: jabba
```

## Testing before you deploy

Run these in order from the project directory:

```powershell
# 1) SSH connectivity
hdm test-ssh

# 2) Installed Chia version per host
hdm status

# 3) Health checks (paths, git, version)
hdm doctor

# 4) Dry run — lists steps, no remote changes
hdm deploy --target all --parallel 2 --dry-run
```

Test a single host first:

```powershell
hdm test-ssh --target my-harvester
hdm deploy --target my-harvester --dry-run
```

## Deploying an upgrade

**Warning:** `deploy` stops Chia, removes virtualenvs, updates git, runs `install.sh`, and restarts the harvester. Plan for downtime; test one machine before upgrading the fleet.

```powershell
# One node
hdm deploy --target tarkin

# Harvesters only (excludes farmer node)
hdm deploy --target harvesters --parallel 2

# Farmer machine only
hdm deploy --target jabba

# Several ids
hdm deploy --target tarkin,padme --parallel 2

# Everything enabled in harvesters.yaml
hdm deploy --target all --parallel 2

# Force full upgrade even when git reports up to date
hdm deploy --target tarkin --force
```

If git is already on `origin/latest`, deploy **skips** stop/install and reports `skipped (up to date)` unless you pass `--force`.

Exit codes: `0` = all succeeded, `1` = all failed, `2` = partial failure.

Logs are written to `deployments/<timestamp>/summary.json` (also recorded in `data/hdm.db` when using the GUI or CLI `deploy`).

`hdm status` shows a **Behind** column (commits behind `origin/latest`). `doctor` includes `git_behind` and `farmer_host` when set.

For table-only output without per-host step logs:

```powershell
hdm status --quiet
```

## Project layout

```text
HarvesterDeploymentManager/
  config/
    harvesters.example.yaml   # committed template
    harvesters.yaml           # local only (gitignored)
    recipes/
  src/harvester_deploy/       # application code
  deployments/                # run output (gitignored)
  ARCHITECTURE.md             # design notes
  How to Upgrade Chia.md      # manual upgrade reference
```

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).

## Further reading

- [ARCHITECTURE.md](ARCHITECTURE.md) — phases, recipe steps, security notes

