# Harvester Deployment Tool

Deploy [Chia](https://www.chia.net/) upgrades from a **Windows 11** controller to **Ubuntu** machines on your local network over **SSH** — dedicated harvesters and your **farmer** node (e.g. JABBA). Phase 1.5 extends the CLI; a desktop GUI is planned for Phase 2.

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
harvester-deploy doctor --target jabba
harvester-deploy status --target jabba
```

## Download and install

### 1. Clone the repository

```powershell
git clone https://github.com/steppsr/HarvesterDeploymentTool.git
cd HarvesterDeploymentTool
```

### 2. Create a virtual environment (recommended)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install the package

```powershell
python -m pip install -e .
```

Verify:

```powershell
harvester-deploy --help
```

## SSH setup (one-time per harvester)

The tool does **not** store passwords. Use an SSH key on your Windows machine.

### 1. Use an existing key or create one

```powershell
# Only if you do not already have a key:
ssh-keygen -t ed25519 -C "harvester-deploy@your-pc"
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
harvester-deploy test-ssh

# 2) Installed Chia version per host
harvester-deploy status

# 3) Health checks (paths, git, version)
harvester-deploy doctor

# 4) Dry run — lists steps, no remote changes
harvester-deploy deploy --target all --parallel 2 --dry-run
```

Test a single host first:

```powershell
harvester-deploy test-ssh --target my-harvester
harvester-deploy deploy --target my-harvester --dry-run
```

## Deploying an upgrade

**Warning:** `deploy` stops Chia, removes virtualenvs, updates git, runs `install.sh`, and restarts the harvester. Plan for downtime; test one machine before upgrading the fleet.

```powershell
# One node
harvester-deploy deploy --target tarkin

# Harvesters only (excludes farmer node)
harvester-deploy deploy --target harvesters --parallel 2

# Farmer machine only
harvester-deploy deploy --target jabba

# Several ids
harvester-deploy deploy --target tarkin,padme --parallel 2

# Everything enabled in harvesters.yaml
harvester-deploy deploy --target all --parallel 2

# Force full upgrade even when git reports up to date
harvester-deploy deploy --target tarkin --force
```

If git is already on `origin/latest`, deploy **skips** stop/install and reports `skipped (up to date)` unless you pass `--force`.

Exit codes: `0` = all succeeded, `1` = all failed, `2` = partial failure.

Logs are written to `deployments/<timestamp>/summary.json`.

`harvester-deploy status` shows a **Behind** column (commits behind `origin/latest`). `doctor` includes `git_behind` and `farmer_host` when set.

## Project layout

```text
HarvesterDeploymentTool/
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

