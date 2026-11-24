"""Command-line interface for VaultLog."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from . import __version__
from .config import default_vault_path
from .vault import Entry, Vault, VaultError, WrongPasswordError

MIN_PASSWORD_LEN = 8


def _password(prompt: str = "Password: ") -> str:
    # VAULTLOG_PASSWORD allows scripting/tests; interactive use should rely on getpass.
    env = os.environ.get("VAULTLOG_PASSWORD")
    if env is not None:
        return env
    return getpass.getpass(prompt)


def _new_password() -> str:
    env = os.environ.get("VAULTLOG_NEW_PASSWORD") or os.environ.get("VAULTLOG_PASSWORD")
    if env is not None:
        pw = env
    else:
        pw = getpass.getpass("New password: ")
        if pw != getpass.getpass("Confirm password: "):
            raise VaultError("Passwords do not match")
    if len(pw) < MIN_PASSWORD_LEN:
        raise VaultError(f"Password must be at least {MIN_PASSWORD_LEN} characters")
    return pw


def _open(args) -> Vault:
    if not Vault.exists(args.vault):
        raise VaultError(f"No vault at {args.vault}. Run 'vaultlog init' first.")
    return Vault.open(args.vault, _password())


def _read_body(args) -> str:
    if args.message:
        return args.message
    if not sys.stdin.isatty():
        return sys.stdin.read()
    eof = "Ctrl+Z then Enter" if os.name == "nt" else "Ctrl+D"
    print(f"Write your entry. Finish with {eof} on an empty line.", file=sys.stderr)
    return sys.stdin.read()


def _print_row(e: Entry) -> None:
    tags = f"  [{', '.join(e.tags)}]" if e.tags else ""
    print(f"{e.id[:8]}  {e.local_time()}  {e.display_title}{tags}")


def _print_full(e: Entry) -> None:
    print(f"# {e.display_title}")
    print(f"id:      {e.id}")
    print(f"created: {e.local_time()}")
    if e.updated_at != e.created_at:
        print(f"updated: {e.local_time('updated_at')}")
    if e.tags:
        print(f"tags:    {', '.join(e.tags)}")
    print()
    print(e.body.rstrip())


def _tags(value: str | None) -> list[str]:
    return [t for t in (value or "").split(",") if t.strip()]


# ---------------------------------------------------------------- commands
def cmd_init(args) -> int:
    if Vault.exists(args.vault):
        raise VaultError(f"A vault already exists at {args.vault}")
    Vault.create(args.vault, _new_password()).close()
    print(f"Created vault at {args.vault}")
    print("Keep your password safe: it cannot be recovered.")
    return 0


def cmd_add(args) -> int:
    with _open(args) as v:
        body = _read_body(args)
        e = v.add(body, title=args.title or "", tags=_tags(args.tags))
    print(f"Saved entry {e.id[:8]} at {e.local_time()}")
    return 0


def cmd_list(args) -> int:
    with _open(args) as v:
        items = v.entries()
    for e in items[: args.limit] if args.limit else items:
        _print_row(e)
    if not items:
        print("No entries yet.")
    return 0


def cmd_search(args) -> int:
    with _open(args) as v:
        items = v.search(" ".join(args.query))
    for e in items:
        _print_row(e)
    print(f"{len(items)} match(es)", file=sys.stderr)
    return 0 if items else 1


def cmd_show(args) -> int:
    with _open(args) as v:
        _print_full(v.get(args.id))
    return 0


def cmd_edit(args) -> int:
    with _open(args) as v:
        e = v.get(args.id)
        if args.message is not None:
            e.body = args.message
        if args.title is not None:
            e.title = args.title
        if args.tags is not None:
            e.tags = _tags(args.tags)
        v.update(e)
    print(f"Updated entry {e.id[:8]}")
    return 0


def cmd_delete(args) -> int:
    with _open(args) as v:
        e = v.get(args.id)
        if not args.yes:
            ans = input(f"Delete '{e.display_title}'? [y/N] ")
            if ans.strip().lower() not in ("y", "yes"):
                print("Cancelled.")
                return 1
        v.delete(e.id)
    print(f"Deleted entry {e.id[:8]}")
    return 0


def cmd_export(args) -> int:
    with _open(args) as v:
        data = v.export_plain()
    Path(args.file).write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
    print(f"Exported {len(data)} entries to {args.file}")
    print("WARNING: this file is NOT encrypted. Store or delete it carefully.", file=sys.stderr)
    return 0


def cmd_import(args) -> int:
    items = json.loads(Path(args.file).read_text("utf-8"))
    if not isinstance(items, list):
        raise VaultError("Import file must contain a JSON list of entries")
    with _open(args) as v:
        n = v.import_plain(items)
    print(f"Imported {n} new entries ({len(items) - n} skipped as duplicates)")
    return 0


def cmd_passwd(args) -> int:
    if not Vault.exists(args.vault):
        raise VaultError(f"No vault at {args.vault}.")
    old = _password("Current password: ")
    with Vault.open(args.vault, old) as v:
        v.change_password(old, _new_password())
    print("Password changed.")
    return 0


def cmd_gui(args) -> int:
    from .gui import run

    run(args.vault)
    return 0


# ------------------------------------------------------------------ parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vaultlog", description="Offline encrypted journal.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument(
        "--vault",
        type=Path,
        default=default_vault_path(),
        help="path to the vault file (default: $VAULTLOG_PATH or ~/.vaultlog/journal.vault)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create a new vault").set_defaults(func=cmd_init)

    s = sub.add_parser("add", help="write a new entry")
    s.add_argument("-m", "--message", help="entry text (otherwise read from stdin)")
    s.add_argument("-t", "--title")
    s.add_argument("--tags", help="comma-separated tags")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("list", help="list entries, newest first")
    s.add_argument("-n", "--limit", type=int, default=0)
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("search", help="search entries (use tag:name to filter by tag)")
    s.add_argument("query", nargs="+")
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("show", help="show an entry")
    s.add_argument("id", help="entry id or unique prefix")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("edit", help="change an entry")
    s.add_argument("id")
    s.add_argument("-m", "--message")
    s.add_argument("-t", "--title")
    s.add_argument("--tags")
    s.set_defaults(func=cmd_edit)

    s = sub.add_parser("delete", help="delete an entry")
    s.add_argument("id")
    s.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    s.set_defaults(func=cmd_delete)

    s = sub.add_parser("export", help="export entries to a plaintext JSON file")
    s.add_argument("file")
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("import", help="import entries from a JSON file")
    s.add_argument("file")
    s.set_defaults(func=cmd_import)

    sub.add_parser("passwd", help="change the vault password").set_defaults(func=cmd_passwd)
    sub.add_parser("gui", help="open the graphical interface").set_defaults(func=cmd_gui)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except WrongPasswordError:
        print("error: incorrect password", file=sys.stderr)
        return 2
    except (VaultError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
