"""Password hashing helpers for the development login flow."""

from argon2.exceptions import VerificationError
from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError


password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Return an Argon2id hash; never persist the supplied plaintext password."""
    return password_hasher.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    """Check a password safely, treating malformed/unsupported hashes as failure."""
    try:
        return password_hasher.verify(password, encoded_hash)
    except (PwdlibError, VerificationError, ValueError):
        return False
