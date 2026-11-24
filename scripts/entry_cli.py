"""PyInstaller entry point for the console vaultlog-cli.exe."""

import sys

from vaultlog.cli import main

if __name__ == "__main__":
    sys.exit(main())
