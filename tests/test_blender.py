from pathlib import Path
from unittest.mock import patch

import pytest

from creative_capability_bridge.adapters.blender import BlenderAdapter
from creative_capability_bridge.schema import PlanError, parse_plan


def make_plan(tmp_path: Path):  # type: ignore[no-untyped-def]
    return parse_plan(
        {
            "version": 1,
            "adapter": "blender",
            "input": None,
            "output": "result.blend",
            "operations": [
                {
                    "capability": "text.create",
                    "target": "title",
                    "parameters": {"content": "Hello\nBridge", "fill": "#FF000080", "z": 2},
                },
                {
                    "capability": "transform.set",
                    "target": "title",
                    "parameters": {"rotation_degrees": 30, "scale_x": 2},
                },
            ],
        },
        base_dir=tmp_path,
    )


def test_script_embeds_plan_safely_and_supports_core_operations(tmp_path: Path) -> None:
    script = BlenderAdapter("blender").script(make_plan(tmp_path))
    assert "Hello\nBridge" not in script
    assert "base64.b64decode" in script
    assert 'capability == "text.create"' in script
    assert "save_as_mainfile" in script


def test_preview_does_not_execute(tmp_path: Path) -> None:
    preview = BlenderAdapter("blender-test").preview(make_plan(tmp_path))
    assert preview["available"] is True
    assert preview["source_preserved"] is True
    assert preview["command"][0] == "blender-test"


def test_execute_checks_for_binary(tmp_path: Path) -> None:
    with pytest.raises(PlanError, match="not found"):
        BlenderAdapter().execute(make_plan(tmp_path))


def test_execute_requires_created_output(tmp_path: Path) -> None:
    result = type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    with patch("creative_capability_bridge.adapters.blender.subprocess.run", return_value=result):
        with pytest.raises(PlanError, match="did not create"):
            BlenderAdapter("blender-test").execute(make_plan(tmp_path))


def test_execute_returns_output_from_successful_process(tmp_path: Path) -> None:
    plan = make_plan(tmp_path)

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        plan.output_path.write_bytes(b"blend")
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    with patch("creative_capability_bridge.adapters.blender.subprocess.run", side_effect=fake_run):
        assert BlenderAdapter("blender-test").execute(plan) == plan.output_path


def test_execute_surfaces_process_failure(tmp_path: Path) -> None:
    result = type("Result", (), {"returncode": 9, "stdout": "", "stderr": "native failure"})()
    with patch("creative_capability_bridge.adapters.blender.subprocess.run", return_value=result):
        with pytest.raises(PlanError, match="native failure"):
            BlenderAdapter("blender-test").execute(make_plan(tmp_path))


def test_execute_refuses_existing_output(tmp_path: Path) -> None:
    plan = make_plan(tmp_path)
    plan.output_path.write_bytes(b"keep")
    with pytest.raises(PlanError, match="already exists"):
        BlenderAdapter("blender-test").execute(plan)


def test_application_version() -> None:
    result = type("Result", (), {"returncode": 0, "stdout": "Blender 4.3.0\n"})()
    with patch("creative_capability_bridge.adapters.blender.subprocess.run", return_value=result):
        assert BlenderAdapter("blender").application_version() == "Blender 4.3.0"
    with patch("creative_capability_bridge.adapters.blender.shutil.which", return_value=None):
        assert BlenderAdapter().application_version() is None
