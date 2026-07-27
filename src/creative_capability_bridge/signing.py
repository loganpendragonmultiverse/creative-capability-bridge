"""Optional Ed25519 signatures for portable CCB artifacts."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .schema import PlanError

SIGNATURE_VERSION = 1


def generate_keypair(private_path: Path, public_path: Path) -> tuple[Path, Path]:
    private_target = private_path.resolve()
    public_target = public_path.resolve()
    if private_target.exists() or public_target.exists():
        raise PlanError("Signing key destination already exists.")
    key = Ed25519PrivateKey.generate()
    private_target.parent.mkdir(parents=True, exist_ok=True)
    public_target.parent.mkdir(parents=True, exist_ok=True)
    private_target.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_target.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return private_target, public_target


def sign_payload(payload: dict[str, Any], private_path: Path) -> dict[str, Any]:
    key = _private_key(private_path)
    public_bytes = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    signature = key.sign(canonical_bytes(payload))
    return {
        "signature_version": SIGNATURE_VERSION,
        "algorithm": "Ed25519",
        "public_key_sha256": hashlib.sha256(public_bytes).hexdigest(),
        "value": base64.b64encode(signature).decode("ascii"),
    }


def verify_payload_signature(
    payload: dict[str, Any], signature: Any, public_path: Path
) -> dict[str, Any]:
    if not isinstance(signature, dict) or signature.get("signature_version") != SIGNATURE_VERSION:
        return {"present": bool(signature), "verified": False, "reason": "invalid signature record"}
    if signature.get("algorithm") != "Ed25519" or not isinstance(signature.get("value"), str):
        return {"present": True, "verified": False, "reason": "unsupported signature"}
    key = _public_key(public_path)
    raw_public = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    fingerprint = hashlib.sha256(raw_public).hexdigest()
    if fingerprint != signature.get("public_key_sha256"):
        return {"present": True, "verified": False, "reason": "public key fingerprint mismatch"}
    try:
        key.verify(base64.b64decode(signature["value"], validate=True), canonical_bytes(payload))
    except (InvalidSignature, ValueError):
        return {"present": True, "verified": False, "reason": "signature mismatch"}
    return {"present": True, "verified": True, "public_key_sha256": fingerprint}


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _private_key(path: Path) -> Ed25519PrivateKey:
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise PlanError(f"Could not read Ed25519 private key: {exc}") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise PlanError("Signing key is not an Ed25519 private key.")
    return key


def _public_key(path: Path) -> Ed25519PublicKey:
    try:
        key = serialization.load_pem_public_key(path.read_bytes())
    except (OSError, ValueError, TypeError) as exc:
        raise PlanError(f"Could not read Ed25519 public key: {exc}") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise PlanError("Verification key is not an Ed25519 public key.")
    return key
