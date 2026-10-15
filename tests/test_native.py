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


@pytest.mark.skipif(
    not REQUIRE_NATIVE and not shutil.which("blender"), reason="Blender is not installed"
)
def test_blender_native_transform_roundtrip_and_font(tmp_path: Path) -> None:
    from creative_capability_bridge.conformance_matrix import blender_roundtrip
    from creative_capability_bridge.execution import execute_transactionally

    assert blender_roundtrip()["passed"]
    font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font.exists():
        if REQUIRE_NATIVE:
            pytest.fail("Native font fixture is missing")
        pytest.skip("Native font fixture not available")
    payload = {
        "version": 1,
        "adapter": "blender",
        "input": None,
        "output": str(tmp_path / "font.blend"),
        "operations": [
            {
                "capability": "text.create",
                "target": "title",
                "parameters": {
                    "content": "Mapped font",
                    "font_family": "DejaVu Sans",
                    "font_file": str(font),
                },
            }
        ],
    }
    result = execute_transactionally(parse_plan(payload), BlenderAdapter())
    obj = next(item for item in result.inspection["objects"] if item["id"] == "title")
    assert Path(obj["font_file"]).resolve() == font.resolve()


@pytest.mark.skipif(
    not REQUIRE_NATIVE and not shutil.which("inkscape"), reason="Inkscape is not installed"
)
def test_native_svg_png_export_contract(tmp_path: Path) -> None:
    import hashlib
    import json

    from creative_capability_bridge.exports import execute_export, load_export_job

    source = tmp_path / "native-source.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 32"><rect width="64" height="32" fill="#123456"/></svg>',
        encoding="utf-8",
    )
    original = source.read_bytes()
    job = tmp_path / "export.json"
    job.write_text(
        json.dumps(
            {
                "export_version": 1,
                "format": "png",
                "source": source.name,
                "output": "native-export.png",
                "receipt": "native-export.json",
                "width": 64,
                "height": 32,
            }
        ),
        encoding="utf-8",
    )
    receipt = execute_export(load_export_job(job))
    assert source.read_bytes() == original
    assert (
        receipt["output"]["sha256"]
        == hashlib.sha256((tmp_path / "native-export.png").read_bytes()).hexdigest()
    )
