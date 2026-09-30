from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from creative_capability_bridge.cli import main
from creative_capability_bridge.review_tools import compare_plans, preflight
from creative_capability_bridge.schema import parse_plan


def payload(tmp_path: Path) -> dict[str, Any]:
    return {
        "version": 1,
        "adapter": "inkscape",
        "input": None,
        "output": str(tmp_path / "output.svg"),
        "operations": [
            {
                "id": "first",
                "capability": "text.create",
                "target": "title",
                "parameters": {"content": "PRIVATE TEXT"},
            },
            {
                "id": "second",
                "capability": "text.create",
                "target": "subtitle",
                "parameters": {"content": "More"},
            },
        ],
    }


def test_preflight_preserves_source_and_checks_output(tmp_path: Path) -> None:
    plan = parse_plan(payload(tmp_path))
    assert preflight(plan)["ready"] and not preflight(plan)["executed"]
    plan.output_path.write_text("existing")
    assert not preflight(plan)["ready"]
    assert preflight(plan, replace=True)["ready"]
    assert plan.output_path.read_text() == "existing"
    assert preflight(plan, receipt=plan.output_path)["errors"]
    plan.output_path.unlink()
    plan.output_path.mkdir()
    assert not preflight(plan, replace=True)["ready"]


def test_input_lint_policy_and_missing_paths(tmp_path: Path) -> None:
    p = payload(tmp_path)
    p["input"] = str(tmp_path / "input.svg")
    plan = parse_plan(p)
    assert not preflight(plan)["ready"]
    assert plan.input_path is not None
    plan.input_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text id="title">Old</text></svg>'
    )
    report = preflight(plan, inspect=True)
    assert not report["ready"] and report["inspection_performed"]
    assert report["input_evidence"][0]["sha256"]
    assert preflight(plan)["warnings"]
    p["output"] = str(tmp_path / "missing" / "out.svg")
    assert not preflight(parse_plan(p))["ready"]
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"policy_version": 1, "require_receipt": True}))
    assert not preflight(plan, policy_path=policy)["ready"]
    receipt = tmp_path / "receipt.json"
    receipt.write_text("{}")
    assert not preflight(plan, receipt=receipt)["ready"]


def test_font_checks_and_operation_flow(tmp_path: Path) -> None:
    p = payload(tmp_path)
    p["adapter"] = "blender"
    p["output"] = str(tmp_path / "out.blend")
    p["operations"][0]["parameters"]["font_file"] = str(tmp_path / "absent.ttf")
    assert not preflight(parse_plan(p))["ready"]
    font = tmp_path / "font.ttf"
    font.write_bytes(b"fixture")
    p["operations"][0]["parameters"]["font_file"] = str(font)
    assert preflight(parse_plan(p))["ready"]
    p["operations"][1] = p["operations"][0].copy()
    p["operations"][1]["id"] = "second"
    assert not preflight(parse_plan(p))["ready"]


def test_plan_diff_is_value_free_and_reports_order(tmp_path: Path) -> None:
    p = payload(tmp_path)
    before = parse_plan(p)
    assert compare_plans(before, before)["equivalent"]
    p["operations"][0]["parameters"]["content"] = "NEW PRIVATE"
    p["operations"].reverse()
    p["output"] = str(tmp_path / "other.svg")
    report = compare_plans(before, parse_plan(p))
    assert report["changed"] == [{"operation": "first", "fields": ["parameters.content"]}]
    assert report["reordered"] and "output_path" in report["metadata_changed"]
    assert "PRIVATE" not in json.dumps(report)
    p["operations"].pop()
    report = compare_plans(before, parse_plan(p))
    assert report["removed"] == ["first"]
    p["operations"].append(
        {
            "id": "third",
            "capability": "text.create",
            "target": "third",
            "parameters": {"content": "Three"},
        }
    )
    assert compare_plans(before, parse_plan(p))["added"] == ["third"]
    p["operations"][0]["tags"] = ["changed"]
    p["operations"][0]["target"] = "changed"
    p["operations"][0]["parameters"]["x"] = 1
    assert compare_plans(before, parse_plan(p))["changed"]


def test_cli_reports_and_no_overwrite(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "plan.json"
    source.write_text(json.dumps(payload(tmp_path)))
    before = source.read_bytes()
    assert main(["preflight", str(source)]) == 0
    report = tmp_path / "review.json"
    assert main(["preflight", str(source), "--output", str(report)]) == 0
    assert main(["preflight", str(source), "--output", str(report)]) == 2
    assert main(["compare-plans", str(source), str(source)]) == 0
    assert (
        main(["compare-plans", str(source), str(source), "--output", str(tmp_path / "diff.json")])
        == 0
    )
    p = payload(tmp_path)
    p["operations"][0]["parameters"]["content"] = "Different"
    other = tmp_path / "other.json"
    other.write_text(json.dumps(p))
    assert main(["compare-plans", str(source), str(other)]) == 1
    (tmp_path / "output.svg").write_text("existing")
    assert main(["preflight", str(source)]) == 1
    assert source.read_bytes() == before
    assert "executed" in capsys.readouterr().out
