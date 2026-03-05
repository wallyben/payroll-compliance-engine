"""Deterministic SHA-256 hashing for reporting (Phase 4)."""
import hashlib


def compute_sha256_bytes(data: bytes) -> str:
    """Compute lowercase hex SHA-256 digest of raw bytes. Deterministic, no side effects."""
    return hashlib.sha256(data).hexdigest()
