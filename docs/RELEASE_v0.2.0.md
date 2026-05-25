## Summary

Phase 1.5 release: safer upgrades, farmer node support, and package-install detection (e.g. `.deb` farmer on JABBA).

## Highlights

- **Skip when current** — `upgrade_check` skips deploy if already on `origin/latest` (`--force` to override)
- **Config backup** — backs up `~/.chia/mainnet/config` plus repo `config.yaml`
- **Farmer nodes** — `role: farmer` uses `chia start farmer`; target groups `harvesters` / `farmers`
- **Package install detection** — `chia` on PATH without git clone; `doctor`/`status` work; `deploy` explains limitation
- **Remote path fix** — `~/chia-blockchain` expands correctly over SSH
- **`chia farm summary`** — farmer nodes only; harvesters report process status
- **Optional `farmer_host`** — post-deploy DNS + process checks on harvesters

## Upgrade from v0.1.0

```powershell
git pull
python -m pip install -e .
```

Update `config/harvesters.yaml` with new optional fields (`role`, `farmer_host`, `chia_config_dir`). See `config/harvesters.example.yaml`.

## CLI changes

| Change | Detail |
| --- | --- |
| `--target harvesters` | Harvester-role nodes only |
| `--target farmers` | Farmer-role nodes only |
| `--force` | Run full deploy even when git is up to date |

## Known limitations

- Git/source `deploy` still requires a clone at `chia_root`
- Package-based farmers: use OS package manager or add a source clone for `deploy`

## Note (v0.2.1+)

The CLI console script was renamed from `harvester-deploy` to **`hdm`**. Re-run `pip install -e .` after upgrading. Phase 2 GUI will use **`harvest-deploy`** as its launcher.
