# PyInstaller spec for Harvester Deployment Manager (Windows).
# Build: pip install pyinstaller && pyinstaller harvest-deploy.spec

import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

a = Analysis(
    [str(root / "src" / "harvester_deploy" / "gui" / "app.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[
        (str(root / "assets"), "harvester_deploy/assets"),
        (str(root / "config" / "recipes"), "config/recipes"),
        (str(root / "config" / "harvesters.example.yaml"), "config"),
    ],
    hiddenimports=[
        "asyncssh",
        "harvester_deploy",
        "harvester_deploy.gui.main_window",
        "harvester_deploy.persistence.history",
        "keyring.backends.Windows",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="HarvesterDeploymentManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(root / "build" / "version_info.txt")
    if (root / "build" / "version_info.txt").is_file()
    else None,
    icon=str(root / "assets" / "hdm.ico")
    if (root / "assets" / "hdm.ico").is_file()
    else None,
)
