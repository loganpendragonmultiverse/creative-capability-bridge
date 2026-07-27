from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from creative_capability_bridge.adapters import GimpAdapter, InkscapeAdapter
from creative_capability_bridge.bundles import create_bundle, verify_bundle
from creative_capability_bridge.cli import main
from creative_capability_bridge.conformance import run_conformance
from creative_capability_bridge.coordinates import normalize_plan
from creative_capability_bridge.document_diff import compare_documents, compare_inspections
from creative_capability_bridge.execution import (
    execute_checkpointed,
    execute_transactionally,
    select_operations,
)
from creative_capability_bridge.inspection import inspect_document
from creative_capability_bridge.pipelines import execute_pipeline, validate_pipeline
from creative_capability_bridge.policies import check_policy, enforce_policy, validate_policy
from creative_capability_bridge.receipts import sign_receipt, verify_receipt, write_receipt
from creative_capability_bridge.schema import PlanError, parse_plan
from creative_capability_bridge.signing import (
    generate_keypair,
    sign_payload,
    verify_payload_signature,
)


def plan_payload(tmp_path: Path, *, output: str = "out.svg") -> dict[str, Any]:
    return {
        "version": 1,
        "adapter": "inkscape",
        "input": None,
        "output": str(tmp_path / output),
        "operations": [
            {
                "id": "create-title",
                "tags": ["titles", "phase-one"],
                "capability": "text.create",
                "target": "title",
                "parameters": {"content": "One", "x": 10, "y": 20},
            },
            {
                "id": "create-subtitle",
                "tags": ["titles", "phase-two"],
                "capability": "text.create",
                "target": "subtitle",
                "parameters": {"content": "Two", "x": 10, "y": 50},
            },
        ],
    }


def write_plan(tmp_path: Path, payload: dict[str, Any], name: str = "plan.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_operation_ids_tags_and_selection(tmp_path: Path) -> None:
    plan = parse_plan(plan_payload(tmp_path))
    selected, keys = select_operations(plan, only={"phase-two"})
    assert keys == ("create-subtitle",)
    assert selected[0].target == "subtitle"
    selected, keys = select_operations(plan, skip={"phase-one"}, from_operation="create-title")
    assert keys == ("create-subtitle",)
    duplicated = plan_payload(tmp_path)
    duplicated["operations"][1]["id"] = "create-title"
    with pytest.raises(PlanError, match="unique"):
        parse_plan(duplicated)


def test_coordinate_normalization_for_gimp(tmp_path: Path) -> None:
    payload = plan_payload(tmp_path, output="out.xcf")
    payload["adapter"] = "gimp"
    payload["coordinate_space"] = {
        "unit": "mm",
        "origin": "bottom-left",
        "y_axis": "up",
        "dpi": 96,
        "width": 254,
        "height": 127,
    }
    payload["operations"] = [
        {
            "capability": "text.create",
            "target": "title",
            "parameters": {"content": "Hi", "x": 25.4, "y": 25.4, "font_size": 12.7},
        }
    ]
    normalized = normalize_plan(parse_plan(payload))
    params = normalized.operations[0].parameters
    assert params["x"] == 96
    assert params["y"] == 384
    assert params["font_size"] == 48
    assert normalized.coordinate_space == {
        "unit": "px",
        "origin": "top-left",
        "y_axis": "down",
        "dpi": 96.0,
        "width": 960.0,
        "height": 480.0,
    }


def test_semantic_document_diff(tmp_path: Path) -> None:
    before = tmp_path / "before.svg"
    after = tmp_path / "after.svg"
    before.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text id="title" x="1">Old</text></svg>',
        encoding="utf-8",
    )
    after.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text id="title" x="2">New</text>'
        '<text id="subtitle">Sub</text></svg>',
        encoding="utf-8",
    )
    report = compare_documents(before, after)
    assert report["counts"] == {"added": 1, "removed": 0, "changed": 1, "unchanged": 0}
    assert set(report["changed"][0]["fields"]) == {"text", "x"}
    assert not report["equivalent"]
    assert compare_inspections({"objects": []}, {"objects": []})["equivalent"]


