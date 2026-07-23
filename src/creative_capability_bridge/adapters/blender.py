"""Blender background-process adapter."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..schema import Plan, PlanError


class BlenderAdapter:
    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or shutil.which("blender")

    def preview(self, plan: Plan) -> dict[str, Any]:
        command = self._command(plan, Path("<temporary-script.py>"))
        return {
            "adapter": "blender",
            "available": bool(self.executable),
            "command": command,
            "output": str(plan.output_path),
            "source_preserved": True,
            "operation_count": len(plan.operations),
        }

    def execute(self, plan: Plan, *, replace: bool = False) -> Path:
        if not self.executable:
            raise PlanError(
                "Blender executable was not found. Install Blender or pass --executable."
            )
        _guard_paths(plan, replace)
        plan.output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ccb-blender-") as temp_dir:
            script_path = Path(temp_dir) / "execute_plan.py"
            script_path.write_text(self.script(plan), encoding="utf-8")
            result = subprocess.run(
                self._command(plan, script_path),
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()[-2000:]
            raise PlanError(f"Blender failed with exit code {result.returncode}: {detail}")
        if not plan.output_path.is_file():
            raise PlanError("Blender reported success but did not create the requested output.")
        return plan.output_path

    def _command(self, plan: Plan, script_path: Path) -> list[str]:
        executable = self.executable or "blender"
        command = [executable, "--background"]
        if plan.input_path:
            command.append(str(plan.input_path))
        else:
            command.append("--factory-startup")
        command.extend(
            ["--python-exit-code", "1", "--python", str(script_path), "--", str(plan.output_path)]
        )
        return command

    def script(self, plan: Plan) -> str:
        encoded = base64.b64encode(json.dumps(plan.as_dict()).encode("utf-8")).decode("ascii")
        return _SCRIPT_TEMPLATE.replace("__PLAN_BASE64__", encoded)


def _guard_paths(plan: Plan, replace: bool) -> None:
    if plan.input_path and not plan.input_path.is_file():
        raise PlanError(f"Input file does not exist: {plan.input_path}")
    if plan.output_path.exists() and not replace:
        raise PlanError(f"Output already exists: {plan.output_path}. Pass --replace to replace it.")


_SCRIPT_TEMPLATE = r"""import base64
import json
import math
import sys

import bpy

plan = json.loads(base64.b64decode("__PLAN_BASE64__").decode("utf-8"))

def find_target(target):
    for item in bpy.data.objects:
        if item.get("ccb_id") == target or item.name == target:
            return item
    return None

def rgba(value):
    raw = value.lstrip("#")
    if len(raw) == 6:
        raw += "FF"
    return tuple(int(raw[index:index + 2], 16) / 255 for index in range(0, 8, 2))

def apply_text(obj, params):
    if "content" in params:
        obj.data.body = params["content"]
    if "font_size" in params:
        obj.data.size = params["font_size"]
    if "alignment" in params:
        obj.data.align_x = {"left": "LEFT", "center": "CENTER", "right": "RIGHT"}[params["alignment"]]
    if "font_family" in params:
        obj["ccb_font_family_requested"] = params["font_family"]
    if "fill" in params:
        material = obj.data.materials[0] if obj.data.materials else bpy.data.materials.new(obj.name + " Material")
        material.diffuse_color = rgba(params["fill"])
        if not obj.data.materials:
            obj.data.materials.append(material)

def apply_transform(obj, params):
    location = list(obj.location)
    for index, key in enumerate(("x", "y", "z")):
        if key in params:
            location[index] = params[key]
    obj.location = location
    if "rotation_degrees" in params:
        obj.rotation_euler[2] = math.radians(params["rotation_degrees"])
    scale = list(obj.scale)
    for index, key in enumerate(("scale_x", "scale_y", "scale_z")):
        if key in params:
            scale[index] = params[key]
    obj.scale = scale

for operation in plan["operations"]:
    capability = operation["capability"]
    target = operation["target"]
    params = operation["parameters"]
    obj = find_target(target)
    if capability == "text.create":
        if obj is not None:
            raise RuntimeError("Target already exists: " + target)
        curve = bpy.data.curves.new(target + " Text", type="FONT")
        obj = bpy.data.objects.new(target, curve)
        obj["ccb_id"] = target
        bpy.context.collection.objects.link(obj)
        apply_text(obj, params)
        apply_transform(obj, params)
    elif capability == "text.update":
        if obj is None or obj.type != "FONT":
            raise RuntimeError("Text target was not found: " + target)
        apply_text(obj, params)
    elif capability == "transform.set":
        if obj is None:
            raise RuntimeError("Transform target was not found: " + target)
        apply_transform(obj, params)

bpy.ops.wm.save_as_mainfile(filepath=sys.argv[sys.argv.index("--") + 1])
"""
