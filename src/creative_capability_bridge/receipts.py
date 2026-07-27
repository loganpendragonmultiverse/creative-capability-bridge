"""Execution receipt creation and comparison."""

from __future__ import annotations

import hashlib
import json
import platform
import time
from pathlib import Path
from typing import Any

from . import __version__
from .schema import Plan, PlanError
from .signing import sign_payload, verify_payload_signature


def file_hash(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_receipt(
    plan: Plan,
    *,
    started: float,
    application_version: str | None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "receipt_version": 1,
        "status": "completed",
        "ccb_version": __version__,
        "adapter": plan.adapter,
        "application_version": application_version,
        "platform": platform.platform(),
        "input": {"path": str(plan.input_path), "sha256": file_hash(plan.input_path)}
        if plan.input_path
        else None,
        "output": {"path": str(plan.output_path), "sha256": file_hash(plan.output_path)},
        "operations": [
            {
                "index": index,
                "capability": op.capability,
                "target": op.target,
                "status": "completed",
            }
            for index, op in enumerate(plan.operations, start=1)
        ],
        "warnings": warnings or [],
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
    }


def write_receipt(path: Path, payload: dict[str, Any]) -> Path:
    target = path.resolve()
    if target.exists():
        raise PlanError(f"Receipt already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def compare_receipts(left_path: Path, right_path: Path) -> dict[str, Any]:
    left = _load(left_path)
    right = _load(right_path)
    fields = ("status", "ccb_version", "adapter", "application_version")
    changed = {
        field: {"left": left.get(field), "right": right.get(field)}
        for field in fields
        if left.get(field) != right.get(field)
    }
    left_hash = (left.get("output") or {}).get("sha256")
    right_hash = (right.get("output") or {}).get("sha256")
    return {
        "left": str(left_path.resolve()),
        "right": str(right_path.resolve()),
        "same_output_hash": bool(left_hash and left_hash == right_hash),
        "output_hashes": {"left": left_hash, "right": right_hash},
        "changed_metadata": changed,
        "operation_counts": {
            "left": len(left.get("operations", [])),
            "right": len(right.get("operations", [])),
        },
        "warnings": {"left": left.get("warnings", []), "right": right.get("warnings", [])},
    }


def sign_receipt(path: Path, destination: Path, private_key: Path) -> Path:
    receipt = _load(path)
    if "signature" in receipt:
        raise PlanError("Receipt is already signed.")
    receipt["signature"] = sign_payload(receipt, private_key)
    return write_receipt(destination, receipt)


def verify_receipt(
    path: Path, *, public_key: Path | None = None, require_signature: bool = False
) -> dict[str, Any]:
    receipt = _load(path)
    signature = receipt.get("signature")
    unsigned = dict(receipt)
    unsigned.pop("signature", None)
    if public_key:
        signature_report = verify_payload_signature(unsigned, signature, public_key)
    else:
        signature_report = {
            "present": signature is not None,
            "verified": None,
            "reason": "no public key supplied" if signature is not None else None,
        }
    checks: dict[str, Any] = {}
    for label in ("input", "output"):
        recorded = receipt.get(label)
        if recorded is None:
            checks[label] = None
            continue
        if not isinstance(recorded, dict) or not isinstance(recorded.get("path"), str):
            raise PlanError(f"Receipt {label} record is invalid.")
        current = file_hash(Path(recorded["path"]))
        checks[label] = {
            "path": recorded["path"],
            "recorded_sha256": recorded.get("sha256"),
            "current_sha256": current,
            "exists": current is not None,
            "matches": current is not None and current == recorded.get("sha256"),
        }
    verified = all(item is None or item["matches"] for item in checks.values())
    if require_signature:
        verified = verified and signature_report.get("verified") is True
    return {
        "receipt": str(path.resolve()),
        "verified": verified,
        "files": checks,
        "signature": signature_report,
    }


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PlanError(f"Could not read receipt: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("receipt_version") != 1:
        raise PlanError(f"Not a supported execution receipt: {path}")
    return payload
