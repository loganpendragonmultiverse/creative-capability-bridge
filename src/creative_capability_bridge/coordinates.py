"""Coordinate and unit normalization across creative applications."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .schema import Operation, Plan, PlanError

_NATIVE_SPACES: dict[str, dict[str, Any]] = {
    "blender": {"unit": "blender-unit", "origin": "center", "y_axis": "up", "dpi": 96.0},
    "inkscape": {"unit": "px", "origin": "top-left", "y_axis": "down", "dpi": 96.0},
    "gimp": {"unit": "px", "origin": "top-left", "y_axis": "down", "dpi": 96.0},
}


def normalize_plan(plan: Plan) -> Plan:
    """Return a plan expressed in the selected adapter's native coordinate space."""
    source = plan.coordinate_space
    if source is None:
        return plan
    target = dict(_NATIVE_SPACES[plan.adapter])
    width = source.get("width")
    height = source.get("height")
    needs_extent = (source["origin"], source["y_axis"]) != (
        target["origin"],
        target["y_axis"],
    )
    if needs_extent and (width is None or height is None):
        raise PlanError(
            "coordinate_space width and height are required when converting origins or y axes."
        )
    if width is not None:
        target["width"] = _convert_length(float(width), source, target)
    if height is not None:
        target["height"] = _convert_length(float(height), source, target)

    operations = tuple(_normalize_operation(item, source, target) for item in plan.operations)
    return replace(plan, operations=operations, coordinate_space=target)


def coordinate_report(plan: Plan) -> dict[str, Any]:
    normalized = normalize_plan(plan)
    return {
        "adapter": plan.adapter,
        "source": plan.coordinate_space,
        "target": normalized.coordinate_space,
        "changed": normalized.as_dict() != plan.as_dict(),
        "operations": normalized.as_dict()["operations"],
    }


def _normalize_operation(
    operation: Operation, source: dict[str, Any], target: dict[str, Any]
) -> Operation:
    params = dict(operation.parameters)
    if "x" in params or "y" in params:
        x, y = _convert_point(
            float(params.get("x", 0.0)), float(params.get("y", 0.0)), source, target
        )
        if "x" in params:
            params["x"] = x
        if "y" in params:
            params["y"] = y
    if "font_size" in params:
        params["font_size"] = _convert_length(float(params["font_size"]), source, target)
    if "rotation_degrees" in params and source["y_axis"] != target["y_axis"]:
        params["rotation_degrees"] = -float(params["rotation_degrees"])
    return replace(operation, parameters=params)


def _convert_point(
    x: float, y: float, source: dict[str, Any], target: dict[str, Any]
) -> tuple[float, float]:
    width = float(source.get("width", 0.0))
    height = float(source.get("height", 0.0))
    source_x, source_y = _origin(source["origin"], width, height)
    canonical_x = source_x + x
    canonical_y = source_y + y * (1.0 if source["y_axis"] == "up" else -1.0)
    converted_x = _convert_length(canonical_x, source, target)
    converted_y = _convert_length(canonical_y, source, target)
    target_x, target_y = _origin(
        target["origin"], float(target.get("width", 0.0)), float(target.get("height", 0.0))
    )
    return (
        round(converted_x - target_x, 9),
        round((converted_y - target_y) * (1.0 if target["y_axis"] == "up" else -1.0), 9),
    )


def _origin(name: str, width: float, height: float) -> tuple[float, float]:
    if name == "top-left":
        return 0.0, height
    if name == "bottom-left":
        return 0.0, 0.0
    return width / 2.0, height / 2.0


def _convert_length(value: float, source: dict[str, Any], target: dict[str, Any]) -> float:
    inches = _to_inches(value, source["unit"], float(source.get("dpi", 96.0)))
    result = _from_inches(inches, target["unit"], float(target.get("dpi", 96.0)))
    return round(result, 9)


def _to_inches(value: float, unit: str, dpi: float) -> float:
    factors = {"in": 1.0, "cm": 1 / 2.54, "mm": 1 / 25.4, "pt": 1 / 72.0}
    if unit == "px":
        return value / dpi
    if unit == "blender-unit":
        return value / 0.0254  # Blender's default unit represents one meter.
    return value * factors[unit]


def _from_inches(value: float, unit: str, dpi: float) -> float:
    factors = {"in": 1.0, "cm": 2.54, "mm": 25.4, "pt": 72.0}
    if unit == "px":
        return value * dpi
    if unit == "blender-unit":
        return value * 0.0254
    return value * factors[unit]
