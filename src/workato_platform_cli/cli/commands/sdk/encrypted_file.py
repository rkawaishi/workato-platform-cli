"""Encrypted file support using aes-128-gcm.

Uses aes-128-gcm cipher with hex-encoded 16-byte keys for encrypting
connector settings files (e.g., settings.yaml.enc).

Note: This implementation encrypts/decrypts raw text without Ruby Marshal
serialization. Files created by this module are readable only by this module,
not by the Ruby workato-connector-sdk gem (which uses ActiveSupport's
MessageEncryptor with Marshal serialization).

Format: base64(ciphertext)--base64(iv)--base64(auth_tag)
"""

from __future__ import annotations

import base64
import os
import secrets

from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def generate_key() -> str:
    """Generate a new encryption key (16 bytes as hex = 32 hex chars).

    Compatible with ActiveSupport::MessageEncryptor.key_len for aes-128-gcm.
    """
    return secrets.token_hex(16)


def encrypt(plaintext: bytes, key_hex: str) -> bytes:
    """Encrypt data using aes-128-gcm.

    Returns format: base64(ciphertext+tag)--base64(iv)
    """
    key = bytes.fromhex(key_hex)
    iv = os.urandom(12)  # 96-bit IV for GCM

    aesgcm = AESGCM(key)
    # AESGCM.encrypt returns ciphertext + tag concatenated
    ct_and_tag = aesgcm.encrypt(iv, plaintext, None)

    # Split into ciphertext and auth_tag (last 16 bytes)
    ciphertext = ct_and_tag[:-16]
    auth_tag = ct_and_tag[-16:]

    encoded = (
        base64.b64encode(ciphertext)
        + b"--"
        + base64.b64encode(iv)
        + b"--"
        + base64.b64encode(auth_tag)
    )
    return encoded


def decrypt(encrypted_data: bytes, key_hex: str) -> bytes:
    """Decrypt data encrypted with aes-128-gcm.

    Expects format: base64(ciphertext)--base64(iv)--base64(auth_tag)
    """
    parts = encrypted_data.split(b"--")
    if len(parts) != 3:
        raise ValueError(
            "Invalid encrypted file format. "
            "Expected: base64(ciphertext)--base64(iv)--base64(auth_tag)"
        )

    ciphertext = base64.b64decode(parts[0])
    iv = base64.b64decode(parts[1])
    auth_tag = base64.b64decode(parts[2])

    key = bytes.fromhex(key_hex)
    aesgcm = AESGCM(key)

    # AESGCM.decrypt expects ciphertext + tag concatenated
    result: bytes = aesgcm.decrypt(iv, ciphertext + auth_tag, None)
    return result


def read_encrypted_file(file_path: Path, key_path: Path) -> str:
    """Read and decrypt an encrypted file.

    Args:
        file_path: Path to the .enc file
        key_path: Path to the master.key file

    Returns:
        Decrypted content as string
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Encrypted file not found: {file_path}")
    if not key_path.exists():
        raise FileNotFoundError(f"Key file not found: {key_path}")

    key_hex = key_path.read_text().strip()
    encrypted_data = file_path.read_bytes()
    return decrypt(encrypted_data, key_hex).decode("utf-8")


def write_encrypted_file(file_path: Path, key_path: Path, content: str) -> None:
    """Encrypt and write content to a file.

    Args:
        file_path: Path to the .enc file
        key_path: Path to the master.key file
        content: Plaintext content to encrypt
    """
    if not key_path.exists():
        raise FileNotFoundError(f"Key file not found: {key_path}")

    key_hex = key_path.read_text().strip()
    encrypted_data = encrypt(content.encode("utf-8"), key_hex)
    file_path.write_bytes(encrypted_data)
