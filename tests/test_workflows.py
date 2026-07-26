import json
import zipfile
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from creative_capability_bridge.bundles import create_bundle, verify_bundle
from creative_capability_bridge.explain import explain_plan
from creative_capability_bridge.inspection import inspect_document
from creative_capability_bridge.negotiation import compatibility, retarget
from creative_capability_bridge.receipts import build_receipt, compare_receipts, write_receipt
from creative_capability_bridge.schema import PlanError, load_plan


def plan_file(tmp_path: Path, *, adapter: str = "inkscape") -> Path:
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "adapter": adapter,
                "input": None,
                "output": "result.svg" if adapter != "blender" else "result.blend",
                "operations": [
                    {
                        "capability": "text.create",
                        "target": "title",
                        "parameters": {"content": "Portable", "font_family": "Inter"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_svg_inspection_is_read_only(tmp_path: Path) -> None:
    source = tmp_path / "sample.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text id="title" x="4" font-family="Inter">Hello</text></svg>',
        encoding="utf-8",
    )
    before = source.read_bytes()
    report = inspect_document(source)
    assert report["read_only"] is True
    assert report["objects"][0]["id"] == "title"
    assert report["objects"][0]["text"] == "Hello"
    assert source.read_bytes() == before


def test_explain_lists_boundaries(tmp_path: Path) -> None:
    report = explain_plan(load_plan(plan_file(tmp_path)))
    assert report["targets_created"] == ["title"]
    assert report["creates"] == [str((tmp_path / "result.svg").resolve())]
    assert report["source_preserved"] is True


def test_bundle_create_verify_and_detect_tamper(tmp_path: Path) -> None:
    plan = plan_file(tmp_path)
    asset = tmp_path / "font-license.txt"
    asset.write_text("OFL", encoding="utf-8")
    bundle = create_bundle(
        plan,
        tmp_path / "project.ccb.zip",
        assets=[asset],
        license_notes="Asset license included.",
        fallback_fonts=["sans-serif"],
    )
    assert verify_bundle(bundle)["valid"] is True
    with zipfile.ZipFile(bundle, "a") as archive:
        archive.writestr("plan.json", b"tampered")
    with pytest.raises(PlanError, match="duplicate"):
        verify_bundle(bundle)


def test_compatibility_and_retarget_auto_plan(tmp_path: Path) -> None:
    source = plan_file(tmp_path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["adapter"] = "auto"
    payload["output"] = "result"
    source.write_text(json.dumps(payload), encoding="utf-8")
    report = compatibility(source)
    assert {item["status"] for item in report["adapters"]} == {"exact", "approximate"}
    target = retarget(source, "inkscape", tmp_path / "inkscape-plan.json")
    assert load_plan(target).output_path.suffix == ".svg"


def test_compatibility_rejects_3d_for_inkscape(tmp_path: Path) -> None:
    source = plan_file(tmp_path, adapter="blender")
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["adapter"] = "auto"
    payload["operations"][0]["parameters"]["z"] = 2
    source.write_text(json.dumps(payload), encoding="utf-8")
    report = compatibility(source)
    inkscape = next(item for item in report["adapters"] if item["adapter"] == "inkscape")
    assert inkscape["status"] == "unsupported"


def test_receipts_record_hashes_and_compare(tmp_path: Path) -> None:
    plan = load_plan(plan_file(tmp_path))
    plan.output_path.write_text("one", encoding="utf-8")
    first = build_receipt(plan, started=0, application_version="Inkscape test")
    first_path = write_receipt(tmp_path / "first.json", first)
    plan.output_path.write_text("two", encoding="utf-8")
    second = build_receipt(plan, started=0, application_version="Inkscape test")
    second_path = write_receipt(tmp_path / "second.json", second)
    comparison = compare_receipts(first_path, second_path)
    assert comparison["same_output_hash"] is False
    assert comparison["operation_counts"] == {"left": 1, "right": 1}


def test_blend_inspection_uses_read_only_background_process(tmp_path: Path) -> None:
    source = tmp_path / "scene.blend"
    source.write_bytes(b"BLENDER")

    def fake_run(command: list[str], **_kwargs: object) -> CompletedProcess[str]:
        Path(command[-1]).write_text(
            json.dumps([{"id": "Title", "type": "font"}]), encoding="utf-8"
        )
        return CompletedProcess(command, 0, stdout="", stderr="")

    with patch("creative_capability_bridge.inspection.subprocess.run", side_effect=fake_run):
        report = inspect_document(source, executable="blender")
    assert report["format"] == "blend"
    assert report["objects"][0]["id"] == "Title"
    assert source.read_bytes() == b"BLENDER"


def test_inspection_rejects_missing_unknown_and_unavailable_blender(tmp_path: Path) -> None:
    with pytest.raises(PlanError, match="does not exist"):
        inspect_document(tmp_path / "missing.svg")
    unknown = tmp_path / "file.txt"
    unknown.write_text("text", encoding="utf-8")
    with pytest.raises(PlanError, match="supports"):
        inspect_document(unknown)
    blend = tmp_path / "file.blend"
    blend.write_bytes(b"BLENDER")
    with patch("creative_capability_bridge.inspection.shutil.which", return_value=None):
        with pytest.raises(PlanError, match="not found"):
            inspect_document(blend)


def test_bundle_and_receipt_error_paths(tmp_path: Path) -> None:
    plan = plan_file(tmp_path)
    with pytest.raises(PlanError, match="asset does not exist"):
        create_bundle(plan, tmp_path / "bad.zip", assets=[tmp_path / "missing.txt"])
    invalid = tmp_path / "invalid.zip"
    invalid.write_text("not zip", encoding="utf-8")
    with pytest.raises(PlanError, match="Could not verify"):
        verify_bundle(invalid)
    bad_receipt = tmp_path / "bad-receipt.json"
    bad_receipt.write_text("{}", encoding="utf-8")
    with pytest.raises(PlanError, match="Not a supported"):
        compare_receipts(bad_receipt, bad_receipt)


def test_retarget_rejects_unsupported_and_existing_destination(tmp_path: Path) -> None:
    source = plan_file(tmp_path, adapter="blender")
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["adapter"] = "auto"
    payload["operations"][0]["parameters"]["z"] = 2
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PlanError, match="cannot target inkscape"):
        retarget(source, "inkscape", tmp_path / "out.json")
    destination = tmp_path / "out.json"
    destination.write_text("existing", encoding="utf-8")
    with pytest.raises(PlanError, match="already exists"):
        retarget(source, "blender", destination)
