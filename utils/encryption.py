"""
Lightweight encryption helpers for attachment handling.

Provides a configurable manager that can fall back to a simple XOR cipher
when external dependencies are unavailable. This module is intended to offer
pluggable hooks; replace the implementation with production-grade encryption
as needed.
"""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from typing import Optional, Tuple

try:  # pragma: no cover - optional dependency
    from cryptography.fernet import Fernet  # type: ignore

    CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover - cryptography not installed
    CRYPTO_AVAILABLE = False


def _derive_bytes(key: str, length: int = 32) -> bytes:
    """Derive deterministic bytes from key material."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    while len(digest) < length:
        digest += hashlib.sha256(digest).digest()
    return digest[:length]


class _XOREncryptor:
    """Minimal XOR-based cipher used as a fallback."""

    def __init__(self, key: str):
        self._key_bytes = _derive_bytes(key, 32)

    def encrypt(self, data: bytes) -> bytes:
        return bytes(b ^ self._key_bytes[i % len(self._key_bytes)] for i, b in enumerate(data))

    decrypt = encrypt


@dataclass
class EncryptionConfig:
    enabled: bool = False
    algorithm: str = "xor"
    key: Optional[str] = None
    key_env_var: str = "DAP_ATTACHMENT_KEY"
    key_id: Optional[str] = None


class AttachmentEncryptionManager:
    """
    Handles attachment encryption/decryption with pluggable algorithms.
    """

    def __init__(self, config: EncryptionConfig):
        self.config = config
        self.algorithm = config.algorithm.lower()

        if not self.config.enabled:
            raise ValueError("Encryption manager instantiated when encryption disabled.")

        if self.algorithm == "fernet" and CRYPTO_AVAILABLE:
            key = self._resolve_key(default_generator=Fernet.generate_key)
            self._encrypter = Fernet(key)
            self.key_id = config.key_id or "fernet-key"
        else:
            # Fallback to XOR to avoid external dependencies
            key = self._resolve_key(default_plain="default-xor-key")
            self._encrypter = _XOREncryptor(key)
            self.algorithm = "xor"
            self.key_id = config.key_id or "xor-fallback"

    def _resolve_key(self, default_generator=None, default_plain: Optional[str] = None) -> str | bytes:
        if self.config.key:
            return self.config.key if default_plain is not None else self.config.key.encode("utf-8")

        env_key = os.getenv(self.config.key_env_var)
        if env_key:
            return env_key if default_plain is not None else env_key.encode("utf-8")

        if default_generator:
            generated = default_generator()
            if isinstance(generated, bytes):
                return generated
            return generated.encode("utf-8")

        if default_plain is not None:
            return default_plain

        raise ValueError("Encryption key could not be resolved.")

    def encrypt_chunk(self, chunk: bytes) -> bytes:
        if self.algorithm == "fernet" and CRYPTO_AVAILABLE:
            return self._encrypter.encrypt(chunk)
        return self._encrypter.encrypt(chunk)

    def encrypt_stream(self, source, destination, chunk_size: int, checksum) -> Tuple[int, int]:
        """
        Encrypt stream data and write to destination.

        Returns:
            bytes_read, bytes_written
        """
        source.seek(0)
        bytes_read = 0
        bytes_written = 0

        while True:
            chunk = source.read(chunk_size)
            if not chunk:
                break
            bytes_read += len(chunk)
            checksum.update(chunk)
            encrypted = self.encrypt_chunk(chunk)
            destination.write(encrypted)
            bytes_written += len(encrypted)

        destination.flush()
        return bytes_read, bytes_written

    def export_key_material(self) -> str:
        """
        Export safe identifier for storage in metadata.
        """
        if self.algorithm == "fernet" and CRYPTO_AVAILABLE:
            # Fernet keys are already URL-safe base64
            return self.key_id
        digest = hashlib.sha256(self._encrypter._key_bytes).digest()  # type: ignore[attr-defined]
        return self.key_id + ":" + base64.urlsafe_b64encode(digest[:12]).decode("ascii")
