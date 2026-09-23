import json
from pathlib import Path

import pytest

from creative_capability_bridge.cli import main
from creative_capability_bridge.conformance_matrix import (
    generate_fixtures,
    run_matrix,
    svg_roundtrip,
)
from creative_capability_bridge.fonts import map_fonts
from creative_capability_bridge.schema import Plan, PlanError, parse_plan


def plan(tmp_path: Path, adapter: str = "inkscape") -> Plan:
    return parse_plan(
        {
            "version": 1,
            "adapter": adapter,
            "input": None,
            "output": str(tmp_path / ("out.blend" if adapter == "blender" else "out.svg")),
            "operations": [
                {
                    "capability": "text.create",
                    "target": "title",
                    "parameters": {"content": "Hello", "font_family": "Portable Sans"},
                }
            ],
        }
    )


def test_font_mapping_and_missing_diagnostics(tmp_path: Path) -> None:
    mapping = tmp_path / "fonts.json"
    mapping.write_text(
        json.dumps(
            {
                "version": 1,
                "families": {
                    "Portable Sans": {
                        "inkscape": {"family": "Example Sans"},
                        "blender": {"family": "Example Sans", "file": "missing.ttf"},
                    }
                },
            }
        )
    )
    source = plan(tmp_path)
    result, report = map_fonts(source, mapping)
    assert result.operations[0].parameters["font_family"] == "Example Sans"
    assert source.operations[0].parameters["font_family"] == "Portable Sans"
    assert report["fonts"][0]["status"] == "inventory-unverified"
    inventory = tmp_path / "inventory.json"
    inventory.write_text("[]")
    assert map_fonts(source, mapping, inventory)[1]["blocked"]
    inventory.write_text('["Example Sans"]')
    assert not map_fonts(source, mapping, inventory)[1]["blocked"]
    assert map_fonts(plan(tmp_path, "blender"), mapping)[1]["blocked"]
    (tmp_path / "missing.ttf").write_bytes(b"fixture-only")
    mapped, report = map_fonts(plan(tmp_path, "blender"), mapping)
    assert not report["blocked"]
    assert Path(mapped.operations[0].parameters["font_file"]).is_absolute()
    mapping.write_text('{"version":1,"families":{}}')
    assert map_fonts(source, mapping)[1]["blocked"]
    mapping.write_text("{}")
    with pytest.raises(PlanError):
        map_fonts(source, mapping)


def test_generated_cases_and_svg_roundtrip(tmp_path: Path) -> None:
    directory = tmp_path / "fixtures"
    report = generate_fixtures(directory)
    assert len(report["fixtures"]) == 12
    for item in report["fixtures"]:
        parse_plan(json.loads((directory / item["plan"]).read_text()))
    with pytest.raises(PlanError):
        generate_fixtures(directory)
    assert svg_roundtrip()["passed"]
    assert len(run_matrix()["applications"]) == 3
    matrix = tmp_path / "matrix.json"
    assert main(["conformance-matrix", "--output", str(matrix)]) == 0
    assert main(["conformance-matrix", "--output", str(matrix)]) == 2
    assert main(["conformance-fixtures", str(tmp_path / "cli-fixtures")]) == 0


def test_font_cli_refuses_existing_outputs(tmp_path: Path) -> None:
    source = tmp_path / "plan.json"
    source.write_text(json.dumps(plan(tmp_path).as_dict()))
    mapping = tmp_path / "mapping.json"
    mapping.write_text('{"version":1,"families":{"Portable Sans":{"inkscape":{"family":"Sans"}}}}')
    output = tmp_path / "mapped.json"
    assert main(["fonts", str(source), "--map", str(mapping), "--output", str(output)]) == 0
    assert main(["fonts", str(source), "--map", str(mapping), "--output", str(output)]) == 2
