"""Real GIMP 3 acceptance; mocks cannot satisfy this gate."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import pytest

from creative_capability_bridge.adapters.gimp import GimpAdapter, _find_gimp
from creative_capability_bridge.inspection import inspect_document
from creative_capability_bridge.schema import PlanError, parse_plan

pytestmark = pytest.mark.skipif(
    os.environ.get("CCB_REQUIRE_GIMP") != "1" and not _find_gimp(),
    reason="GIMP 3 native acceptance is not available",
)


def test_gimp_native_saved_text_transforms_and_guards(tmp_path: Path) -> None:
    adapter = GimpAdapter()
    version = adapter.application_version()
    assert version and "3." in version

    def execute(
        name: str,
        params: dict[str, Any],
        source: Path | None = None,
        capability: str = "text.create",
        target: str = "title",
    ) -> Path:
        plan = parse_plan(
            {
                "version": 1,
                "adapter": "gimp",
                "input": str(source) if source else None,
                "output": str(tmp_path / name),
                "operations": [{"capability": capability, "target": target, "parameters": params}],
            }
        )
        return adapter.execute(plan)

    def inspect(path: Path) -> dict[str, Any]:
        original = path.read_bytes()
        result = inspect_document(path, executable=adapter.executable)["objects"]
        assert path.read_bytes() == original
        return next(item for item in result if item["id"] == "title")

    source = execute(
        "created.xcf",
        {
            "content": "Café\tline\nΩ",
            "font_family": "DejaVu Sans Book",
            "font_size": 20,
            "fill": "#24342F80",
            "x": 12,
            "y": 18,
        },
    )
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    first = inspect(source)
    assert first["text"] == "Café\tline\nΩ"
    assert first["fill"] == "#24342F80"
    assert (first["x"], first["y"]) == (12, 18)
    assert first["width"] > 0 and first["height"] > 0

    updated = execute("updated.xcf", {"content": "Reopened ✓"}, source, "text.update")
    assert inspect(updated)["text"] == "Reopened ✓"
    moved = execute("moved.xcf", {"x": 42}, source, "transform.set")
    assert (inspect(moved)["x"], inspect(moved)["y"]) == (42, 18)
    scaled = execute("scaled.xcf", {"scale_x": 2, "scale_y": 3}, source, "transform.set")
    measured = inspect(scaled)
    assert measured["width"] == first["width"] * 2
    assert measured["height"] == first["height"] * 3
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before

    with pytest.raises(PlanError, match="already exists"):
        execute("created.xcf", {"content": "collision"})
    with pytest.raises(PlanError, match="GIMP failed"):
        execute("missing.xcf", {"content": "bad"}, source, "text.update", "absent")
    assert not (tmp_path / "missing.xcf").exists()
    with pytest.raises(PlanError, match="GIMP failed"):
        execute("bad-font.xcf", {"content": "bad", "font_family": "CCB missing font resource"})
    assert not (tmp_path / "bad-font.xcf").exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_shipped_gimp_example_uses_installed_default_font(tmp_path: Path) -> None:
    import json

    example = Path(__file__).resolve().parents[1] / "examples" / "gimp-text.json"
    original = example.read_bytes()
    payload = json.loads(original)
    payload["output"] = str(tmp_path / "shipped-example.xcf")
    adapter = GimpAdapter()
    output = adapter.execute(parse_plan(payload))
    report = inspect_document(output, executable=adapter.executable)
    item = next(item for item in report["objects"] if item["id"] == "title")
    assert item["text"] == "Portable creative work"
    assert item["fill"] == "#24342FFF"
    assert (item["x"], item["y"]) == (600, 350)
    assert example.read_bytes() == original
