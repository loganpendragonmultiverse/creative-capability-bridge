"""Capability manifests exposed by the bundled adapters."""

from __future__ import annotations

from typing import Any


def manifest(adapter: str) -> dict[str, Any]:
    common: dict[str, Any] = {
        "protocol_version": 1,
        "adapter": adapter,
        "operations": {
            "text.create": ["content", "font_family", "font_size", "alignment", "fill"],
            "text.update": ["content", "font_family", "font_size", "alignment", "fill"],
            "transform.set": ["x", "y", "rotation_degrees", "scale_x", "scale_y"],
        },
        "guarantees": ["source-preserved", "explicit-output", "structured-errors"],
        "tested_versions": [],
    }
    if adapter == "blender":
        common["application"] = "Blender"
        common["transport"] = "background Python script"
        common["tested_versions"] = ["Blender 3.4", "Blender 4.x"]
        common["operations"]["text.create"] += ["x", "y", "z"]
        common["operations"]["transform.set"] += ["z", "scale_z"]
    elif adapter == "inkscape":
        common["application"] = "Inkscape"
        common["transport"] = "SVG document adapter with optional Inkscape CLI preview"
        common["tested_versions"] = ["Inkscape 1.2+"]
        common["operations"]["text.create"] += ["x", "y"]
    else:
        raise KeyError(adapter)
    return common


def all_manifests() -> list[dict[str, Any]]:
    return [manifest("blender"), manifest("inkscape")]