def test_transaction_backup_and_checkpoint_resume(tmp_path: Path) -> None:
    payload = plan_payload(tmp_path)
    plan = parse_plan(payload)
    adapter = InkscapeAdapter()
    state = tmp_path / "run.state.json"
    first = execute_checkpointed(plan, adapter, only={"create-title"}, state_path=state)
    assert first.output.is_file()
    assert first.completed == ("create-title",)
    resumed = execute_checkpointed(plan, adapter, state_path=state, resume=True)
    assert resumed.completed == ("create-title", "create-subtitle")
    report = compare_documents(first.output, resumed.output)
    assert report["counts"]["added"] == 0  # Both paths now refer to the final checkpoint.

    replacement = parse_plan(
        {
            "version": 1,
            "adapter": "inkscape",
            "input": str(resumed.output),
            "output": str(tmp_path / "replacement.svg"),
            "operations": [
                {
                    "capability": "text.update",
                    "target": "title",
                    "parameters": {"content": "Changed"},
                }
            ],
        }
    )
    replacement.output_path.write_text("old", encoding="utf-8")
    result = execute_transactionally(replacement, adapter, replace_output=True)
    assert result.backup and result.backup.read_text(encoding="utf-8") == "old"
    assert "Changed" in result.output.read_text(encoding="utf-8")


def test_resume_rejects_drift(tmp_path: Path) -> None:
    plan = parse_plan(plan_payload(tmp_path))
    state = tmp_path / "state.json"
    execute_checkpointed(plan, InkscapeAdapter(), only={"create-title"}, state_path=state)
    plan.output_path.write_text("tampered", encoding="utf-8")
    with pytest.raises(PlanError, match="changed"):
        execute_checkpointed(plan, InkscapeAdapter(), state_path=state, resume=True)


def test_policy_profiles(tmp_path: Path) -> None:
    plan = parse_plan(plan_payload(tmp_path))
    policy = validate_policy(
        {
            "policy_version": 1,
            "name": "restricted",
            "allowed_adapters": ["inkscape"],
            "allowed_capabilities": ["text.create"],
            "output_roots": [str(tmp_path)],
            "max_operations": 3,
            "require_receipt": True,
            "allow_replace": False,
        }
    )
    assert not check_policy(plan, policy)["valid"]
    assert check_policy(plan, policy, receipt=tmp_path / "receipt.json")["valid"]
    assert not check_policy(plan, policy, receipt=tmp_path / "r", replace=True)["valid"]


def test_pipeline_validation_and_execution(tmp_path: Path) -> None:
    first = plan_payload(tmp_path, output="one.svg")
    first["operations"] = first["operations"][:1]
    second = plan_payload(tmp_path, output="two.svg")
    second["operations"] = second["operations"][1:]
    write_plan(tmp_path, first, "one.json")
    write_plan(tmp_path, second, "two.json")
    pipeline_path = tmp_path / "pipeline.json"
    pipeline_path.write_text(
        json.dumps(
            {
                "pipeline_version": 1,
                "name": "two-documents",
                "steps": [
                    {"id": "second", "plan": "two.json", "depends_on": ["first"]},
                    {"id": "first", "plan": "one.json", "depends_on": []},
                ],
            }
        ),
        encoding="utf-8",
    )
    checked = validate_pipeline(json.loads(pipeline_path.read_text()), base_dir=tmp_path)
    assert [item["id"] for item in checked["steps"]] == ["first", "second"]
    result = execute_pipeline(
        pipeline_path,
        lambda _name, _executable: InkscapeAdapter(),
        receipt_dir=tmp_path / "receipts",
    )
    assert result["status"] == "completed"
    assert (tmp_path / "one.svg").is_file() and (tmp_path / "two.svg").is_file()
    assert (tmp_path / "receipts" / "first.receipt.json").is_file()

    cyclic = {
        "pipeline_version": 1,
        "steps": [
            {"id": "a", "plan": "one.json", "depends_on": ["b"]},
            {"id": "b", "plan": "two.json", "depends_on": ["a"]},
        ],
    }
    with pytest.raises(PlanError, match="cycle"):
        validate_pipeline(cyclic, base_dir=tmp_path)


