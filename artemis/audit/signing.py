"""Ed25519 signing key for audit checkpoints. The private key stays on the server; verification trusts the server's own
public key, not the one embedded in an exported checkpoint (a forger could embed theirs)."""
from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

DEFAULT_KEY_PATH = "data/signing_key.pem"


def key_path() -> Path:
    return Path(os.environ.get("SIGNING_KEY_PATH") or DEFAULT_KEY_PATH)


def load_or_create_key(path: str | Path | None = None) -> Ed25519PrivateKey:
    p = Path(path) if path else key_path()
    if p.exists():
        return serialization.load_pem_private_key(p.read_bytes(), password=None)
    p.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    p.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()))
    try:
        p.chmod(0o600)
    except OSError:
        pass  # Windows: best effort
    return key


def public_b64(key: Ed25519PrivateKey | Ed25519PublicKey) -> str:
    pub = key.public_key() if isinstance(key, Ed25519PrivateKey) else key
    return base64.b64encode(pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
