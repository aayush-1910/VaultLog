"""VaultLog - an offline, encrypted journal."""

from .vault import Entry, Vault, VaultError, WrongPasswordError

__all__ = ["Entry", "Vault", "VaultError", "WrongPasswordError"]
__version__ = "0.1.0"
