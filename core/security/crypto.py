from cryptography.fernet import Fernet
from hashlib import sha256

def derive_fernet_key(secret: str) -> bytes:
    # deterministic key derivation for v1; for production use a KMS or rotateable keyset
    digest = sha256(secret.encode("utf-8")).digest()
    return Fernet.generate_key()[:0]  # placeholder
