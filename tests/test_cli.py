import json
from pathlib import Path
from unittest.mock import patch

from creative_capability_bridge.cli import main


def write_plan(tmp_path: Path, adapter: str = "inkscape") -> Path:
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "adapter": adapter,
                "input": None,
                "output": "output.svg" if adapter == "inkscape" else "output.blend",
                "operations": [
                    {
                        "capability": "text.create",
                        "target": "title",
                        "parameters": {"content": "Hi"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_capabilities_json(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["capabilities", "inkscape", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["application"] == "Inkscape"


def test_validate_and_preview(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    plan = write_plan(tmp_path)
    assert main(["validate", str(plan)]) == 0
    assert "Valid v1" in capsys.readouterr().out
    assert main(["preview", str(plan)]) == 0
    assert json.loads(capsys.readouterr().out)["source_preserved"] is True


def test_execute_inkscape_plan(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    plan = write_plan(tmp_path)
    assert main(["execute", str(plan)]) == 0
    assert (tmp_path / "output.svg").is_file()
    assert "output.svg" in capsys.readouterr().out


def test_invalid_plan_returns_two(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "bad.json"
    path.write_text("{}", encoding="utf-8")
    assert main(["validate", str(path)]) == 2
    assert "error:" in capsys.readouterr().err


def test_plain_capabilities_and_doctor(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["capabilities"]) == 0
    assert "Blender" in capsys.readouterr().out
    with patch("creative_capability_bridge.cli.shutil.which", return_value=None):
        assert main(["doctor"]) == 1
    assert json.loads(capsys.readouterr().out) == {"blender": None, "inkscape": None}


def test_blender_rejects_inkscape_preview_option(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    plan = write_plan(tmp_path, "blender")
    assert main(["execute", str(plan), "--executable", "blender", "--render-preview", "x.png"]) == 2
    assert "only supported" in capsys.readouterr().err
