# Build Windows GUI executable with PyInstaller.
# Requires: pip install -e ".[gui]" pyinstaller

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
python scripts/make_icon.py
python scripts/write_version_info.py
python -m pip install pyinstaller -q
pyinstaller --clean --noconfirm harvest-deploy.spec

Write-Host ""
Write-Host "Output: dist\HarvesterDeploymentManager.exe"
