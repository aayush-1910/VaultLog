"""Encrypted journal storage backed by SQLite.

Only opaque ciphertext is written to disk. The entry id (a random UUID) is the
sole plaintext column per entry; title, body, tags and timestamps all live
inside the encrypted payload. Search happens in memory on decrypted entries.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from . import crypto

SCHEMA_VERSION = 1
WRAP_AAD = b"vaultlog:data-key:v1"


class VaultError(Exception):
    pass


class WrongPasswordError(VaultError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Entry:
    body: str
    title: str = ""
    tags: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=_now)
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.updated_at:
            self.updated_at = self.created_at
        self.tags = sorted({t.strip().lower() for t in self.tags if t.strip()})

    @property
    def display_title(self) -> str:
        if self.title:
            return self.title
        first = self.body.strip().splitlines()[0] if self.body.strip() else ""
        return (first[:60] + "…") if len(first) > 60 else (first or "(untitled)")

    def local_time(self, which: str = "created_at") -> str:
        dt = datetime.fromisoformat(getattr(self, which))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")

    def matches(self, query: str) -> bool:
        """Case-insensitive match: every whitespace-separated term must appear
        in the title, body or tags. ``tag:foo`` restricts a term to tags."""
        haystack = f"{self.title}\n{self.body}".lower()
        for term in query.lower().split():
            if term.startswith("tag:"):
                if term[4:] not in self.tags:
                    return False
            elif term not in haystack and not any(term in t for t in self.tags):
                return False
        return True

    def to_json(self) -> bytes:
        return json.dumps(asdict(self), ensure_ascii=False).encode("utf-8")

    @classmethod
    def from_json(cls, data: bytes) -> "Entry":
        return cls(**json.loads(data.decode("utf-8")))


class Vault:
    """An unlocked vault. Use :meth:`create` or :meth:`open`."""

    def __init__(self, path: Path, conn: sqlite3.Connection, data_key: bytes):
        self.path = path
        self._conn = conn
        self._key = data_key

    # ------------------------------------------------------------------ setup
    @staticmethod
    def exists(path: str | Path) -> bool:
        return Path(path).is_file()

    @classmethod
    def create(cls, path: str | Path, password: str) -> "Vault":
        path = Path(path)
        if path.exists():
            raise VaultError(f"A vault already exists at {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        params = crypto.KdfParams.generate()
        kek = crypto.derive_key(password, params)
        data_key = crypto.generate_key()

        conn = sqlite3.connect(path)
        with conn:
            conn.executescript(
                """
                CREATE TABLE meta (key TEXT PRIMARY KEY, value BLOB NOT NULL);
                CREATE TABLE entries (id TEXT PRIMARY KEY, data BLOB NOT NULL);
                """
            )
            cls._write_key_meta(conn, params, kek, data_key)
            conn.execute(
                "INSERT INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),)
            )
        return cls(path, conn, data_key)

    @classmethod
    def open(cls, path: str | Path, password: str) -> "Vault":
        path = Path(path)
        if not path.is_file():
            raise VaultError(f"No vault found at {path}")
        conn = sqlite3.connect(path)
        try:
            meta = dict(conn.execute("SELECT key, value FROM meta"))
            params = crypto.KdfParams(
                salt=meta["salt"],
                n=int(meta["kdf_n"]),
                r=int(meta["kdf_r"]),
                p=int(meta["kdf_p"]),
            )
            kek = crypto.derive_key(password, params)
            data_key = crypto.decrypt(kek, meta["wrapped_key"], WRAP_AAD)
        except crypto.DecryptionError as exc:
            conn.close()
            raise WrongPasswordError("Incorrect password") from exc
        except (sqlite3.DatabaseError, KeyError) as exc:
            conn.close()
            raise VaultError(f"{path} is not a valid VaultLog file") from exc
        return cls(path, conn, data_key)

    @staticmethod
    def _write_key_meta(conn, params: crypto.KdfParams, kek: bytes, data_key: bytes):
        rows = {
            "salt": params.salt,
            "kdf_n": str(params.n),
            "kdf_r": str(params.r),
            "kdf_p": str(params.p),
            "wrapped_key": crypto.encrypt(kek, data_key, WRAP_AAD),
        }
        conn.executemany("INSERT OR REPLACE INTO meta VALUES (?, ?)", rows.items())

    def change_password(self, old_password: str, new_password: str) -> None:
        # Verify the old password before re-wrapping.
        Vault.open(self.path, old_password).close()
        params = crypto.KdfParams.generate()
        kek = crypto.derive_key(new_password, params)
        with self._conn:
            self._write_key_meta(self._conn, params, kek, self._key)

    def close(self) -> None:
        self._conn.close()
        self._key = b""

    def __enter__(self) -> "Vault":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---------------------------------------------------------------- entries
    def _encrypt_entry(self, entry: Entry) -> bytes:
        return crypto.encrypt(self._key, entry.to_json(), entry.id.encode())

    def _decrypt_entry(self, entry_id: str, blob: bytes) -> Entry:
        return Entry.from_json(crypto.decrypt(self._key, blob, entry_id.encode()))

    def add(self, body: str, title: str = "", tags: Iterable[str] = ()) -> Entry:
        if not body.strip():
            raise ValueError("Entry body must not be empty")
        entry = Entry(body=body, title=title.strip(), tags=list(tags))
        with self._conn:
            self._conn.execute(
                "INSERT INTO entries VALUES (?, ?)", (entry.id, self._encrypt_entry(entry))
            )
        return entry

    def update(self, entry: Entry) -> Entry:
        entry.updated_at = _now()
        entry.__post_init__()
        with self._conn:
            cur = self._conn.execute(
                "UPDATE entries SET data = ? WHERE id = ?",
                (self._encrypt_entry(entry), entry.id),
            )
        if cur.rowcount == 0:
            raise VaultError(f"No entry with id {entry.id}")
        return entry

    def delete(self, entry_id: str) -> None:
        with self._conn:
            cur = self._conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        if cur.rowcount == 0:
            raise VaultError(f"No entry with id {entry_id}")

    def get(self, entry_id: str) -> Entry:
        """Fetch by full id or unique id prefix."""
        rows = self._conn.execute(
            "SELECT id, data FROM entries WHERE id LIKE ? || '%'", (entry_id,)
        ).fetchall()
        if not rows:
            raise VaultError(f"No entry matching id {entry_id!r}")
        if len(rows) > 1:
            raise VaultError(f"Id prefix {entry_id!r} is ambiguous")
        return self._decrypt_entry(*rows[0])

    def entries(self) -> list[Entry]:
        """All entries, newest first, decrypted in memory."""
        rows = self._conn.execute("SELECT id, data FROM entries").fetchall()
        items = [self._decrypt_entry(i, d) for i, d in rows]
        return sorted(items, key=lambda e: e.created_at, reverse=True)

    def search(self, query: str) -> list[Entry]:
        query = query.strip()
        return [e for e in self.entries() if not query or e.matches(query)]

    def __len__(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]

    # ---------------------------------------------------------- import/export
    def export_plain(self) -> list[dict]:
        """Return all entries as plain dicts (caller decides where to put them)."""
        return [asdict(e) for e in self.entries()]

    def import_plain(self, items: Iterable[dict]) -> int:
        """Import entries from dicts; existing ids are skipped. Returns count."""
        count = 0
        with self._conn:
            for item in items:
                entry = Entry(**item)
                cur = self._conn.execute(
                    "INSERT OR IGNORE INTO entries VALUES (?, ?)",
                    (entry.id, self._encrypt_entry(entry)),
                )
                count += cur.rowcount
        return count
