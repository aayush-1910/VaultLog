"""Cryptographic primitives for VaultLog.

Design
------
* A random 256-bit **data key** encrypts every entry with AES-256-GCM.
* The data key is itself encrypted ("wrapped") with a **key-encryption key**
  derived from the user's password via scrypt.
* Changing the password only re-wraps the data key; entries stay untouched.
* Each ciphertext is bound to its context (e.g. the entry id) through
  GCM associated data, so rows cannot be silently swapped around.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

KEY_SIZE = 32  # bytes -> AES-256
NONCE_SIZE = 12  # bytes, recommended for GCM
SALT_SIZE = 16

# scrypt cost parameters (OWASP: n=2**17, r=8, p=1 -> ~128 MiB RAM)
DEFAULT_N = 2**17
DEFAULT_R = 8
DEFAULT_P = 1


class DecryptionError(Exception):
    """Raised when data cannot be decrypted (wrong key or tampered data)."""


@dataclass(frozen=True)
class KdfParams:
    salt: bytes
    n: int = DEFAULT_N
    r: int = DEFAULT_R
    p: int = DEFAULT_P

    @classmethod
    def generate(cls) -> "KdfParams":
        return cls(salt=os.urandom(SALT_SIZE), n=DEFAULT_N, r=DEFAULT_R, p=DEFAULT_P)


def derive_key(password: str, params: KdfParams) -> bytes:
    """Derive a key-encryption key from a password."""
    if not password:
        raise ValueError("Password must not be empty")
    kdf = Scrypt(salt=params.salt, length=KEY_SIZE, n=params.n, r=params.r, p=params.p)
    return kdf.derive(password.encode("utf-8"))


def generate_key() -> bytes:
    return AESGCM.generate_key(bit_length=KEY_SIZE * 8)


def encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    """Encrypt and return ``nonce || ciphertext+tag``."""
    nonce = os.urandom(NONCE_SIZE)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad or None)


def decrypt(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    if len(blob) < NONCE_SIZE + 16:
        raise DecryptionError("Ciphertext too short")
    nonce, ct = blob[:NONCE_SIZE], blob[NONCE_SIZE:]
    try:
        return AESGCM(key).decrypt(nonce, ct, aad or None)
    except InvalidTag as exc:
        raise DecryptionError("Wrong password or corrupted data") from exc