def test_signed_bundles_and_receipts(tmp_path: Path) -> None:
    private = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    generate_keypair(private, public)
    plan_path = write_plan(tmp_path, plan_payload(tmp_path))
    bundle = create_bundle(plan_path, tmp_path / "project.ccb.zip", signing_key=private)
    report = verify_bundle(bundle, public_key=public, require_signature=True)
    assert report["valid"] and report["signature"]["verified"]

    receipt = {
        "receipt_version": 1,
        "status": "completed",
        "input": None,
        "output": None,
        "operations": [],
    }
    receipt_path = write_receipt(tmp_path / "receipt.json", receipt)
    signed = sign_receipt(receipt_path, tmp_path / "signed.json", private)
    assert verify_receipt(signed, public_key=public, require_signature=True)["verified"]
    payload = json.loads(signed.read_text(encoding="utf-8"))
    payload["status"] = "altered"
    signed.write_text(json.dumps(payload), encoding="utf-8")
    assert not verify_receipt(signed, public_key=public, require_signature=True)["verified"]
    assert sign_payload({"value": 1}, private)["algorithm"] == "Ed25519"


def test_gimp_adapter_and_conformance_contract(tmp_path: Path) -> None:
    payload = plan_payload(tmp_path, output="out.xcf")
    payload["adapter"] = "gimp"
    plan = parse_plan(payload)
    adapter = GimpAdapter("gimp-console-3.0")
    script = adapter.script(plan)
    assert "gimp-text-layer-new" in script
    assert "gimp-file-save" in script
    assert '"subtitle"' in script
    preview = adapter.preview(plan)
    assert preview["source_preserved"] and "script-fu" in preview["transport"].lower()
    assert run_conformance("gimp")["passed"]
    assert run_conformance("inkscape", native=True)["passed"]


