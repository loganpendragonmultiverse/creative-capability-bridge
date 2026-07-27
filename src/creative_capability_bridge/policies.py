"""Execution policy profiles for capability plans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import ADAPTERS, CAPABILITIES, Plan, PlanError

POLICY_VERSION = 1


def load_policy(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PlanError(f"Could not read policy: {exc}") from exc
    return validate_policy(payload, base_dir=path.resolve().parent)


def validate_policy(payload: Any, *, base_dir: Path | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("policy_version") != POLICY_VERSION:
        raise PlanError("Policy must be a version 1 JSON object.")
    allowed = {
        "policy_version",
        "name",
        "allowed_adapters",
        "allowed_capabilities",
        "output_roots",
        "max_operations",
        "max_input_bytes",
        "require_input",
        "require_receipt",
        "require_inspection",
        "allow_replace",
        "require_signed_bundle",
    }
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise PlanError(f"Unknown policy fields: {', '.join(unknown)}.")
    adapters = payload.get("allowed_adapters", list(ADAPTERS))
    capabilities = payload.get("allowed_capabilities", list(CAPABILITIES))
    if not isinstance(adapters, list) or not set(adapters) <= set(ADAPTERS):
        raise PlanError("Policy allowed_adapters contains an unsupported adapter.")
    if not isinstance(capabilities, list) or not set(capabilities) <= set(CAPABILITIES):
        raise PlanError("Policy allowed_capabilities contains an unsupported capability.")
    roots = payload.get("output_roots", [])
    if not isinstance(roots, list) or not all(isinstance(item, str) for item in roots):
        raise PlanError("Policy output_roots must be a list of paths.")
    root = base_dir or Path.cwd()
    checked = dict(payload)
    checked["allowed_adapters"] = list(dict.fromkeys(adapters))
    checked["allowed_capabilities"] = list(dict.fromkeys(capabilities))
    checked["output_roots"] = [str((root / item).resolve()) for item in roots]
    for key, default in (("max_operations", 100), ("max_input_bytes", 1_000_000_000)):
        value = payload.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise PlanError(f"Policy {key} must be a positive integer.")
        checked[key] = value
    for key in (
        "require_input",
        "require_receipt",
        "require_inspection",
        "allow_replace",
        "require_signed_bundle",
    ):
        value = payload.get(key, False)
        if not isinstance(value, bool):
            raise PlanError(f"Policy {key} must be true or false.")
        checked[key] = value
    checked.setdefault("name", "unnamed-policy")
    return checked


def check_policy(
    plan: Plan,
    policy: dict[str, Any],
    *,
    replace: bool = False,
    receipt: Path | None = None,
    inspected: bool = False,
    signed_bundle: bool = False,
) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    if plan.adapter not in policy["allowed_adapters"]:
        violations.append(_violation("adapter_denied", f"Adapter {plan.adapter} is not allowed."))
    denied = sorted(
        {item.capability for item in plan.operations} - set(policy["allowed_capabilities"])
    )
    if denied:
        violations.append(
            _violation("capability_denied", f"Capabilities are not allowed: {', '.join(denied)}.")
        )
    if len(plan.operations) > policy["max_operations"]:
        violations.append(_violation("operation_limit", "Plan exceeds the operation limit."))
    if policy["require_input"] and plan.input_path is None:
        violations.append(_violation("input_required", "An existing input document is required."))
    if (
        plan.input_path
        and plan.input_path.is_file()
        and plan.input_path.stat().st_size > policy["max_input_bytes"]
    ):
        violations.append(_violation("input_too_large", "Input exceeds the byte limit."))
    if replace and not policy["allow_replace"]:
        violations.append(_violation("replace_denied", "Replacing an output is not allowed."))
    if policy["require_receipt"] and receipt is None:
        violations.append(_violation("receipt_required", "An execution receipt is required."))
    if policy["require_inspection"] and not inspected:
        violations.append(
            _violation("inspection_required", "Pre-execution inspection is required.")
        )
    if policy["require_signed_bundle"] and not signed_bundle:
        violations.append(
            _violation("signed_bundle_required", "A verified signed bundle is required.")
        )
    roots = [Path(item) for item in policy["output_roots"]]
    if roots and not any(_within(plan.output_path, root) for root in roots):
        violations.append(_violation("output_root_denied", "Output is outside permitted roots."))
    return {
        "policy": policy.get("name"),
        "valid": not violations,
        "violations": violations,
    }


def enforce_policy(plan: Plan, policy: dict[str, Any], **context: Any) -> None:
    report = check_policy(plan, policy, **context)
    if not report["valid"]:
        messages = "; ".join(item["message"] for item in report["violations"])
        raise PlanError(f"Policy rejected execution: {messages}")


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _violation(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}
