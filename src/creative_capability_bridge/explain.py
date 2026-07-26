"""Clear execution-boundary reports."""

from __future__ import annotations

from typing import Any

from .capabilities import manifest
from .schema import Plan


def explain_plan(plan: Plan, *, replace: bool = False) -> dict[str, Any]:
    adapter = manifest(plan.adapter)
    created = [op.target for op in plan.operations if op.capability == "text.create"]
    modified = [op.target for op in plan.operations if op.capability != "text.create"]
    approximations: list[str] = []
    if plan.adapter == "blender" and any("font_family" in op.parameters for op in plan.operations):
        approximations.append(
            "Blender records font_family requests but does not resolve fonts portably."
        )
    return {
        "adapter": plan.adapter,
        "application": adapter["application"],
        "protocol_version": plan.version,
        "reads": [str(plan.input_path)] if plan.input_path else [],
        "creates": [str(plan.output_path)],
        "replaces_existing_output": replace and plan.output_path.exists(),
        "source_preserved": True,
        "targets_created": created,
        "targets_modified": modified,
        "operation_count": len(plan.operations),
        "approximations": approximations,
        "unsupported": [],
        "requirements": {
            "native_application": plan.adapter == "blender",
            "application": adapter["application"],
            "tested_versions": adapter.get("tested_versions", []),
        },
    }
