"""Build release executables with PyInstaller.

    python scripts/build.py            # builds dist/VaultLog.exe and dist/vaultlog-cli.exe
    python scripts/build.py --zip      # also creates dist/VaultLog-<version>-windows-x64.zip

Requires: pip install -e ".[build]"
"""

from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
ICON = ROOT / "assets" / "vaultlog.ico"

sys.path.insert(0, str(ROOT))
from vaultlog import __version__  # noqa: E402

VERSION_TEMPLATE = """\
VSVersionInfo(
  ffi=FixedFileInfo(filevers={tup}, prodvers={tup}, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'VaultLog'),
      StringStruct('FileDescription', '{desc}'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', '{name}'),
      StringStruct('LegalCopyright', 'MIT License'),
      StringStruct('OriginalFilename', '{name}.exe'),
      StringStruct('ProductName', 'VaultLog'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def version_file(name: str, desc: str) -> Path:
    nums = [int(x) for x in __version__.split(".")[:3] if x.isdigit()]
    tup = tuple((nums + [0, 0, 0, 0])[:4])
    path = BUILD / f"{name}-version.txt"
    path.write_text(VERSION_TEMPLATE.format(tup=tup, ver=__version__, name=name, desc=desc), "utf-8")
    return path


def pyinstaller(script: str, name: str, desc: str, windowed: bool) -> None:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(ROOT / "scripts" / script),
        "--name", name,
        "--onefile",
        "--clean",
        "--noconfirm",
        "--distpath", str(DIST),
        "--workpath", str(BUILD / name),
        "--specpath", str(BUILD),
        "--paths", str(ROOT),
        "--exclude-module", "pytest",
    ]
    cmd.append("--windowed" if windowed else "--console")
    if ICON.exists():
        cmd += ["--icon", str(ICON)]
    if platform.system() == "Windows":
        cmd += ["--version-file", str(version_file(name, desc))]
    print(">", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def make_zip() -> Path:
    arch = "x64" if platform.machine().endswith("64") else platform.machine().lower()
    out = DIST / f"VaultLog-{__version__}-{platform.system().lower()}-{arch}.zip"
    ext = ".exe" if platform.system() == "Windows" else ""
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in (f"VaultLog{ext}", f"vaultlog-cli{ext}"):
            z.write(DIST / f, f)
        for f in ("README.md", "LICENSE", "CHANGELOG.md"):
            if (ROOT / f).exists():
                z.write(ROOT / f, f)
    return out


def write_checksums() -> None:
    lines = []
    for f in sorted(DIST.iterdir()):
        if f.is_file() and f.suffix != ".txt":
            lines.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}")
    (DIST / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", action="store_true", help="also create a release zip")
    args = ap.parse_args()

    shutil.rmtree(DIST, ignore_errors=True)
    shutil.rmtree(BUILD, ignore_errors=True)
    BUILD.mkdir(parents=True)

    pyinstaller("entry_gui.py", "VaultLog", "VaultLog encrypted journal", windowed=True)
    pyinstaller("entry_cli.py", "vaultlog-cli", "VaultLog command-line interface", windowed=False)
    if args.zip:
        print(f"Created {make_zip()}")
    write_checksums()
    print(f"\nBuilt VaultLog {__version__} -> {DIST}")


if __name__ == "__main__":
    main()
