import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pytest

from creative_capability_bridge.adapters.inkscape import SVG_NS, InkscapeAdapter
from creative_capability_bridge.schema import PlanError, parse_plan


def make_plan(tmp_path: Path, operations: list[dict[str, object]], input_name: str | None = None):  # type: ignore[no-untyped-def]
    return parse_plan(
        {
            "version": 1,
            "adapter": "inkscape",
            "input": input_name,
            "output": "output.svg",
            "operations": operations,
        },
        base_dir=tmp_path,
    )


def test_creates_text_and_transform_without_mutating_source(tmp_path: Path) -> None:
    source = tmp_path / "source.svg"
    original = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" />'
    source.write_text(original, encoding="utf-8")
    plan = make_plan(
        tmp_path,
        [
            {
                "capability": "text.create",
                "target": "heading",
                "parameters": {
                    "content": "Bridge",
                    "font_family": "Liberation Sans",
                    "font_size": 30,
                    "alignment": "center",
                    "fill": "#223344",
                    "x": 50,
                    "y": 20,
                },
            },
            {
                "capability": "transform.set",
                "target": "heading",
                "parameters": {
                    "x": 4,
                    "y": 5,
                    "rotation_degrees": 15,
                    "scale_x": 2,
                    "scale_y": 1.5,
                },
            },
        ],
        "source.svg",
    )
    output = InkscapeAdapter().execute(plan)
    element = ET.parse(output).getroot().find(f"{{{SVG_NS}}}text")
    assert element is not None
    assert element.text == "Bridge"
    assert element.get("font-size") == "30"
    assert element.get("text-anchor") == "middle"
    assert element.get("transform") == "translate(4 5) rotate(15) scale(2 1.5)"
    assert source.read_text(encoding="utf-8") == original


def test_updates_existing_bridge_text(tmp_path: Path) -> None:
    source = tmp_path / "source.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text id="title">Old</text></svg>',
        encoding="utf-8",
    )
    plan = make_plan(
        tmp_path,
        [{"capability": "text.update", "target": "title", "parameters": {"content": "New"}}],
        "source.svg",
    )
    output = InkscapeAdapter().execute(plan)
    assert ET.parse(output).getroot().find(f"{{{SVG_NS}}}text").text == "New"  # type: ignore[union-attr]


def test_refuses_existing_output_without_replace(tmp_path: Path) -> None:
    plan = make_plan(
        tmp_path,
        [{"capability": "text.create", "target": "title", "parameters": {"content": "Hi"}}],
    )
    plan.output_path.write_text("keep", encoding="utf-8")
    with pytest.raises(PlanError, match="already exists"):
        InkscapeAdapter().execute(plan)
    assert plan.output_path.read_text(encoding="utf-8") == "keep"


def test_missing_update_target_is_reported(tmp_path: Path) -> None:
    plan = make_plan(
        tmp_path,
        [{"capability": "text.update", "target": "missing", "parameters": {"content": "Hi"}}],
    )
    with pytest.raises(PlanError, match="not found"):
        InkscapeAdapter().execute(plan)


def test_native_preview_invokes_inkscape(tmp_path: Path) -> None:
    plan = make_plan(
        tmp_path,
        [{"capability": "text.create", "target": "title", "parameters": {"content": "Hi"}}],
    )
    preview = tmp_path / "preview.png"

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        preview.write_bytes(b"png")
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    with patch(
        "creative_capability_bridge.adapters.inkscape.subprocess.run", side_effect=fake_run
    ) as run:
        InkscapeAdapter("inkscape-test").execute(plan, render_preview=preview)
    assert run.call_args.args[0][0] == "inkscape-test"


def test_invalid_svg_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "source.svg").write_text("<not-svg />", encoding="utf-8")
    plan = make_plan(
        tmp_path,
        [{"capability": "text.create", "target": "title", "parameters": {"content": "Hi"}}],
        "source.svg",
    )
    with pytest.raises(PlanError, match="not an SVG"):
        InkscapeAdapter().execute(plan)


def test_malformed_svg_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "source.svg").write_text("<svg", encoding="utf-8")
    plan = make_plan(
        tmp_path,
        [{"capability": "text.create", "target": "title", "parameters": {"content": "Hi"}}],
        "source.svg",
    )
    with pytest.raises(PlanError, match="Could not parse"):
        InkscapeAdapter().execute(plan)


def test_duplicate_create_target_is_rejected(tmp_path: Path) -> None:
    operations: list[dict[str, object]] = [
        {"capability": "text.create", "target": "title", "parameters": {"content": "One"}},
        {"capability": "text.create", "target": "title", "parameters": {"content": "Two"}},
    ]
    with pytest.raises(PlanError, match="already exists"):
        InkscapeAdapter().execute(make_plan(tmp_path, operations))


def test_preview_requires_native_executable(tmp_path: Path) -> None:
    plan = make_plan(
        tmp_path,
        [{"capability": "text.create", "target": "title", "parameters": {"content": "Hi"}}],
    )
    with pytest.raises(PlanError, match="not found"):
        InkscapeAdapter().execute(plan, render_preview=tmp_path / "preview.png")


def test_application_version() -> None:
    result = type("Result", (), {"returncode": 0, "stdout": "Inkscape 1.4\n"})()
    with patch("creative_capability_bridge.adapters.inkscape.subprocess.run", return_value=result):
        assert InkscapeAdapter("inkscape").application_version() == "Inkscape 1.4"
    with patch("creative_capability_bridge.adapters.inkscape.shutil.which", return_value=None):
        assert InkscapeAdapter().application_version() is None
