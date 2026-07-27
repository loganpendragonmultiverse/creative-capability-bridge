"""GIMP 3 Script-Fu batch adapter for XCF documents."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..schema import Operation, Plan, PlanError


class GimpAdapter:
    """Execute text and transform capabilities through GIMP 3's bundled Script-Fu."""

    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or _find_gimp()

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "adapter": "gimp",
            "available": bool(self.executable),
            "transport": "GIMP 3 Script-Fu batch interpreter",
            "command": self._command(Path("<temporary-script.scm>")),
            "output": str(plan.output_path),
            "source_preserved": True,
            "operation_count": len(plan.operations),
        }

    def application_version(self) -> str | None:
        if not self.executable:
            return None
        result = subprocess.run(
            [self.executable, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result.stdout.splitlines()[0].strip() if result.returncode == 0 else None

    def execute(self, plan: Plan, *, replace: bool = False) -> Path:
        if not self.executable:
            raise PlanError("GIMP 3 executable was not found. Install GIMP 3 or pass --executable.")
        if plan.input_path and not plan.input_path.is_file():
            raise PlanError(f"Input file does not exist: {plan.input_path}")
        if plan.output_path.exists() and not replace:
            raise PlanError(
                f"Output already exists: {plan.output_path}. Pass --replace to replace it."
            )
        plan.output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ccb-gimp-") as temp_dir:
            script = Path(temp_dir) / "execute.scm"
            script.write_text(self.script(plan), encoding="utf-8")
            result = subprocess.run(
                self._command(script), capture_output=True, text=True, timeout=180, check=False
            )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()[-2000:]
            raise PlanError(f"GIMP failed with exit code {result.returncode}: {detail}")
        if not plan.output_path.is_file():
            raise PlanError("GIMP reported success but did not create the requested XCF output.")
        return plan.output_path

    def script(self, plan: Plan) -> str:
        width = int((plan.coordinate_space or {}).get("width", 1200))
        height = int((plan.coordinate_space or {}).get("height", 800))
        image_expression = (
            f"(gimp-file-load RUN-NONINTERACTIVE {_string(str(plan.input_path))})"
            if plan.input_path
            else f"(gimp-image-new {width} {height} RGB)"
        )
        operations = "\n".join(_operation_script(item) for item in plan.operations)
        return f"""(script-fu-use-v3)
(define (ccb-find-layer image target)
  (let loop ((items (vector->list (gimp-image-get-layers image))))
    (if (null? items) #f
      (if (string=? (gimp-item-get-name (car items)) target) (car items)
        (loop (cdr items))))))
(let* ((image {image_expression}))
  (gimp-image-undo-group-start image)
{operations}
  (gimp-image-undo-group-end image)
  (gimp-file-save RUN-NONINTERACTIVE image {_string(str(plan.output_path))} NULL)
  (gimp-image-delete image))
"""

    def _command(self, script: Path) -> list[str]:
        executable = self.executable or "gimp-console-3.0"
        script_path = str(script).replace("\\", "/")
        return [
            executable,
            "--no-interface",
            "--no-data",
            "--batch-interpreter=plug-in-script-fu-eval",
            f"--batch=(load {_string(script_path)})",
        ]


def _operation_script(operation: Operation) -> str:
    target = _string(operation.target)
    params = operation.parameters
    lines = [f"  ; {operation.capability} {operation.target}"]
    if operation.capability == "text.create":
        content = _string(str(params["content"]))
        font = _string(str(params.get("font_family", "Sans-serif")))
        size = float(params.get("font_size", 32.0))
        lines.extend(
            [
                f"  (if (ccb-find-layer image {target}) (quit -1))",
                f"  (let* ((font (gimp-font-get-by-name {font}))",
                f"         (layer (gimp-text-layer-new image {content} font {size} UNIT-PIXEL)))",
                f"    (gimp-item-set-name layer {target})",
                "    (gimp-image-insert-layer image layer -1 0)",
                *_text_updates("layer", params, include_content=False),
                *_transform_updates("layer", params),
                "  )",
            ]
        )
    else:
        lines.extend(
            [
                f"  (let* ((layer (ccb-find-layer image {target})))",
                "    (if (not layer) (quit -1))",
                *(
                    _text_updates("layer", params, include_content=True)
                    if operation.capability == "text.update"
                    else _transform_updates("layer", params)
                ),
                "  )",
            ]
        )
    return "\n".join(lines)


def _text_updates(layer: str, params: dict[str, Any], *, include_content: bool) -> list[str]:
    lines: list[str] = []
    if include_content and "content" in params:
        lines.append(f"    (gimp-text-layer-set-text {layer} {_string(str(params['content']))})")
    if "font_family" in params:
        lines.append(
            f"    (gimp-text-layer-set-font {layer} "
            f"(gimp-font-get-by-name {_string(str(params['font_family']))}))"
        )
    if "font_size" in params:
        lines.append(
            f"    (gimp-text-layer-set-font-size {layer} {float(params['font_size'])} UNIT-PIXEL)"
        )
    if "fill" in params:
        lines.append(f"    (gimp-text-layer-set-color {layer} {_string(str(params['fill']))})")
    if "alignment" in params:
        alignment = {
            "left": "TEXT-JUSTIFY-LEFT",
            "center": "TEXT-JUSTIFY-CENTER",
            "right": "TEXT-JUSTIFY-RIGHT",
        }[str(params["alignment"])]
        lines.append(f"    (gimp-text-layer-set-justification {layer} {alignment})")
    return lines


def _transform_updates(layer: str, params: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if "x" in params or "y" in params:
        lines.append(
            f"    (gimp-layer-set-offsets {layer} {round(params.get('x', 0))} "
            f"{round(params.get('y', 0))})"
        )
    if "scale_x" in params or "scale_y" in params:
        scale_x = float(params.get("scale_x", 1.0))
        scale_y = float(params.get("scale_y", 1.0))
        lines.extend(
            [
                (
                    f"    (gimp-layer-scale {layer} "
                    f"(max 1 (round (* (gimp-drawable-get-width {layer}) {scale_x}))) "
                    f"(max 1 (round (* (gimp-drawable-get-height {layer}) {scale_y}))) #t)"
                ),
            ]
        )
    if "rotation_degrees" in params:
        radians = math.radians(float(params["rotation_degrees"]))
        lines.append(f"    (gimp-item-transform-rotate {layer} {radians} #t 0 0)")
    return lines


def _find_gimp() -> str | None:
    for name in ("gimp-console-3.0", "gimp-3.0", "gimp-console", "gimp"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)
