"""Semantic checks that supplement strict plan schema validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .inspection import inspect_document
from .schema import Plan


def lint_plan(
    plan: Plan,
    *,
    document: Path | None = None,
    executable: str | None = None,
) -> dict[str, Any]:
    known: set[str] = set()
    inspected_target_count = 0
    if document is not None:
        inspected = inspect_document(document, executable=executable)
        known = {
            item["id"] for item in inspected["objects"] if item.get("modifiable") and item.get("id")
        }
        inspected_target_count = len(known)

    created: set[str] = set()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for index, operation in enumerate(plan.operations, start=1):
        target = operation.target
        if operation.capability == "text.create":
            if target in created or target in known:
                errors.append(
                    _finding(
                        index, target, "target_already_exists", "text.create target already exists."
                    )
                )
            created.add(target)
            known.add(target)
            continue
        if target in known:
            continue
        finding = _finding(
            index, target, "target_not_established", "Target is not created earlier in this plan."
        )
        if document is None:
            finding["message"] += " Confirm that it exists in the input document."
            warnings.append(finding)
        else:
            errors.append(finding)
    return {
        "plan": plan.as_dict(),
        "document_inspected": str(document.resolve()) if document else None,
        "inspected_target_count": inspected_target_count,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def _finding(index: int, target: str, code: str, message: str) -> dict[str, Any]:
    return {"operation": index, "target": target, "code": code, "message": message}
