"""PyInstaller entry point for the windowed VaultLog.exe.

Usage: VaultLog.exe [--vault PATH]
"""

import argparse

from vaultlog.config import default_vault_path
from vaultlog.gui import run

if __name__ == "__main__":
    p = argparse.ArgumentParser(prog="VaultLog")
    p.add_argument("--vault", default=str(default_vault_path()))
    args, _ = p.parse_known_args()
    run(args.vault)
