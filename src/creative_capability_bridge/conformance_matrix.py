"""Generated transform/pivot cases and evidence-bounded application matrix."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .conformance import _adapter, run_conformance
from .execution import execute_transactionally
from .schema import ADAPTERS, PlanError, parse_plan

PIVOTS = {
    "blender": "Object origin; Z-axis rotation; native object coordinates",
    "inkscape": "SVG local origin; translate, then rotate, then scale attribute order",
    "gimp": "Layer center for rotation; layer-offset coordinates; raster transforms may be lossy",
}


def fixture_plans(adapter: str, directory: Path) -> list[dict[str, Any]]:
    suffix = {"blender": ".blend", "inkscape": ".svg", "gimp": ".xcf"}[adapter]
    cases = []
    for name, params in [
        ("identity", {"x": 0, "y": 0, "rotation_degrees": 0, "scale_x": 1, "scale_y": 1}),
        ("translated", {"x": 12, "y": 15}),
        ("rotated", {"rotation_degrees": 30}),
        ("scaled", {"scale_x": 1.5, "scale_y": 0.75}),
    ]:
        cases.append(
            {
                "version": 1,
                "adapter": adapter,
                "input": None,
                "output": str(directory / (name + suffix)),
                "operations": [
                    {
                        "capability": "text.create",
                        "target": "fixture",
                        "parameters": {
                            "content": "CCB transform fixture",
                            "font_size": 12,
                            "x": 0,
                            "y": 0,
                        },
                    },
                    {"capability": "transform.set", "target": "fixture", "parameters": params},
                ],
            }
        )
    return cases


def generate_fixtures(directory: Path) -> dict[str, Any]:
    if directory.exists():
        raise PlanError("Fixture directory must be new.")
    directory.mkdir(parents=True)
    records = []
    for adapter in ADAPTERS:
        folder = directory / adapter
        folder.mkdir()
        for i, plan in enumerate(fixture_plans(adapter, folder)):
            file = folder / f"{i + 1}-plan.json"
            file.write_text(json.dumps(plan, indent=2), encoding="utf-8")
            restore = {
                "version": 1,
                "adapter": adapter,
                "input": plan["output"],
                "output": str(folder / f"restored-{i}{Path(plan['output']).suffix}"),
                "operations": [
                    {
                        "capability": "text.update",
                        "target": "fixture",
                        "parameters": {"content": "CCB round-trip"},
                    },
                    {
                        "capability": "transform.set",
                        "target": "fixture",
                        "parameters": {
                            "x": 0,
                            "y": 0,
                            "rotation_degrees": 0,
                            "scale_x": 1,
                            "scale_y": 1,
                        },
                    },
                ],
            }
            (folder / f"{i + 1}-roundtrip.json").write_text(
                json.dumps(restore, indent=2), encoding="utf-8"
            )
            records.append(
                {
                    "plan": str(file.relative_to(directory)),
                    "pivot": PIVOTS[adapter],
                    "assertions": [
                        "input hash unchanged",
                        "fixture target retained",
                        "inspect native transform semantics",
                        "round-trip content and transform inspected",
                    ],
                    "native_acceptance": "not run by generator",
                }
            )
    report = {
        "schema_version": 1,
        "fixtures": records,
        "boundary": "Plans declare adapter-specific pivots. Unlike raster and vector transforms are not claimed equivalent.",
    }
    (directory / "manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def run_matrix(native: bool = False, executables: dict[str, str] | None = None) -> dict[str, Any]:
    rows = []
    for name in ADAPTERS:
        executable = (executables or {}).get(name)
        adapter = _adapter(name, executable)
        row: dict[str, Any] = {
            "adapter": name,
            "pivot": PIVOTS[name],
            "application_version": None,
            "native_verified": False,
        }
        try:
            row["application_version"] = adapter.application_version()
            row["contract"] = run_conformance(name, executable=executable, native=native)
            row["native_verified"] = bool(
                native and row["application_version"] and row["contract"]["passed"]
            )
            row["status"] = "native-smoke-verified" if row["native_verified"] else "contract-only"
            row["transform_roundtrip"] = "not verified"
            if native and name == "blender" and row["native_verified"]:
                row["transform_roundtrip"] = blender_roundtrip(executable)
                if not row["transform_roundtrip"]["passed"]:
                    row.update(native_verified=False, status="native-transform-failed")
            if name == "inkscape":
                row["svg_roundtrip"] = svg_roundtrip()
        except (PlanError, OSError, TimeoutError, subprocess.TimeoutExpired) as error:
            row.update(native_verified=False, status="unavailable-or-failed", error=str(error))
        rows.append(row)
    return {
        "schema_version": 1,
        "applications": rows,
        "boundary": "Native smoke verifies creation/inspection only. SVG round-trip evidence is a document-adapter test, not native application rendering. Blender transform round-trips are reported when native checks run; GIMP still requires semantic acceptance.",
    }


def svg_roundtrip() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ccb-svg-matrix-") as temporary:
        folder = Path(temporary)
        adapter = _adapter("inkscape", None)
        cases = []
        for plan_data in fixture_plans("inkscape", folder):
            plan = parse_plan(plan_data)
            first = execute_transactionally(plan, adapter)
            before = hashlib.sha256(plan.output_path.read_bytes()).hexdigest()
            data = {
                "version": 1,
                "adapter": "inkscape",
                "input": str(plan.output_path),
                "output": str(folder / ("round-" + plan.output_path.name)),
                "operations": [
                    {
                        "capability": "text.update",
                        "target": "fixture",
                        "parameters": {"content": "CCB round-trip"},
                    }
                ],
            }
            second = execute_transactionally(parse_plan(data), adapter)
            a = next(item for item in first.inspection["objects"] if item["id"] == "fixture")
            b = next(item for item in second.inspection["objects"] if item["id"] == "fixture")
            passed = (
                b["text"] == "CCB round-trip"
                and a["transform"] == b["transform"]
                and hashlib.sha256(plan.output_path.read_bytes()).hexdigest() == before
            )
            cases.append(
                {
                    "case": plan.output_path.stem,
                    "passed": passed,
                    "transform": b["transform"],
                    "source_sha256": before,
                }
            )
        return {"passed": all(item["passed"] for item in cases), "cases": cases}


def blender_roundtrip(executable: str | None = None) -> dict[str, Any]:
    import math

    with tempfile.TemporaryDirectory(prefix="ccb-blender-matrix-") as temporary:
        folder = Path(temporary)
        adapter = _adapter("blender", executable)
        cases = []
        for payload in fixture_plans("blender", folder):
            plan = parse_plan(payload)
            first = execute_transactionally(plan, adapter)
            before = hashlib.sha256(plan.output_path.read_bytes()).hexdigest()
            obj = next(item for item in first.inspection["objects"] if item["id"] == "fixture")
            expected = payload["operations"][1]["parameters"]
            transform = (
                all(
                    math.isclose(float(obj["location"][i]), expected.get(axis, 0), abs_tol=1e-5)
                    for i, axis in enumerate(["x", "y"])
                )
                and math.isclose(
                    float(obj["rotation_degrees"][2]),
                    expected.get("rotation_degrees", 0),
                    abs_tol=1e-4,
                )
                and all(
                    math.isclose(float(obj["scale"][i]), expected.get(axis, 1), abs_tol=1e-5)
                    for i, axis in enumerate(["scale_x", "scale_y"])
                )
            )
            update = {
                "version": 1,
                "adapter": "blender",
                "input": str(plan.output_path),
                "output": str(folder / ("round-" + plan.output_path.name)),
                "operations": [
                    {
                        "capability": "text.update",
                        "target": "fixture",
                        "parameters": {"content": "CCB round-trip"},
                    }
                ],
            }
            second = execute_transactionally(parse_plan(update), adapter)
            after = next(item for item in second.inspection["objects"] if item["id"] == "fixture")
            passed = (
                transform
                and after["text"] == "CCB round-trip"
                and all(after[key] == obj[key] for key in ["location", "rotation_degrees", "scale"])
                and hashlib.sha256(plan.output_path.read_bytes()).hexdigest() == before
            )
            cases.append({"case": plan.output_path.stem, "passed": passed, "source_sha256": before})
        return {"passed": all(item["passed"] for item in cases), "cases": cases}
