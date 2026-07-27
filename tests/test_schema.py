from pathlib import Path

import pytest

from creative_capability_bridge.schema import PlanError, load_plan, parse_plan


def payload(adapter: str = "inkscape") -> dict[str, object]:
    return {
        "version": 1,
        "adapter": adapter,
        "input": None,
        "output": "result.svg" if adapter == "inkscape" else "result.blend",
        "operations": [
            {
                "capability": "text.create",
                "target": "title",
                "parameters": {"content": "Hello", "font_size": 42, "fill": "#112233"},
            }
        ],
    }


def test_parses_valid_plan_relative_to_base(tmp_path: Path) -> None:
    plan = parse_plan(payload(), base_dir=tmp_path)
    assert plan.output_path == tmp_path / "result.svg"
    assert plan.operations[0].parameters["font_size"] == 42.0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("version", 2, "version"),
        ("adapter", "paint", "Adapter"),
        ("output", "", "output"),
        ("operations", [], "operations"),
    ],
)
def test_rejects_invalid_root_fields(field: str, value: object, message: str) -> None:
    data = payload()
    data[field] = value
    with pytest.raises(PlanError, match=message):
        parse_plan(data)


def test_rejects_same_input_and_output(tmp_path: Path) -> None:
    data = payload()
    data["input"] = "same.svg"
    data["output"] = "same.svg"
    with pytest.raises(PlanError, match="different"):
        parse_plan(data, base_dir=tmp_path)


@pytest.mark.parametrize("target", ["", "contains spaces", "0starts-wrong", "x" * 65])
def test_rejects_nonportable_target(target: str) -> None:
    data = payload()
    data["operations"][0]["target"] = target  # type: ignore[index]
    with pytest.raises(PlanError, match="portable identifier"):
        parse_plan(data)


@pytest.mark.parametrize(
    ("parameters", "message"),
    [
        ({}, "requires content"),
        ({"content": ""}, "content"),
        ({"content": "Hello", "fill": "red"}, "fill"),
        ({"content": "Hello", "font_size": 0}, "greater than zero"),
        ({"content": "Hello", "alignment": "justify"}, "alignment"),
        ({"content": "Hello", "surprise": True}, "Unknown"),
    ],
)
def test_rejects_invalid_text_parameters(parameters: dict[str, object], message: str) -> None:
    data = payload()
    data["operations"][0]["parameters"] = parameters  # type: ignore[index]
    with pytest.raises(PlanError, match=message):
        parse_plan(data)


def test_rejects_3d_parameter_for_inkscape() -> None:
    data = payload()
    data["operations"][0]["parameters"]["z"] = 3  # type: ignore[index]
    with pytest.raises(PlanError, match="two-dimensional"):
        parse_plan(data)


def test_accepts_3d_transform_for_blender() -> None:
    data = payload("blender")
    data["operations"] = [
        {
            "capability": "transform.set",
            "target": "title",
            "parameters": {"z": 2, "rotation_degrees": 90, "scale_z": 1.5},
        }
    ]
    plan = parse_plan(data)
    assert plan.operations[0].parameters["z"] == 2.0


def test_rejects_wrong_output_extension() -> None:
    data = payload()
    data["output"] = "wrong.blend"
    with pytest.raises(PlanError, match=".svg"):
        parse_plan(data)


def test_load_plan_reports_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(PlanError, match="Could not read"):
        load_plan(path)


@pytest.mark.parametrize("bad_payload", [None, [], "plan"])
def test_rejects_non_object_root(bad_payload: object) -> None:
    with pytest.raises(PlanError, match="root"):
        parse_plan(bad_payload)


def test_rejects_non_object_operation_and_parameters() -> None:
    data = payload()
    data["operations"] = ["wrong"]
    with pytest.raises(PlanError, match="operation"):
        parse_plan(data)
    data["operations"] = [{"capability": "text.update", "target": "title", "parameters": "wrong"}]
    with pytest.raises(PlanError, match="parameters"):
        parse_plan(data)


def test_rejects_boolean_and_out_of_range_numbers() -> None:
    data = payload()
    data["operations"] = [
        {"capability": "transform.set", "target": "title", "parameters": {"x": True}}
    ]
    with pytest.raises(PlanError, match="number"):
        parse_plan(data)
    data["operations"][0]["parameters"] = {"x": 2_000_000}  # type: ignore[index]
    with pytest.raises(PlanError, match="range"):
        parse_plan(data)
