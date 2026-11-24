import json

import pytest

from vaultlog.cli import main

PW = "test password"


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / "cli.vault"
    monkeypatch.setenv("VAULTLOG_PATH", str(path))
    monkeypatch.setenv("VAULTLOG_PASSWORD", PW)
    return path


def run(*args):
    return main(list(args))


def test_full_flow(env, capsys, tmp_path, monkeypatch):
    assert run("--vault", str(env), "init") == 0
    assert run("--vault", str(env), "add", "-m", "Learned about AES today", "--tags", "study") == 0
    assert run("--vault", str(env), "add", "-m", "Grocery list", "-t", "Errands") == 0
    capsys.readouterr()

    assert run("--vault", str(env), "list") == 0
    out = capsys.readouterr().out
    assert "Errands" in out and "Learned about AES" in out

    assert run("--vault", str(env), "search", "aes") == 0
    out = capsys.readouterr().out
    assert "Learned" in out and "Errands" not in out
    assert run("--vault", str(env), "search", "zzz") == 1

    export = tmp_path / "out.json"
    assert run("--vault", str(env), "export", str(export)) == 0
    data = json.loads(export.read_text("utf-8"))
    assert len(data) == 2

    entry_id = data[0]["id"]
    assert run("--vault", str(env), "edit", entry_id[:8], "-m", "changed") == 0
    capsys.readouterr()
    assert run("--vault", str(env), "show", entry_id[:8]) == 0
    assert "changed" in capsys.readouterr().out

    assert run("--vault", str(env), "delete", entry_id, "-y") == 0

    monkeypatch.setenv("VAULTLOG_NEW_PASSWORD", "brand new password")
    assert run("--vault", str(env), "passwd") == 0
    assert run("--vault", str(env), "list") == 2  # old password rejected
    monkeypatch.setenv("VAULTLOG_PASSWORD", "brand new password")
    assert run("--vault", str(env), "list") == 0


def test_interactive_shell(env, capsys, monkeypatch):
    from vaultlog import cli

    lines = iter([
        "add -t Hello --tags shell",  # body typed line by line, ended by "."
        "first line",
        "second line",
        ".",
        "list",
        "search tag:shell",
        "bogus-command",               # bad input must not kill the shell
        "show",                        # missing argument, also survives
        "exit",
    ])
    monkeypatch.setattr("builtins.input", lambda *_: next(lines))
    assert cli.interactive(env) == 0  # creates the vault on first run
    out = capsys.readouterr().out
    assert "Vault created" in out and "Unlocked" in out
    assert out.count("Hello") >= 2 and "Locked. Bye!" in out
    assert cli._session is None

    from vaultlog.vault import Vault
    with Vault.open(env, PW) as v:
        assert v.entries()[0].body == "first line\nsecond line"


def test_errors(env, capsys, monkeypatch):
    assert run("--vault", str(env), "list") == 2
    assert "init" in capsys.readouterr().err
    monkeypatch.setenv("VAULTLOG_PASSWORD", "short")
    assert run("--vault", str(env), "init") == 2
