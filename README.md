# VaultLog

[![CI](https://github.com/aayush-1910/VaultLog/actions/workflows/ci.yml/badge.svg)](https://github.com/aayush-1910/VaultLog/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/aayush-1910/VaultLog)](https://github.com/aayush-1910/VaultLog/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

VaultLog is a journaling project I’m building in Python. The idea is simple: keep everything offline and secure so entries stay private. Each log is encrypted with AES before it’s saved, and you can add entries through either a basic CLI or a small GUI. Every entry is timestamped, and there’s an in-memory search to go through logs without exposing the raw files.

## Features
- AES encryption for all entries  
- CLI and GUI support for writing logs  
- Automatic timestamps  
- In-memory search  
- Works fully offline  

## Purpose
Most journaling tools store data in the cloud. VaultLog is meant for people who prefer to keep their thoughts and notes local, private, and under their control. It’s a simple start, but something I’ll keep improving as I learn.  

## Download (Windows)
Grab the latest release from the [Releases page](https://github.com/aayush-1910/VaultLog/releases/latest):

| File | What it is |
|---|---|
| `VaultLog.exe` | The GUI app. Double-click to run. |
| `vaultlog-cli.exe` | The command-line tool. Run it from a terminal, e.g. `vaultlog-cli.exe list`. |
| `VaultLog-x.y.z-windows-x64.zip` | Both executables plus README and LICENSE. |
| `SHA256SUMS.txt` | Checksums for verifying the downloads. |

Both are standalone and need no Python install. Windows SmartScreen may warn about an unrecognized app because the executables are not code-signed. Click **More info → Run anyway**.

Verify a download in PowerShell: `Get-FileHash VaultLog.exe -Algorithm SHA256`, then compare the result with `SHA256SUMS.txt`.

## Installation from source
Requires Python 3.10+.

```bash
pip install -e .          # installs the `vaultlog` and `vaultlog-gui` commands
# or just: pip install -r requirements.txt  and use `python -m vaultlog`
```

## Usage

### CLI
```bash
vaultlog init                                  # create a vault (asks for a password)
vaultlog add -m "Today I learned about AES" --tags study,crypto
vaultlog add -t "Long entry"                   # type a multi-line entry, end with Ctrl+D (Ctrl+Z Enter on Windows)
vaultlog list -n 10                            # newest first
vaultlog search budget tag:work                # all terms must match; tag:x filters by tag
vaultlog show 66aa0cf8                         # full id or unique prefix
vaultlog edit 66aa0cf8 -m "new text" --tags personal
vaultlog delete 66aa0cf8
vaultlog passwd                                # change password (entries are not re-encrypted)
vaultlog export backup.json                    # PLAINTEXT export - handle with care
vaultlog import backup.json                    # duplicates are skipped
vaultlog gui                                   # open the GUI
```

The vault file defaults to `~/.vaultlog/journal.vault`. Override it with `--vault PATH` or the `VAULTLOG_PATH` environment variable.

### GUI
Run `vaultlog-gui`, `vaultlog gui` or `python -m vaultlog.gui`. You can unlock or create a vault, browse entries, search live, and write or edit entries (Ctrl+N new, Ctrl+S save, Ctrl+F search). The window locks itself after 10 minutes of inactivity.

## How the encryption works
- A random 256-bit **data key** encrypts every entry with **AES-256-GCM**. GCM is authenticated, so tampering is detected.
- The data key is wrapped with a key derived from your password using **scrypt** (N=2^17, r=8, p=1, random salt).
- Everything about an entry (title, body, tags, timestamps) is inside the ciphertext. On disk, the SQLite file holds only random entry ids and encrypted blobs.
- Each ciphertext is bound to its entry id, so encrypted rows cannot be swapped between entries.
- Search decrypts entries in memory only. Nothing decrypted is written to disk.

## Project layout
```
vaultlog/
  crypto.py   # AES-GCM + scrypt key derivation
  vault.py    # encrypted SQLite storage, entries, search, import/export
  cli.py      # command-line interface
  gui.py      # Tkinter GUI
  config.py   # default vault location
scripts/      # PyInstaller entry points, build script, icon generator
assets/       # app icon
tests/        # pytest suite
.github/      # CI and release workflows
```

## Development
```bash
pip install -e ".[dev,build]"
python -m pytest                 # run tests
python scripts/build.py --zip    # build dist/VaultLog.exe, dist/vaultlog-cli.exe and a release zip
```

### Releasing
1. Bump `__version__` in `vaultlog/__init__.py` and add a section to `CHANGELOG.md`.
2. Commit, then tag and push: `git tag v0.2.0 && git push origin v0.2.0`.
3. The **Release** workflow runs the tests, builds the executables, smoke-tests them and publishes a GitHub release with the files attached.

## Limitations
- Losing the password/key means losing access to the data  
- In-memory search may slow down with very large log sets  
- GUI is minimal for now

## Roadmap
- ~~Better key handling~~ (password-wrapped data key, password change)  
- ~~Encrypted database integration (SQLite)~~  
- Cleaner UI/UX  
- ~~Import/export support~~ (JSON; encrypted export planned)  

## Open source
VaultLog is free and open source under the [MIT License](LICENSE). You can use it, read every line of the code, fork it and change it however you like. That matters for a privacy tool: you don't have to trust me, you can check exactly what happens to your data.

Contributions are welcome, from bug reports and ideas to pull requests. Open an [issue](https://github.com/aayush-1910/VaultLog/issues), or fork the repo, make your change and send a PR. Please run `python -m pytest` before submitting.

## Status
Active development.