import pytest

from vaultlog import crypto


@pytest.fixture(autouse=True)
def fast_kdf(monkeypatch):
    """Use cheap scrypt parameters so tests run quickly."""
    monkeypatch.setattr(crypto, "DEFAULT_N", 2**10)
