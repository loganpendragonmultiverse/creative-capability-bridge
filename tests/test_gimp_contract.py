import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from creative_capability_bridge.adapters.gimp import GimpAdapter
from creative_capability_bridge.inspection import inspect_document
from creative_capability_bridge.schema import PlanError, parse_plan


def test_batch_has_fresh_instance_and_termination(tmp_path: Path) -> None:
    command = GimpAdapter("gimp")._command(tmp_path / "script.scm")
    assert "--new-instance" in command and "--quit" in command
    assert "--no-fonts" not in command


@pytest.mark.parametrize(
    "params,expected",
    [
        ({"x": 12}, "layer 12 (cadr offsets)"),
        ({"y": -8}, "layer (car offsets) -8"),
    ],
)
def test_partial_position_preserves_other_axis(
    tmp_path: Path, params: dict[str, int], expected: str
) -> None:
    plan = parse_plan(
        {
            "version": 1,
            "adapter": "gimp",
            "input": None,
            "output": str(tmp_path / "out.xcf"),
            "operations": [
                {"capability": "transform.set", "target": "title", "parameters": params}
            ],
        }
    )
    assert expected in GimpAdapter().script(plan)


@pytest.mark.parametrize(
    "record,message",
    [
        ("broken\n", "malformed"),
        ("zz\t1\t1\t0\t0\ttext\t43\t0 0 0 255\n", "invalid text"),
        ("110000\t1\t1\t0\t0\ttext\t43\t0 0 0 255\n", "invalid text"),
    ],
)
def test_inspection_rejects_bad_records(tmp_path: Path, record: str, message: str) -> None:
    source = tmp_path / "source.xcf"
    source.write_bytes(b"mock")

    def command(_adapter: object, script: Path) -> list[str]:
        (script.parent / "layers.tsv").write_text(record, encoding="utf-8")
        return ["gimp"]

    with (
        patch.object(GimpAdapter, "_command", autospec=True, side_effect=command),
        patch(
            "creative_capability_bridge.inspection.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, "", ""),
        ),
        pytest.raises(PlanError, match=message),
    ):
        inspect_document(source, executable="gimp")


@pytest.mark.parametrize(
    "fill,components",
    [
        ("#24342F80", "'(36 52 47 128)"),
        ("#123456", "'(18 52 86 255)"),
    ],
)
def test_gimp_color_encodes_explicit_alpha(tmp_path: Path, fill: str, components: str) -> None:
    plan = parse_plan(
        {
            "version": 1,
            "adapter": "gimp",
            "input": None,
            "output": str(tmp_path / "out.xcf"),
            "operations": [
                {
                    "capability": "text.create",
                    "target": "title",
                    "parameters": {"content": "Color", "fill": fill},
                }
            ],
        }
    )
    assert components in GimpAdapter().script(plan)
