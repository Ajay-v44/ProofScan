import base64
import hashlib
from dataclasses import dataclass

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def decode(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


@dataclass(frozen=True)
class Signature:
    digest: str
    value: str
    key_id: str


class Signer:
    def __init__(self, private_key: str, key_id: str, trusted_keys: dict[str, str]):
        try:
            self.private_key = Ed25519PrivateKey.from_private_bytes(decode(private_key))
            self.public_keys = {
                name: Ed25519PublicKey.from_public_bytes(decode(key))
                for name, key in trusted_keys.items()
            }
        except ValueError as exc:
            raise ValueError("Report keys must be base64url-encoded 32-byte Ed25519 keys") from exc
        if key_id in self.public_keys:
            if (
                self.public_keys[key_id].public_bytes_raw()
                != self.private_key.public_key().public_bytes_raw()
            ):
                raise ValueError("REPORT_KEY_ID is already assigned to a different public key")
        self.key_id = key_id
        self.public_keys[key_id] = self.private_key.public_key()

    def sign(self, report: dict) -> Signature:
        digest = hashlib.sha256(rfc8785.dumps(report)).digest()
        return Signature(digest.hex(), encode(self.private_key.sign(digest)), self.key_id)

    def verify(self, report: dict, signature: Signature) -> bool:
        try:
            digest = hashlib.sha256(rfc8785.dumps(report)).digest()
            if digest.hex() != signature.digest:
                return False
            self.public_keys[signature.key_id].verify(decode(signature.value), digest)
        except (InvalidSignature, KeyError, ValueError):
            return False
        return True
