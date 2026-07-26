"""Inkscape SVG document adapter with optional native preview rendering."""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ..schema import Operation, Plan, PlanError

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


class InkscapeAdapter:
    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or shutil.which("inkscape")

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "adapter": "inkscape",
            "available": bool(self.executable),
            "transport": "SVG document adapter",
            "native_preview_available": bool(self.executable),
            "output": str(plan.output_path),
            "source_preserved": True,
            "operation_count": len(plan.operations),
        }

    def application_version(self) -> str | None:
        if not self.executable:
            return None
        result = subprocess.run(
            [self.executable, "--version"], capture_output=True, text=True, timeout=30, check=False
        )
        return (
            result.stdout.splitlines()[0].strip()
            if result.returncode == 0 and result.stdout
            else None
        )

    def execute(
        self,
        plan: Plan,
        *,
        replace: bool = False,
        render_preview: Path | None = None,
    ) -> Path:
        if plan.input_path and not plan.input_path.is_file():
            raise PlanError(f"Input file does not exist: {plan.input_path}")
        if plan.output_path.exists() and not replace:
            raise PlanError(
                f"Output already exists: {plan.output_path}. Pass --replace to replace it."
            )
        root = self._root(plan)
        for operation in plan.operations:
            self._apply(root, operation)
        plan.output_path.parent.mkdir(parents=True, exist_ok=True)
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(plan.output_path, encoding="utf-8", xml_declaration=True)
        if render_preview:
            self._render(plan.output_path, render_preview)
        return plan.output_path

    def _root(self, plan: Plan) -> ET.Element:
        if plan.input_path:
            try:
                root = ET.parse(plan.input_path).getroot()
            except (ET.ParseError, OSError) as exc:
                raise PlanError(f"Could not parse SVG input: {exc}") from exc
            if root.tag != f"{{{SVG_NS}}}svg":
                raise PlanError("Input is not an SVG document.")
            return root
        return ET.Element(
            f"{{{SVG_NS}}}svg",
            {"width": "1200", "height": "800", "viewBox": "0 0 1200 800"},
        )

    def _apply(self, root: ET.Element, operation: Operation) -> None:
        target = _find_target(root, operation.target)
        params = operation.parameters
        if operation.capability == "text.create":
            if target is not None:
                raise PlanError(f"Target already exists: {operation.target}")
            target = ET.SubElement(
                root,
                f"{{{SVG_NS}}}text",
                {"id": operation.target, "data-ccb-id": operation.target},
            )
            _apply_text(target, params)
            target.set("x", _format_number(params.get("x", 0.0)))
            target.set("y", _format_number(params.get("y", 0.0)))
        elif operation.capability == "text.update":
            if target is None or target.tag != f"{{{SVG_NS}}}text":
                raise PlanError(f"Text target was not found: {operation.target}")
            _apply_text(target, params)
        elif operation.capability == "transform.set":
            if target is None:
                raise PlanError(f"Transform target was not found: {operation.target}")
            transform = (
                f"translate({_format_number(params.get('x', 0.0))} "
                f"{_format_number(params.get('y', 0.0))}) "
                f"rotate({_format_number(params.get('rotation_degrees', 0.0))}) "
                f"scale({_format_number(params.get('scale_x', 1.0))} "
                f"{_format_number(params.get('scale_y', 1.0))})"
            )
            target.set("transform", transform)

    def _render(self, svg_path: Path, preview_path: Path) -> None:
        if not self.executable:
            raise PlanError("Inkscape executable was not found; native preview cannot be rendered.")
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                self.executable,
                str(svg_path),
                f"--export-filename={preview_path}",
                "--export-area-drawing",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0 or not preview_path.is_file():
            detail = (result.stderr or result.stdout).strip()[-2000:]
            raise PlanError(f"Inkscape preview failed: {detail}")


def _find_target(root: ET.Element, target: str) -> ET.Element | None:
    for element in root.iter():
        if element.get("data-ccb-id") == target or element.get("id") == target:
            return element
    return None


def _apply_text(element: ET.Element, params: dict[str, Any]) -> None:
    if "content" in params:
        element.text = str(params["content"])
    if "font_family" in params:
        element.set("font-family", str(params["font_family"]))
    if "font_size" in params:
        element.set("font-size", _format_number(params["font_size"]))
    if "alignment" in params:
        element.set(
            "text-anchor",
            {"left": "start", "center": "middle", "right": "end"}[params["alignment"]],
        )
    if "fill" in params:
        element.set("fill", str(params["fill"]))


def _format_number(value: Any) -> str:
    numeric = float(value)
    return str(int(numeric)) if numeric.is_integer() else f"{numeric:.6f}".rstrip("0").rstrip(".")
