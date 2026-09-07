"""Explicit portable family mappings and local availability diagnostics."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from .schema import Plan, PlanError


def map_fonts(
    plan: Plan, mapping_path: Path, inventory: Path | None = None
) -> tuple[Plan, dict[str, Any]]:
    try:
        config = json.loads(mapping_path.read_text(encoding="utf-8"))
        if (
            not isinstance(config, dict)
            or config.get("version") != 1
            or not isinstance(config.get("families"), dict)
        ):
            raise PlanError("Expected font-map version 1 with families.")
        available = json.loads(inventory.read_text(encoding="utf-8")) if inventory else None
        if available is not None and (
            not isinstance(available, list) or not all(isinstance(v, str) for v in available)
        ):
            raise PlanError("Font inventory must be an array of family names.")
    except (OSError, ValueError) as error:
        raise PlanError(f"Could not read font configuration: {error}") from error
    operations = []
    findings = []
    for operation in plan.operations:
        params = dict(operation.parameters)
        requested = params.get("font_family")
        if requested:
            family = config["families"].get(requested, {})
            target = family.get(plan.adapter) if isinstance(family, dict) else None
            if (
                not isinstance(target, dict)
                or not isinstance(target.get("family"), str)
                or not target["family"].strip()
            ):
                findings.append(
                    {"target": operation.target, "requested": requested, "status": "unmapped"}
                )
                operations.append(operation)
                continue
            params["font_family"] = target["family"]
            status = "inventory-unverified"
            if plan.adapter == "blender":
                filename = target.get("file")
                if not isinstance(filename, str):
                    status = "missing-font-file"
                else:
                    file = (mapping_path.resolve().parent / filename).resolve()
                    if (
                        not file.is_file()
                        or file.suffix.lower() not in {".ttf", ".otf"}
                        or file.stat().st_size > 20 * 1024 * 1024
                    ):
                        status = "missing-or-invalid-font-file"
                    else:
                        params["font_file"] = str(file)
                        status = "file-present"
            elif available is not None:
                status = "family-present" if target["family"] in available else "family-missing"
            findings.append(
                {
                    "target": operation.target,
                    "requested": requested,
                    "resolved": target["family"],
                    "status": status,
                }
            )
        operations.append(replace(operation, parameters=params))
    blocked = any(
        item["status"]
        in {"unmapped", "missing-font-file", "missing-or-invalid-font-file", "family-missing"}
        for item in findings
    )
    return replace(plan, operations=tuple(operations)), {
        "version": 1,
        "adapter": plan.adapter,
        "blocked": blocked,
        "fonts": findings,
        "boundary": "Inventory is operator-supplied. File presence and family matches do not prove native rendering or font embedding rights.",
    }
