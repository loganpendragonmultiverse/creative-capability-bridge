import os
import shutil
from pathlib import Path

import pytest

from creative_capability_bridge.adapters import BlenderAdapter, InkscapeAdapter
from creative_capability_bridge.schema import parse_plan

REQUIRE_NATIVE = os.environ.get("CCB_REQUIRE_NATIVE") == "1"


@pytest.mark.skipif(
    not REQUIRE_NATIVE and not shutil.which("blender"), reason="Blender is not installed"
)
def test_blender_native_smoke(tmp_path: Path) -> None:
    plan = parse_plan(
        {
            "version": 1,
            "adapter": "blender",
            "input": None,
            "output": "native.blend",
            "operations": [
                {
                    "capability": "text.create",
                    "target": "title",
                    "parameters": {"content": "Bridge", "x": 2},
                }
            ],
        },
        base_dir=tmp_path,
    )
    assert BlenderAdapter().execute(plan).stat().st_size > 0


@pytest.mark.skipif(
    not REQUIRE_NATIVE and not shutil.which("inkscape"), reason="Inkscape is not installed"
)
def test_inkscape_native_preview_smoke(tmp_path: Path) -> None:
    plan = parse_plan(
        {
            "version": 1,
            "adapter": "inkscape",
            "input": None,
            "output": "native.svg",
            "operations": [
                {
                    "capability": "text.create",
                    "target": "title",
                    "parameters": {"content": "Bridge", "x": 2},
                }
            ],
        },
        base_dir=tmp_path,
    )
    preview = tmp_path / "native.png"
    InkscapeAdapter().execute(plan, render_preview=preview)
    assert preview.stat().st_size > 0
