import sqlite3

import pytest

from vaultlog import crypto
from vaultlog.vault import Entry, Vault, VaultError, WrongPasswordError

PW = "correct horse battery"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "test.vault"


@pytest.fixture
def vault(path):
    v = Vault.create(path, PW)
    yield v
    v.close()


def test_crypto_roundtrip_and_tamper():
    key = crypto.generate_key()
    blob = crypto.encrypt(key, b"hello", b"ctx")
    assert crypto.decrypt(key, blob, b"ctx") == b"hello"
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(key, blob, b"other")
    tampered = blob[:-1] + bytes([blob[-1] ^ 1])
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(key, tampered, b"ctx")


def test_add_and_reopen(vault, path):
    e = vault.add("Dear diary, secret plans", title="Day 1", tags=["Work", " life "])
    assert e.tags == ["life", "work"]
    assert e.created_at
    vault.close()
    with Vault.open(path, PW) as v:
        [got] = v.entries()
        assert got.body == "Dear diary, secret plans"
        assert got.title == "Day 1"
        assert got.created_at == e.created_at


def test_nothing_plaintext_on_disk(vault, path):
    vault.add("supersecretword", title="hiddentitle", tags=["hiddentag"])
    vault.close()
    raw = path.read_bytes()
    for needle in (b"supersecretword", b"hiddentitle", b"hiddentag"):
        assert needle not in raw


def test_wrong_password(vault, path):
    vault.close()
    with pytest.raises(WrongPasswordError):
        Vault.open(path, "nope")


def test_create_refuses_existing(vault, path):
    with pytest.raises(VaultError):
        Vault.create(path, PW)


def test_open_non_vault(tmp_path):
    p = tmp_path / "junk.vault"
    p.write_bytes(b"not a database at all" * 100)
    with pytest.raises(VaultError):
        Vault.open(p, PW)


def test_search(vault):
    vault.add("Went hiking in the mountains", tags=["travel"])
    vault.add("Meeting about the budget", tags=["work"])
    vault.add("Budget hiking gear list", tags=["travel", "shopping"])
    assert len(vault.search("")) == 3
    assert len(vault.search("BUDGET")) == 2
    assert len(vault.search("budget hiking")) == 1
    assert len(vault.search("tag:travel")) == 2
    assert len(vault.search("tag:travel budget")) == 1
    assert vault.search("nothing-here") == []


def test_update_delete_and_prefix(vault):
    e = vault.add("first draft")
    got = vault.get(e.id[:6])
    got.body = "second draft"
    vault.update(got)
    again = vault.get(e.id)
    assert again.body == "second draft"
    assert again.updated_at >= again.created_at
    vault.delete(e.id)
    assert len(vault) == 0
    with pytest.raises(VaultError):
        vault.get(e.id)


def test_rows_cannot_be_swapped(vault, path):
    a = vault.add("entry A")
    b = vault.add("entry B")
    vault.close()
    con = sqlite3.connect(path)
    data = dict(con.execute("SELECT id, data FROM entries"))
    with con:
        con.execute("UPDATE entries SET data=? WHERE id=?", (data[b.id], a.id))
    con.close()
    with Vault.open(path, PW) as v, pytest.raises(crypto.DecryptionError):
        v.get(a.id)


def test_change_password(vault, path):
    vault.add("keep me")
    vault.change_password(PW, "new password!")
    vault.close()
    with pytest.raises(WrongPasswordError):
        Vault.open(path, PW)
    with Vault.open(path, "new password!") as v:
        assert v.entries()[0].body == "keep me"


def test_change_password_requires_old(vault):
    with pytest.raises(WrongPasswordError):
        vault.change_password("wrong", "whatever123")


def test_export_import(vault, tmp_path):
    vault.add("one")
    vault.add("two", tags=["x"])
    data = vault.export_plain()
    other = Vault.create(tmp_path / "other.vault", "another pw")
    assert other.import_plain(data) == 2
    assert other.import_plain(data) == 0  # duplicates skipped
    assert sorted(e.body for e in other.entries()) == ["one", "two"]
    other.close()


def test_empty_body_rejected(vault):
    with pytest.raises(ValueError):
        vault.add("   ")


def test_display_title():
    assert Entry(body="hello\nworld").display_title == "hello"
    assert Entry(body="x", title="T").display_title == "T"
