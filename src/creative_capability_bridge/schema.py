"""Canonical v1 plan parsing and validation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PLAN_VERSION = 1
ADAPTERS = ("blender", "inkscape")
CAPABILITIES = ("text.create", "text.update", "transform.set")
TARGET_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?$")


class PlanError(ValueError):
    """Raised when a capability plan is invalid or unsafe to execute."""


@dataclass(frozen=True)
class Operation:
    capability: str
    target: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class Plan:
    version: int
    adapter: str
    input_path: Path | None
    output_path: Path
    operations: tuple[Operation, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "adapter": self.adapter,
            "input": str(self.input_path) if self.input_path else None,
            "output": str(self.output_path),
            "operations": [
                {
                    "capability": operation.capability,
                    "target": operation.target,
                    "parameters": operation.parameters,
                }
                for operation in self.operations
            ],
        }


def load_plan(path: str | Path) -> Plan:
    plan_path = Path(path)
    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PlanError(f"Could not read plan: {exc}") from exc
    return parse_plan(payload, base_dir=plan_path.resolve().parent)


def parse_plan(payload: Any, *, base_dir: Path | None = None) -> Plan:
    if not isinstance(payload, dict):
        raise PlanError("Plan root must be a JSON object.")
    version = payload.get("version")
    if version != PLAN_VERSION:
        raise PlanError(f"Plan version must be {PLAN_VERSION}.")
    adapter = payload.get("adapter")
    if adapter not in ADAPTERS:
        raise PlanError(f"Adapter must be one of: {', '.join(ADAPTERS)}.")

    root = base_dir or Path.cwd()
    input_value = payload.get("input")
    if input_value is not None and not isinstance(input_value, str):
        raise PlanError("input must be a path string or null.")
    output_value = payload.get("output")
    if not isinstance(output_value, str) or not output_value.strip():
        raise PlanError("output must be a non-empty path string.")
    input_path = _resolve(root, input_value) if input_value else None
    output_path = _resolve(root, output_value)
    expected_suffix = ".blend" if adapter == "blender" else ".svg"
    if output_path.suffix.lower() != expected_suffix:
        raise PlanError(f"{adapter} output must use the {expected_suffix} extension.")
    if input_path and input_path == output_path:
        raise PlanError("input and output must be different; originals are never overwritten.")

    raw_operations = payload.get("operations")
    if not isinstance(raw_operations, list) or not 1 <= len(raw_operations) <= 100:
        raise PlanError("operations must contain between 1 and 100 items.")
    operations = tuple(_parse_operation(item, adapter) for item in raw_operations)
    return Plan(PLAN_VERSION, adapter, input_path, output_path, operations)


def _resolve(root: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def _parse_operation(payload: Any, adapter: str) -> Operation:
    if not isinstance(payload, dict):
        raise PlanError("Each operation must be an object.")
    capability = payload.get("capability")
    if capability not in CAPABILITIES:
        raise PlanError(f"Unsupported capability: {capability!r}.")
    target = payload.get("target")
    if not isinstance(target, str) or not TARGET_RE.fullmatch(target):
        raise PlanError("Operation target must be a portable identifier of 1-64 characters.")
    parameters = payload.get("parameters", {})
    if not isinstance(parameters, dict):
        raise PlanError("Operation parameters must be an object.")
    checked = _validate_parameters(capability, parameters, adapter)
    return Operation(capability, target, checked)


def _validate_parameters(capability: str, params: dict[str, Any], adapter: str) -> dict[str, Any]:
    allowed = {
        "text.create": {"content", "font_family", "font_size", "alignment", "fill", "x", "y", "z"},
        "text.update": {"content", "font_family", "font_size", "alignment", "fill"},
        "transform.set": {"x", "y", "z", "rotation_degrees", "scale_x", "scale_y", "scale_z"},
    }[capability]
    unknown = sorted(set(params) - allowed)
    if unknown:
        raise PlanError(f"Unknown {capability} parameters: {', '.join(unknown)}.")
    checked = dict(params)
    if capability == "text.create" and "content" not in checked:
        raise PlanError("text.create requires content.")
    if "content" in checked:
        content = checked["content"]
        if not isinstance(content, str) or not 1 <= len(content) <= 10_000:
            raise PlanError("content must be a string between 1 and 10,000 characters.")
    if "font_family" in checked and not isinstance(checked["font_family"], str):
        raise PlanError("font_family must be a string.")
    if "font_size" in checked:
        checked["font_size"] = _positive_number(checked["font_size"], "font_size")
    if "alignment" in checked and checked["alignment"] not in {"left", "center", "right"}:
        raise PlanError("alignment must be left, center, or right.")
    if "fill" in checked:
        fill = checked["fill"]
        if not isinstance(fill, str) or not HEX_COLOR_RE.fullmatch(fill):
            raise PlanError("fill must be #RRGGBB or #RRGGBBAA.")
    for key in ("x", "y", "z", "rotation_degrees"):
        if key in checked:
            checked[key] = _number(checked[key], key)
    for key in ("scale_x", "scale_y", "scale_z"):
        if key in checked:
            checked[key] = _positive_number(checked[key], key)
    if adapter == "inkscape" and any(key in checked for key in ("z", "scale_z")):
        raise PlanError("Inkscape is two-dimensional and does not support z or scale_z.")
    return checked


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanError(f"{name} must be a number.")
    numeric = float(value)
    if not -1_000_000 <= numeric <= 1_000_000:
        raise PlanError(f"{name} is outside the supported range.")
    return numeric


def _positive_number(value: Any, name: str) -> float:
    numeric = _number(value, name)
    if numeric <= 0:
        raise PlanError(f"{name} must be greater than zero.")
    return numeric
