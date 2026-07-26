"""Read-only inspection for supported creative documents."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .schema import PlanError

SVG_NS = "http://www.w3.org/2000/svg"


def inspect_document(path: Path, *, executable: str | None = None) -> dict[str, Any]:
    source = path.resolve()
    if not source.is_file():
        raise PlanError(f"Document does not exist: {source}")
    suffix = source.suffix.lower()
    if suffix == ".svg":
        return _inspect_svg(source)
    if suffix == ".blend":
        return _inspect_blend(source, executable)
    raise PlanError("Inspection supports .svg and .blend documents.")


def _inspect_svg(path: Path) -> dict[str, Any]:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise PlanError(f"Could not parse SVG input: {exc}") from exc
    if root.tag != f"{{{SVG_NS}}}svg":
        raise PlanError("Input is not an SVG document.")
    objects: list[dict[str, Any]] = []
    for element in root.iter():
        if element is root:
            continue
        identifier = element.get("data-ccb-id") or element.get("id")
        kind = element.tag.rsplit("}", 1)[-1]
        if not identifier and kind != "text":
            continue
        objects.append(
            {
                "id": identifier,
                "type": kind,
                "modifiable": bool(identifier),
                "text": "".join(element.itertext()) if kind == "text" else None,
                "font_family": element.get("font-family"),
                "font_size": element.get("font-size"),
                "x": element.get("x"),
                "y": element.get("y"),
                "transform": element.get("transform"),
            }
        )
    return {"format": "svg", "path": str(path), "read_only": True, "objects": objects}


def _inspect_blend(path: Path, executable: str | None) -> dict[str, Any]:
    blender = executable or shutil.which("blender")
    if not blender:
        raise PlanError("Blender executable was not found. Install Blender or pass --executable.")
    with tempfile.TemporaryDirectory(prefix="ccb-inspect-") as temp_dir:
        script = Path(temp_dir) / "inspect.py"
        output = Path(temp_dir) / "inspection.json"
        script.write_text(_BLENDER_INSPECTION_SCRIPT, encoding="utf-8")
        result = subprocess.run(
            [
                blender,
                "--background",
                str(path),
                "--python-exit-code",
                "1",
                "--python",
                str(script),
                "--",
                str(output),
            ],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if result.returncode != 0 or not output.is_file():
            detail = (result.stderr or result.stdout).strip()[-2000:]
            raise PlanError(f"Blender inspection failed: {detail}")
        payload = json.loads(output.read_text(encoding="utf-8"))
    return {"format": "blend", "path": str(path), "read_only": True, "objects": payload}


_BLENDER_INSPECTION_SCRIPT = r"""import json
import sys
import bpy

items = []
for obj in bpy.data.objects:
    identifier = obj.get("ccb_id") or obj.name
    item = {
        "id": identifier,
        "type": obj.type.lower(),
        "modifiable": bool(identifier),
        "location": list(obj.location),
        "rotation_degrees": [value * 57.29577951308232 for value in obj.rotation_euler],
        "scale": list(obj.scale),
    }
    if obj.type == "FONT":
        item.update({
            "text": obj.data.body,
            "font_family": obj.get("ccb_font_family_requested") or getattr(obj.data.font, "name", None),
            "font_size": obj.data.size,
        })
    items.append(item)
with open(sys.argv[sys.argv.index("--") + 1], "w", encoding="utf-8") as handle:
    json.dump(items, handle, indent=2)
"""
