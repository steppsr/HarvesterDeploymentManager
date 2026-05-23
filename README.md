# Harvester Deployment Tool

Deploy [Chia](https://www.chia.net/) harvester upgrades from a **Windows 11** controller to **Ubuntu** harvesters on your local network over **SSH**. Phase 1 provides a CLI; a desktop GUI is planned for a later phase.

## Features

- Fleet inventory via YAML (`config/harvesters.yaml`)
- Commands: `test-ssh`, `status`, `doctor`, `deploy`
- Git-based upgrade recipe matching the standard Chia harvester workflow (`git checkout latest`, `install.sh`, `chia init`, start harvester)
- Parallel deployments with a concurrency limit
- Live log streaming per harvester
- JSON summaries under `deployments/` (not committed to git)
- Recovery mode when a prior run stopped Chia and removed venvs but did not finish `install.sh`
- Automatic `chia init --fix-ssl-permissions` when SSL warnings appear

## Requirements


| Component     | Version                                           |
| ------------- | ------------------------------------------------- |
| Controller OS | Windows 10/11 (developed on Windows 11)           |
| Python        | 3.11+                                             |
| Harvesters    | Ubuntu with Chia installed at `~/chia-blockchain` |
| Network       | LAN; SSH port 22 (default)                        |
| Auth          | SSH key (passwordless login recommended)          |


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


| Field          | Description                                          |
| -------------- | ---------------------------------------------------- |
| `ssh_user`     | Linux user (e.g. `steve`)                            |
| `ssh_key_path` | Private key path (e.g. `~/.ssh/id_ed25519`)          |
| `chia_root`    | Chia repo on harvester (usually `~/chia-blockchain`) |
| `git_branch`   | Release branch (usually `latest`)                    |


Per harvester, set `id`, `display_name`, `host` (hostname or IP), and `last_known_version` for your records.

### 3. Optional: Chia config backup path

The recipe backs up `config.yaml` in the chia repo if present. Your live config may be under `~/.chia/mainnet/config/` on the harvester; back that up separately if needed.

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
# One harvester
harvester-deploy deploy --target my-harvester

# Several (comma-separated)
harvester-deploy deploy --target host1,host2 --parallel 2

# All enabled hosts in harvesters.yaml
harvester-deploy deploy --target all --parallel 2
```

Exit codes: `0` = all succeeded, `1` = all failed, `2` = partial failure.

Logs are written to `deployments/<timestamp>/summary.json`.

### Check if an upgrade is needed (manual)

```powershell
ssh YOUR_USER@HARVESTER_HOST "cd ~/chia-blockchain && git fetch -q && git rev-list HEAD..origin/latest --count"
```

`0` means already on `origin/latest` (the tool still runs the full recipe unless a version gate is added later).

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

