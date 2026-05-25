"""Generate PyInstaller Windows version metadata from pyproject.toml."""

from __future__ import annotations

from pathlib import Path
import tomllib


def _version_tuple(version: str) -> tuple[int, int, int, int]:
    parts = [int(part) for part in version.split(".") if part.isdigit()]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    version = project["version"]
    version_tuple = _version_tuple(version)
    build_dir = root / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    out = build_dir / "version_info.txt"

    out.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Steve Stepp'),
          StringStruct('FileDescription', 'Harvester Deployment Manager'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'HarvesterDeploymentManager'),
          StringStruct('LegalCopyright', 'Copyright (c) 2026 Steve Stepp'),
          StringStruct('OriginalFilename', 'HarvesterDeploymentManager.exe'),
          StringStruct('ProductName', 'Harvester Deployment Manager'),
          StringStruct('ProductVersion', '{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
        encoding="utf-8",
    )
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