def test_expansion_cli_surface(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    plan_path = write_plan(tmp_path, plan_payload(tmp_path))
    assert main(["normalize", str(plan_path)]) == 0
    assert json.loads(capsys.readouterr().out)["adapter"] == "inkscape"
    assert main(["conformance", "inkscape"]) == 0
    assert json.loads(capsys.readouterr().out)["passed"]

    private = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    assert main(["key", "generate", str(private), str(public)]) == 0
    assert json.loads(capsys.readouterr().out)["algorithm"] == "Ed25519"
    bundle = tmp_path / "signed.ccb.zip"
    assert (
        main(
            [
                "bundle",
                "create",
                str(plan_path),
                str(bundle),
                "--signing-key",
                str(private),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "bundle",
                "verify",
                str(bundle),
                "--public-key",
                str(public),
                "--require-signature",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["signature"]["verified"]
    unrelated_plan = write_plan(
        tmp_path, plan_payload(tmp_path, output="unrelated.svg"), "other.json"
    )
    assert (
        main(
            [
                "execute",
                str(unrelated_plan),
                "--bundle",
                str(bundle),
                "--public-key",
                str(public),
            ]
        )
        == 2
    )
    assert "does not match" in capsys.readouterr().err
    extracted = tmp_path / "extracted"
    assert (
        main(
            [
                "bundle",
                "extract",
                str(bundle),
                str(extracted),
                "--public-key",
                str(public),
                "--require-signature",
            ]
        )
        == 0
    )
    capsys.readouterr()

    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "policy_version": 1,
                "allowed_adapters": ["inkscape"],
                "allowed_capabilities": ["text.create"],
                "output_roots": [str(tmp_path)],
                "max_operations": 5,
            }
        ),
        encoding="utf-8",
    )
    assert main(["policy", "check", str(plan_path), str(policy_path)]) == 0
    capsys.readouterr()

    state = tmp_path / "state.json"
    receipt = tmp_path / "receipt.json"
    assert (
        main(
            [
                "execute",
                str(plan_path),
                "--only",
                "create-title",
                "--state",
                str(state),
                "--receipt",
                str(receipt),
                "--signing-key",
                str(private),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "verify-receipt",
                str(receipt),
                "--public-key",
                str(public),
                "--require-signature",
            ]
        )
        == 0
    )
    capsys.readouterr()
    separately_signed = tmp_path / "receipt-signed.json"
    unsigned = json.loads(receipt.read_text(encoding="utf-8"))
    unsigned.pop("signature")
    unsigned_path = tmp_path / "receipt-unsigned.json"
    unsigned_path.write_text(json.dumps(unsigned), encoding="utf-8")
    assert (
        main(
            [
                "sign-receipt",
                str(unsigned_path),
                str(separately_signed),
                "--private-key",
                str(private),
            ]
        )
        == 0
    )


def test_gimp_native_guards_and_subprocess(tmp_path: Path) -> None:
    payload = plan_payload(tmp_path, output="out.xcf")
    payload["adapter"] = "gimp"
    payload["operations"].extend(
        [
            {
                "capability": "text.update",
                "target": "title",
                "parameters": {
                    "content": "Updated",
                    "font_family": "Sans",
                    "font_size": 24,
                    "fill": "#123456",
                    "alignment": "center",
                },
            },
            {
                "capability": "transform.set",
                "target": "title",
                "parameters": {"scale_x": 2, "scale_y": 3, "rotation_degrees": 45},
            },
        ]
    )
    plan = parse_plan(payload)
    missing = GimpAdapter()
    missing.executable = None
    with pytest.raises(PlanError, match="not found"):
        missing.execute(plan)

    adapter = GimpAdapter("gimp")
    script = adapter.script(plan)
    assert "gimp-text-layer-set-color" in script
    assert "gimp-item-transform-rotate" in script
    with patch(
        "creative_capability_bridge.adapters.gimp.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, "GIMP 3.2", ""),
    ):
        assert adapter.application_version() == "GIMP 3.2"

    def successful_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        plan.output_path.write_bytes(b"xcf")
        return subprocess.CompletedProcess([], 0, "", "")

    with patch(
        "creative_capability_bridge.adapters.gimp.subprocess.run", side_effect=successful_run
    ):
        assert adapter.execute(plan) == plan.output_path
    with pytest.raises(PlanError, match="already exists"):
        adapter.execute(plan)

    plan.output_path.unlink()
    with (
        patch(
            "creative_capability_bridge.adapters.gimp.subprocess.run",
            return_value=subprocess.CompletedProcess([], 1, "", "failure"),
        ),
        pytest.raises(PlanError, match="GIMP failed"),
    ):
        adapter.execute(plan)


def test_xcf_inspection_through_mocked_native_process(tmp_path: Path) -> None:
    source = tmp_path / "source.xcf"
    source.write_bytes(b"mock-xcf")

    def command_with_fixture(_self: object, script: Path) -> list[str]:
        (script.parent / "layers.tsv").write_text("title\t100\t30\t12\t14\n", encoding="utf-8")
        return ["gimp"]

    with (
        patch.object(GimpAdapter, "_command", autospec=True, side_effect=command_with_fixture),
        patch(
            "creative_capability_bridge.inspection.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, "", ""),
        ),
    ):
        report = inspect_document(source, executable="gimp")
    assert report["format"] == "xcf"
    assert report["objects"][0] == {
        "id": "title",
        "type": "layer",
        "modifiable": True,
        "width": 100,
        "height": 30,
        "x": 12,
        "y": 14,
    }


def test_policy_pipeline_and_signing_error_edges(tmp_path: Path) -> None:
    invalid_policies = [
        {},
        {"policy_version": 1, "unknown": True},
        {"policy_version": 1, "allowed_adapters": ["paint"]},
        {"policy_version": 1, "allowed_capabilities": ["erase"]},
        {"policy_version": 1, "output_roots": "bad"},
        {"policy_version": 1, "max_operations": 0},
        {"policy_version": 1, "require_input": "yes"},
    ]
    for payload in invalid_policies:
        with pytest.raises(PlanError):
            validate_policy(payload)

    write_plan(tmp_path, plan_payload(tmp_path), "one.json")
    invalid_pipelines = [
        {},
        {"pipeline_version": 1, "steps": []},
        {"pipeline_version": 1, "steps": ["bad"]},
        {"pipeline_version": 1, "steps": [{"id": "a", "plan": "", "depends_on": []}]},
        {
            "pipeline_version": 1,
            "steps": [{"id": "a", "plan": "one.json", "depends_on": ["missing"]}],
        },
    ]
    for payload in invalid_pipelines:
        with pytest.raises(PlanError):
            validate_pipeline(payload, base_dir=tmp_path)

    private = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    generate_keypair(private, public)
    with pytest.raises(PlanError, match="already exists"):
        generate_keypair(private, public)
    other_private = tmp_path / "other-private.pem"
    other_public = tmp_path / "other-public.pem"
    generate_keypair(other_private, other_public)
    payload = {"message": "signed"}
    signature = sign_payload(payload, private)
    assert not verify_payload_signature(payload, signature, other_public)["verified"]
    assert not verify_payload_signature(payload, {}, public)["verified"]


def test_execution_selection_and_failure_edges(tmp_path: Path) -> None:
    plan = parse_plan(plan_payload(tmp_path))
    with pytest.raises(PlanError, match="Unknown"):
        select_operations(plan, from_operation="missing")
    with pytest.raises(PlanError, match="empty"):
        select_operations(plan, only={"missing"})
    with pytest.raises(PlanError, match="requires --state"):
        execute_checkpointed(plan, InkscapeAdapter(), resume=True)

    class FailingAdapter:
        executable = None

        def preview(self, _plan: object) -> dict[str, object]:
            return {"adapter": "failing"}

        def application_version(self) -> None:
            return None

        def execute(self, staged: object, *, replace: bool = False) -> Path:
            output = staged.output_path  # type: ignore[attr-defined]
            output.write_text("partial", encoding="utf-8")
            raise PlanError("forced failure")

    with pytest.raises(PlanError, match="forced failure"):
        execute_transactionally(plan, FailingAdapter())  # type: ignore[arg-type]
    assert not plan.output_path.exists()


def test_policy_reports_every_execution_boundary(tmp_path: Path) -> None:
    plan = parse_plan(plan_payload(tmp_path))
    policy = validate_policy(
        {
            "policy_version": 1,
            "name": "deny-all",
            "allowed_adapters": ["gimp"],
            "allowed_capabilities": ["text.update"],
            "output_roots": [str(tmp_path / "permitted")],
            "max_operations": 1,
            "require_input": True,
            "require_receipt": True,
            "require_inspection": True,
            "require_signed_bundle": True,
            "allow_replace": False,
        }
    )
    report = check_policy(plan, policy, replace=True)
    assert {item["code"] for item in report["violations"]} == {
        "adapter_denied",
        "capability_denied",
        "operation_limit",
        "input_required",
        "replace_denied",
        "receipt_required",
        "inspection_required",
        "signed_bundle_required",
        "output_root_denied",
    }
    with pytest.raises(PlanError, match="Policy rejected"):
        enforce_policy(plan, policy, replace=True)


def test_bundle_rejection_edges(tmp_path: Path) -> None:
    plan_path = write_plan(tmp_path, plan_payload(tmp_path))
    target = tmp_path / "bundle.zip"
    target.write_bytes(b"exists")
    with pytest.raises(PlanError, match="already exists"):
        create_bundle(plan_path, target)
    with pytest.raises(PlanError, match="does not exist"):
        create_bundle(plan_path, tmp_path / "missing.zip", assets=[tmp_path / "missing.txt"])

    first = tmp_path / "one" / "same.txt"
    second = tmp_path / "two" / "same.txt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    with pytest.raises(PlanError, match="Duplicate"):
        create_bundle(plan_path, tmp_path / "duplicate.zip", assets=[first, second])

    unsafe = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr("../escape", b"bad")
        archive.writestr("manifest.json", "{}")
    with pytest.raises(PlanError, match="unsafe"):
        verify_bundle(unsafe)


def test_coordinate_and_key_error_branches(tmp_path: Path) -> None:
    missing_extent = plan_payload(tmp_path, output="missing.xcf")
    missing_extent["adapter"] = "gimp"
    missing_extent["coordinate_space"] = {
        "unit": "px",
        "origin": "bottom-left",
        "y_axis": "up",
    }
    with pytest.raises(PlanError, match="width and height"):
        normalize_plan(parse_plan(missing_extent))

    blender = plan_payload(tmp_path, output="native.blend")
    blender["adapter"] = "blender"
    blender["coordinate_space"] = {
        "unit": "blender-unit",
        "origin": "center",
        "y_axis": "up",
        "width": 2,
        "height": 1,
    }
    normalized = normalize_plan(parse_plan(blender))
    assert normalized.operations[0].parameters["x"] == 10

    private = tmp_path / "bad-private.pem"
    public = tmp_path / "bad-public.pem"
    private.write_text("not a key", encoding="utf-8")
    public.write_text("not a key", encoding="utf-8")
    with pytest.raises(PlanError, match="private key"):
        sign_payload({"x": 1}, private)
    with pytest.raises(PlanError, match="public key"):
        verify_payload_signature(
            {"x": 1},
            {"signature_version": 1, "algorithm": "Ed25519", "value": "AA=="},
            public,
        )
    assert not verify_payload_signature(
        {"x": 1},
        {"signature_version": 1, "algorithm": "RSA", "value": "AA=="},
        public,
    )["verified"]
