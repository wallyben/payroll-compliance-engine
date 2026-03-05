"""Phase 4 Gate 1: tests for core.reporting.hash_utils."""
import pytest
from core.reporting.hash_utils import compute_sha256_bytes


def test_known_vector_empty():
    """Known test vector: SHA-256 of empty bytes."""
    # Standard: SHA-256("") in hex
    expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert compute_sha256_bytes(b"") == expected


def test_known_vector_hello():
    """Known test vector: SHA-256 of b'hello'."""
    expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert compute_sha256_bytes(b"hello") == expected


def test_deterministic_repeat_calls():
    """Same input must produce same digest on repeated calls."""
    data = b"payroll compliance input"
    first = compute_sha256_bytes(data)
    for _ in range(10):
        assert compute_sha256_bytes(data) == first
