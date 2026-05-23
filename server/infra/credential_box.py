from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from typing import Any


_ENVELOPE_MARKER = "__knowlink_encrypted__"
_TEXT_ENVELOPE_PREFIX = "klenc:v1:"
_VERSION = 1


def encrypt_json_secret(payload: dict[str, Any]) -> dict[str, Any]:
    plaintext = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    nonce = secrets.token_bytes(16)
    cipher = _xor_bytes(plaintext, _keystream(nonce, len(plaintext)))
    mac = hmac.new(_key(), b"v1" + nonce + cipher, hashlib.sha256).digest()
    return {
        _ENVELOPE_MARKER: True,
        "v": _VERSION,
        "nonce": _b64(nonce),
        "ciphertext": _b64(cipher),
        "mac": _b64(mac),
    }


def decrypt_json_secret(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get(_ENVELOPE_MARKER) is not True:
        return dict(payload)
    nonce = _unb64(payload["nonce"])
    cipher = _unb64(payload["ciphertext"])
    expected_mac = hmac.new(_key(), b"v1" + nonce + cipher, hashlib.sha256).digest()
    actual_mac = _unb64(payload["mac"])
    if not hmac.compare_digest(expected_mac, actual_mac):
        raise ValueError("encrypted credential payload failed integrity check")
    plaintext = _xor_bytes(cipher, _keystream(nonce, len(cipher)))
    decoded = json.loads(plaintext.decode("utf-8"))
    return dict(decoded) if isinstance(decoded, dict) else {}


def encrypt_text_secret(payload: str | None) -> str | None:
    if payload is None:
        return None
    plaintext = payload.encode("utf-8")
    nonce = secrets.token_bytes(16)
    cipher = _xor_bytes(plaintext, _keystream(nonce, len(plaintext)))
    mac = hmac.new(_key(), b"v1" + nonce + cipher, hashlib.sha256).digest()
    return f"{_TEXT_ENVELOPE_PREFIX}{_b64(nonce)}:{_b64(cipher)}:{_b64(mac)}"


def decrypt_text_secret(payload: str | None) -> str | None:
    if payload is None or not payload.startswith(_TEXT_ENVELOPE_PREFIX):
        return payload
    encoded = payload[len(_TEXT_ENVELOPE_PREFIX) :]
    nonce_text, cipher_text, mac_text = encoded.split(":", 2)
    nonce = _unb64(nonce_text)
    cipher = _unb64(cipher_text)
    expected_mac = hmac.new(_key(), b"v1" + nonce + cipher, hashlib.sha256).digest()
    actual_mac = _unb64(mac_text)
    if not hmac.compare_digest(expected_mac, actual_mac):
        raise ValueError("encrypted credential payload failed integrity check")
    return _xor_bytes(cipher, _keystream(nonce, len(cipher))).decode("utf-8")


def _key() -> bytes:
    raw = (
        os.getenv("KNOWLINK_BILIBILI_CREDENTIAL_SECRET")
        or os.getenv("KNOWLINK_DEMO_TOKEN")
        or "knowlink-demo-token"
    )
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _keystream(nonce: bytes, length: int) -> bytes:
    blocks: list[bytes] = []
    counter = 0
    while sum(len(block) for block in blocks) < length:
        blocks.append(hmac.new(_key(), nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest())
        counter += 1
    return b"".join(blocks)[:length]


def _xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right))


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))
