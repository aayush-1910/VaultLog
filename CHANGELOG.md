# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-24
### Fixed
- `vaultlog-cli.exe` no longer closes instantly when double-clicked. With no arguments it now opens an interactive prompt.

### Added
- AES-256-GCM encryption of every entry, with a password-wrapped data key (scrypt KDF).
- Encrypted SQLite storage; only random ids and ciphertext are written to disk.
- CLI: `init`, `add`, `list`, `search`, `show`, `edit`, `delete`, `export`, `import`, `passwd`, `gui`.
- Tkinter GUI with live search, editing, tags and auto-lock after 10 minutes of inactivity.
- In-memory search with `tag:` filters.
- JSON import/export.
- Windows executables (`VaultLog.exe`, `vaultlog-cli.exe`) built with PyInstaller.

[Unreleased]: https://github.com/aayush-1910/VaultLog/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/aayush-1910/VaultLog/releases/tag/v0.1.0
