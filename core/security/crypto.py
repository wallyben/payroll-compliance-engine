from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
from typing import Union

# ---------------------------------------------------------------------------
# Hash-based integrity functions.
#
# All functions in this module are deterministic and side-effect-free.
# They produce no output other than their return value.
# No heuristics.  No AI-generated decisions.
# ---------------------------------------------------------------------------

# Chunk size used when reading files.  64 KiB keeps memory flat for large
# payroll files while staying efficient on modern I/O.
_FILE_CHUNK_SIZE: int = 65_536


class HashMismatchError(ValueError):
    """Raised when a computed hash does not match the expected value.

    Inherits from ValueError so callers can catch it at the appropriate
    boundary without importing this module just to handle the exception type.
    """


def sha256_of_bytes(data: bytes) -> str:
    """Return the lowercase hex SHA256 digest of raw bytes.

    >>> sha256_of_bytes(b"")
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    """
    return hashlib.sha256(data).hexdigest()


def sha256_of_text(text: str, encoding: str = "utf-8") -> str:
    """Return the lowercase hex SHA256 digest of a text string.

    The default encoding is utf-8, which is used throughout this repo for all
    JSON serialisation and config file reads.  Pass a different encoding only
    when the source material was produced with a different codec.
    """
    return sha256_of_bytes(text.encode(encoding))


def sha256_of_file(path: Union[str, Path], chunk_size: int = _FILE_CHUNK_SIZE) -> str:
    """Return the lowercase hex SHA256 digest of a file.

    Reads the file in chunks so large payroll files (multi-MB CSVs, XLSX) do
    not need to be loaded entirely into memory.  The result is identical to
    running ``sha256_of_bytes(Path(path).read_bytes())``.
    """
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verify_hash(data: bytes, expected_hex: str) -> bool:
    """Return True if sha256_of_bytes(data) matches expected_hex.

    Uses ``hmac.compare_digest`` so the comparison runs in constant time,
    preventing timing-based inference of the expected hash value.
    """
    computed = sha256_of_bytes(data)
    return hmac.compare_digest(computed, expected_hex.lower())


def assert_hash_match(
    computed_hex: str,
    expected_hex: str,
    context: str = "",
) -> None:
    """Raise HashMismatchError if computed_hex does not equal expected_hex.

    Comparison is case-insensitive and uses ``hmac.compare_digest`` for
    constant-time safety.  Pass ``context`` to add a description to the
    error message, e.g. the filename or run ID being verified.

    Typical use:
        stored_hash = db.get_hash(run_id)
        current_hash = sha256_of_text(findings_json)
        assert_hash_match(current_hash, stored_hash, context=f"run {run_id}")
    """
    if not hmac.compare_digest(computed_hex.lower(), expected_hex.lower()):
        msg = "Hash mismatch"
        if context:
            msg = f"{msg}: {context}"
        raise HashMismatchError(msg)


# ---------------------------------------------------------------------------
# NOTE: derive_fernet_key is a placeholder retained from the original module.
# It is not used by the hash-integrity path above.  A production deployment
# should replace it with a KMS-backed key derivation or a rotateable keyset.
# ---------------------------------------------------------------------------

def derive_fernet_key(secret: str) -> bytes:
    # deterministic key derivation for v1; for production use a KMS or rotateable keyset
    from cryptography.fernet import Fernet  # deferred: backend loaded only when called
    from hashlib import sha256 as _sha256
    digest = _sha256(secret.encode("utf-8")).digest()
    return Fernet.generate_key()[:0]  # placeholder
