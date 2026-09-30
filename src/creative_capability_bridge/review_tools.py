"""Read-only readiness checks and value-free semantic plan comparisons."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .linting import lint_plan
from .policies import check_policy, load_policy
from .schema import Plan, PlanError


def preflight(
    plan: Plan,
    *,
    policy_path: Path | None = None,
    replace: bool = False,
    receipt: Path | None = None,
    inspect: bool = False,
    executable: str | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    files: list[dict[str, Any]] = []

    def error(code: str, message: str) -> None:
        errors.append({"code": code, "message": message})

    if plan.input_path:
        if not plan.input_path.is_file():
            error("missing_input", "Input document is missing or is not a regular file.")
        else:
            try:
                size = plan.input_path.stat().st_size
                digest = hashlib.sha256(plan.input_path.read_bytes()).hexdigest()
            except OSError as exc:
                raise PlanError("Could not read the input for preflight.") from exc
            files.append(
                {
                    "role": "input",
                    "bytes": size,
                    "sha256": digest,
                }
            )
    if plan.output_path.exists():
        if not plan.output_path.is_file():
            error("invalid_output", "Output is not a regular file.")
        elif not replace:
            error(
                "output_exists",
                "Output already exists; execution would require explicit replacement.",
            )
        else:
            warnings.append(
                {
                    "code": "replacement",
                    "message": "Replacement requires the transactional rollback backup.",
                }
            )
    if not plan.output_path.parent.is_dir():
        error("missing_output_parent", "Output parent directory does not exist.")
    if receipt and receipt.exists():
        error("receipt_exists", "Receipt destination already exists.")
    if receipt and (
        receipt.resolve() == plan.output_path.resolve()
        or (plan.input_path and receipt.resolve() == plan.input_path.resolve())
    ):
        error("receipt_collision", "Receipt must not alias an input or output document.")
    for operation in plan.operations:
        font = operation.parameters.get("font_file")
        if font and (not Path(font).is_file() or Path(font).suffix.lower() not in {".ttf", ".otf"}):
            error("font_unavailable", "A referenced local TTF/OTF font file is unavailable.")
    inspected = bool(inspect and plan.input_path and plan.input_path.is_file())
    lint = lint_plan(plan, document=plan.input_path if inspected else None, executable=executable)
    for finding in lint["errors"]:
        errors.append({"code": finding["code"], "message": finding["message"]})
    for finding in lint["warnings"]:
        warnings.append({"code": finding["code"], "message": finding["message"]})
    if plan.input_path and not inspected:
        warnings.append(
            {
                "code": "input_not_inspected",
                "message": "Existing document targets have not been verified; use --inspect for native/document inspection.",
            }
        )
    policy = None
    if policy_path:
        policy = check_policy(
            plan,
            load_policy(policy_path),
            replace=replace,
            receipt=receipt,
            inspected=inspected,
            signed_bundle=False,
        )
        errors.extend(policy["violations"])
    return {
        "report_version": 1,
        "adapter": plan.adapter,
        "ready": not errors,
        "executed": False,
        "operation_count": len(plan.operations),
        "input_evidence": files,
        "inspection_performed": inspected,
        "errors": errors,
        "warnings": warnings,
        "policy": policy,
        "limitations": [
            "A read-only report does not reserve paths, authorize execution, or prove native rendering. Recheck at execution time.",
            "Signed-bundle requirements stay blocked here; verify and supply the bundle to the execution command.",
        ],
    }


def compare_plans(before: Plan, after: Plan) -> dict[str, Any]:
    def operation_map(plan: Plan) -> dict[str, Any]:
        return {
            operation.identifier or f"position:{index + 1}": operation
            for index, operation in enumerate(plan.operations)
        }

    left, right = operation_map(before), operation_map(after)
    common = left.keys() & right.keys()
    changed = []
    for key in sorted(common):
        a, b = left[key], right[key]
        fields = []
        for name in ["capability", "target", "tags"]:
            if getattr(a, name) != getattr(b, name):
                fields.append(name)
        fields.extend(
            "parameters." + name
            for name in sorted(a.parameters.keys() | b.parameters.keys())
            if a.parameters.get(name) != b.parameters.get(name)
            or (name in a.parameters) != (name in b.parameters)
        )
        if fields:
            changed.append({"operation": key, "fields": fields})
    metadata = []
    for name in ["adapter", "input_path", "output_path", "coordinate_space"]:
        if getattr(before, name) != getattr(after, name):
            metadata.append(name)
    before_order = list(left)
    after_order = list(right)
    reordered = [key for key in before_order if key in common] != [
        key for key in after_order if key in common
    ]

    def fingerprint(plan: Plan) -> str:
        return hashlib.sha256(
            json.dumps(plan.as_dict(), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    return {
        "report_version": 1,
        "equivalent": not (metadata or changed or left.keys() != right.keys() or reordered),
        "metadata_changed": metadata,
        "added": sorted(right.keys() - left.keys()),
        "removed": sorted(left.keys() - right.keys()),
        "changed": changed,
        "reordered": reordered,
        "before_sha256": fingerprint(before),
        "after_sha256": fingerprint(after),
        "matching": "Explicit operation IDs; operations without IDs match by position. Raw content and file paths are omitted.",
    }
