"""Tests for encrypted file support."""

from __future__ import annotations

from pathlib import Path

import pytest

from workato_platform_cli.cli.commands.sdk.encrypted_file import (
    decrypt,
    encrypt,
    generate_key,
    read_encrypted_file,
    write_encrypted_file,
)


def test_generate_key_length() -> None:
    key = generate_key()
    assert len(key) == 32  # 16 bytes as hex
    # Verify it's valid hex
    bytes.fromhex(key)


def test_encrypt_decrypt_roundtrip() -> None:
    key = generate_key()
    plaintext = b"Hello, World!"

    encrypted = encrypt(plaintext, key)
    decrypted = decrypt(encrypted, key)

    assert decrypted == plaintext


def test_encrypt_decrypt_unicode() -> None:
    key = generate_key()
    plaintext = "日本語テスト 🔑".encode()

    encrypted = encrypt(plaintext, key)
    decrypted = decrypt(encrypted, key)

    assert decrypted == plaintext


def test_encrypt_format() -> None:
    key = generate_key()
    encrypted = encrypt(b"test", key)

    # Format: base64--base64--base64
    parts = encrypted.split(b"--")
    assert len(parts) == 3


def test_decrypt_wrong_key() -> None:
    key1 = generate_key()
    key2 = generate_key()

    encrypted = encrypt(b"secret", key1)
    with pytest.raises(Exception):  # noqa: B017
        decrypt(encrypted, key2)


def test_decrypt_invalid_format() -> None:
    key = generate_key()
    with pytest.raises(ValueError, match="Invalid encrypted file format"):
        decrypt(b"not-valid-format", key)


def test_read_write_encrypted_file(tmp_path: Path) -> None:
    key_path = tmp_path / "master.key"
    enc_path = tmp_path / "settings.yaml.enc"

    key = generate_key()
    key_path.write_text(key)

    content = "api_key: secret123\napi_secret: hunter2\n"
    write_encrypted_file(enc_path, key_path, content)

    assert enc_path.exists()
    # Encrypted file should not contain plaintext
    assert b"secret123" not in enc_path.read_bytes()

    # Read back
    decrypted = read_encrypted_file(enc_path, key_path)
    assert decrypted == content


def test_read_encrypted_file_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_encrypted_file(tmp_path / "missing.enc", tmp_path / "master.key")


def test_read_encrypted_file_missing_key(tmp_path: Path) -> None:
    enc_path = tmp_path / "test.enc"
    enc_path.write_bytes(b"data")

    with pytest.raises(FileNotFoundError):
        read_encrypted_file(enc_path, tmp_path / "missing.key")
