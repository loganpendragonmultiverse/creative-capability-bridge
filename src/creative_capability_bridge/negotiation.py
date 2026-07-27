"""Capability compatibility reports and safe plan retargeting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .capabilities import manifest
from .schema import ADAPTERS, PlanError, parse_plan


def load_intent(path: Path) -> tuple[dict[str, Any], Path]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PlanError(f"Could not read plan: {exc}") from exc
    if not isinstance(payload, dict):
        raise PlanError("Plan root must be a JSON object.")
    adapter = payload.get("adapter")
    if adapter not in (*ADAPTERS, "auto"):
        raise PlanError("Adapter must be blender, inkscape, gimp, or auto.")
    return payload, path.resolve().parent


def compatibility(path: Path) -> dict[str, Any]:
    payload, base = load_intent(path)
    reports = [_for_adapter(payload, base, adapter) for adapter in ADAPTERS]
    return {
        "plan": str(path.resolve()),
        "requested_adapter": payload["adapter"],
        "adapters": reports,
    }


def retarget(path: Path, adapter: str, destination: Path) -> Path:
    if adapter not in ADAPTERS:
        raise PlanError(f"Adapter must be one of: {', '.join(ADAPTERS)}.")
    payload, base = load_intent(path)
    report = _for_adapter(payload, base, adapter)
    if report["status"] == "unsupported":
        raise PlanError(f"Plan cannot target {adapter}: {'; '.join(report['reasons'])}")
    converted = dict(payload)
    converted["adapter"] = adapter
    output = converted.get("output")
    if not isinstance(output, str) or not output.strip():
        output = "output"
    suffix = {"blender": ".blend", "inkscape": ".svg", "gimp": ".xcf"}[adapter]
    converted["output"] = str(Path(output).with_suffix(suffix))
    parse_plan(converted, base_dir=base)
    target = destination.resolve()
    if target.exists():
        raise PlanError(f"Retargeted plan already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(converted, indent=2) + "\n", encoding="utf-8")
    return target


def _for_adapter(payload: dict[str, Any], base: Path, adapter: str) -> dict[str, Any]:
    candidate = dict(payload)
    candidate["adapter"] = adapter
    output = candidate.get("output")
    if not isinstance(output, str) or not output.strip():
        output = "output"
    suffix = {"blender": ".blend", "inkscape": ".svg", "gimp": ".xcf"}[adapter]
    candidate["output"] = str(Path(output).with_suffix(suffix))
    approximations: list[str] = []
    if adapter == "blender":
        for operation in candidate.get("operations", []):
            params = operation.get("parameters", {}) if isinstance(operation, dict) else {}
            if "font_family" in params:
                approximations.append(
                    "font_family is recorded as a request; native resolution is application-dependent"
                )
    try:
        parse_plan(candidate, base_dir=base)
        status = "approximate" if approximations else "exact"
        reasons: list[str] = []
    except PlanError as exc:
        status = "unsupported"
        reasons = [str(exc)]
    return {
        "adapter": adapter,
        "application": manifest(adapter)["application"],
        "status": status,
        "approximations": sorted(set(approximations)),
        "reasons": reasons,
    }
