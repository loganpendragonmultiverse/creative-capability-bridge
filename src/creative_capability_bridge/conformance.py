"""Reusable conformance checks for bundled and third-party adapters."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Protocol

from .adapters import BlenderAdapter, GimpAdapter, InkscapeAdapter
from .capabilities import manifest
from .execution import ExecutableAdapter, execute_transactionally
from .schema import Plan, PlanError, parse_plan


class PreviewAdapter(ExecutableAdapter, Protocol):
    def preview(self, plan: Plan) -> dict[str, Any]: ...


def run_conformance(
    adapter_name: str, *, executable: str | None = None, native: bool = False
) -> dict[str, Any]:
    adapter = _adapter(adapter_name, executable)
    capability_manifest = manifest(adapter_name)
    checks = check_adapter_contract(adapter, capability_manifest)
    native_report: dict[str, Any] | None = None
    if native:
        native_report = _native_fixture(adapter_name, adapter)
        checks.append(
            {
                "name": "native_fixture",
                "passed": native_report["passed"],
                "detail": native_report,
            }
        )
    return {
        "adapter": adapter_name,
        "native_requested": native,
        "passed": all(item["passed"] for item in checks),
        "checks": checks,
        "native": native_report,
    }


def check_adapter_contract(
    adapter: PreviewAdapter, capability_manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    required_manifest = {"protocol_version", "adapter", "application", "operations", "guarantees"}
    checks: list[dict[str, Any]] = [
        {
            "name": "manifest_fields",
            "passed": required_manifest <= capability_manifest.keys(),
            "detail": sorted(required_manifest),
        },
        {
            "name": "protocol_version",
            "passed": capability_manifest.get("protocol_version") == 1,
            "detail": capability_manifest.get("protocol_version"),
        },
        {
            "name": "operations_declared",
            "passed": bool(capability_manifest.get("operations")),
            "detail": sorted(capability_manifest.get("operations", {})),
        },
    ]
    suffix = {"blender": ".blend", "inkscape": ".svg", "gimp": ".xcf"}[
        capability_manifest["adapter"]
    ]
    plan = parse_plan(
        {
            "version": 1,
            "adapter": capability_manifest["adapter"],
            "input": None,
            "output": f"conformance{suffix}",
            "operations": [
                {
                    "id": "create-title",
                    "capability": "text.create",
                    "target": "conformance-title",
                    "parameters": {"content": "CCB conformance"},
                }
            ],
        }
    )
    preview = adapter.preview(plan)
    checks.append(
        {
            "name": "preview_contract",
            "passed": preview.get("adapter") == capability_manifest["adapter"]
            and preview.get("source_preserved") is True
            and preview.get("operation_count") == 1,
            "detail": preview,
        }
    )
    return checks


def _native_fixture(adapter_name: str, adapter: PreviewAdapter) -> dict[str, Any]:
    if not adapter.executable and adapter_name != "inkscape":
        raise PlanError(f"{adapter_name.title()} executable is unavailable for native conformance.")
    suffix = {"blender": ".blend", "inkscape": ".svg", "gimp": ".xcf"}[adapter_name]
    with tempfile.TemporaryDirectory(prefix=f"ccb-{adapter_name}-conformance-") as temp_dir:
        output = Path(temp_dir) / f"fixture{suffix}"
        plan = parse_plan(
            {
                "version": 1,
                "adapter": adapter_name,
                "input": None,
                "output": str(output),
                "operations": [
                    {
                        "id": "create-title",
                        "capability": "text.create",
                        "target": "conformance-title",
                        "parameters": {"content": "CCB conformance", "x": 10, "y": 20},
                    }
                ],
            }
        )
        result = execute_transactionally(plan, adapter)
        targets = {item.get("id") for item in result.inspection["objects"]}
        return {
            "passed": output.is_file() and "conformance-title" in targets,
            "output_created": output.is_file(),
            "target_found": "conformance-title" in targets,
        }


def _adapter(name: str, executable: str | None) -> PreviewAdapter:
    if name == "blender":
        return BlenderAdapter(executable)
    if name == "inkscape":
        return InkscapeAdapter(executable)
    if name == "gimp":
        return GimpAdapter(executable)
    raise PlanError(f"Unknown adapter: {name}")
