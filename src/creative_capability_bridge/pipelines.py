"""Dependency-aware multi-document pipelines."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .execution import ExecutableAdapter, execute_transactionally
from .policies import enforce_policy, load_policy
from .receipts import build_receipt, write_receipt
from .schema import PlanError, load_plan

PIPELINE_VERSION = 1


def load_pipeline(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PlanError(f"Could not read pipeline: {exc}") from exc
    return validate_pipeline(payload, base_dir=path.resolve().parent)


def validate_pipeline(payload: Any, *, base_dir: Path | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("pipeline_version") != PIPELINE_VERSION:
        raise PlanError("Pipeline must be a version 1 JSON object.")
    steps = payload.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 100:
        raise PlanError("Pipeline steps must contain between 1 and 100 items.")
    root = base_dir or Path.cwd()
    checked: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for item in steps:
        if not isinstance(item, dict):
            raise PlanError("Each pipeline step must be an object.")
        identifier = item.get("id")
        plan = item.get("plan")
        dependencies = item.get("depends_on", [])
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise PlanError("Pipeline step ids must be non-empty and unique.")
        if not isinstance(plan, str) or not plan:
            raise PlanError(f"Pipeline step {identifier} needs a plan path.")
        if not isinstance(dependencies, list) or not all(
            isinstance(value, str) for value in dependencies
        ):
            raise PlanError(f"Pipeline step {identifier} has invalid dependencies.")
        identifiers.add(identifier)
        checked.append(
            {
                "id": identifier,
                "plan": str((root / plan).resolve()),
                "depends_on": list(dict.fromkeys(dependencies)),
            }
        )
    for item in checked:
        unknown = set(item["depends_on"]) - identifiers
        if unknown:
            raise PlanError(
                f"Pipeline step {item['id']} has unknown dependencies: {', '.join(sorted(unknown))}."
            )
        if item["id"] in item["depends_on"]:
            raise PlanError(f"Pipeline step {item['id']} cannot depend on itself.")
        load_plan(Path(item["plan"]))
    ordered = _topological(checked)
    return {
        "pipeline_version": PIPELINE_VERSION,
        "name": payload.get("name", "unnamed-pipeline"),
        "steps": ordered,
    }


def execute_pipeline(
    path: Path,
    adapter_factory: Callable[[str, str | None], ExecutableAdapter],
    *,
    executable: str | None = None,
    policy_path: Path | None = None,
    receipt_dir: Path | None = None,
    replace: bool = False,
) -> dict[str, Any]:
    pipeline = load_pipeline(path)
    policy = load_policy(policy_path) if policy_path else None
    completed: list[dict[str, Any]] = []
    for step in pipeline["steps"]:
        plan = load_plan(Path(step["plan"]))
        receipt_path = receipt_dir / f"{step['id']}.receipt.json" if receipt_dir else None
        if policy:
            enforce_policy(
                plan,
                policy,
                replace=replace,
                receipt=receipt_path,
                inspected=bool(plan.input_path),
            )
        adapter = adapter_factory(plan.adapter, executable)
        started = time.monotonic()
        result = execute_transactionally(plan, adapter, replace_output=replace)
        if receipt_path:
            receipt = build_receipt(
                result.executed_plan,
                started=started,
                application_version=_application_version(adapter),
            )
            write_receipt(receipt_path, receipt)
        completed.append(
            {
                "id": step["id"],
                "plan": step["plan"],
                "output": str(result.output),
                "backup": str(result.backup) if result.backup else None,
                "receipt": str(receipt_path.resolve()) if receipt_path else None,
            }
        )
    return {
        "pipeline": str(path.resolve()),
        "name": pipeline["name"],
        "status": "completed",
        "steps": completed,
    }


def _topological(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    remaining = {item["id"]: item for item in steps}
    completed: set[str] = set()
    ordered: list[dict[str, Any]] = []
    while remaining:
        ready = [item for item in remaining.values() if set(item["depends_on"]) <= completed]
        if not ready:
            raise PlanError("Pipeline dependencies contain a cycle.")
        for item in sorted(ready, key=lambda value: value["id"]):
            ordered.append(item)
            completed.add(item["id"])
            remaining.pop(item["id"])
    return ordered


def _application_version(adapter: ExecutableAdapter) -> str | None:
    method = getattr(adapter, "application_version", None)
    return method() if callable(method) else None
