"""Command-line interface for portable creative operations."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .adapters import BlenderAdapter, GimpAdapter, InkscapeAdapter
from .bundles import create_bundle, extract_bundle, verify_bundle
from .capabilities import all_manifests, manifest
from .conformance import run_conformance
from .coordinates import coordinate_report
from .document_diff import compare_documents
from .execution import ExecutableAdapter, execute_checkpointed, execute_transactionally
from .explain import explain_plan
from .inspection import inspect_document
from .linting import lint_plan
from .negotiation import compatibility, retarget
from .pipelines import execute_pipeline, load_pipeline
from .policies import check_policy, enforce_policy, load_policy
from .receipts import (
    build_receipt,
    compare_receipts,
    sign_receipt,
    verify_receipt,
    write_receipt,
)
from .schema import ADAPTERS, Plan, PlanError, load_plan
from .signing import generate_keypair, sign_payload


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="creative-capability-bridge")
    subcommands = root.add_subparsers(dest="command", required=True)
    capabilities = subcommands.add_parser("capabilities", help="Show adapter capability manifests.")
    capabilities.add_argument("adapter", choices=ADAPTERS, nargs="?")
    capabilities.add_argument("--json", action="store_true")
    validate = subcommands.add_parser("validate", help="Validate a plan without executing it.")
    validate.add_argument("plan", type=Path)
    explain = subcommands.add_parser("explain", help="Explain a plan's file and target effects.")
    explain.add_argument("plan", type=Path)
    explain.add_argument("--replace", action="store_true")
    lint = subcommands.add_parser("lint", help="Check target flow beyond schema validation.")
    lint.add_argument("plan", type=Path)
    lint.add_argument("--document", type=Path, help="Inspect a document for existing targets.")
    lint.add_argument("--executable", help="Native application executable path.")
    inspect = subcommands.add_parser("inspect", help="Read document targets without modifying it.")
    inspect.add_argument("document", type=Path)
    inspect.add_argument("--executable", help="Native application executable path.")
    diff = subcommands.add_parser("diff", help="Compare document structure and properties.")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    diff.add_argument("--before-executable")
    diff.add_argument("--after-executable")
    normalize = subcommands.add_parser("normalize", help="Show adapter-native coordinates.")
    normalize.add_argument("plan", type=Path)
    compatible = subcommands.add_parser(
        "compatibility", help="Report exact, approximate, and unsupported adapters."
    )
    compatible.add_argument("plan", type=Path)
    retarget_parser = subcommands.add_parser(
        "retarget", help="Write a concrete plan for one compatible adapter."
    )
    retarget_parser.add_argument("plan", type=Path)
    retarget_parser.add_argument("--adapter", choices=ADAPTERS, required=True)
    retarget_parser.add_argument("--output", type=Path, required=True)
    conformance = subcommands.add_parser(
        "conformance", help="Run adapter manifest and optional native fixture checks."
    )
    conformance.add_argument("adapter", choices=ADAPTERS)
    conformance.add_argument("--executable")
    conformance.add_argument("--native", action="store_true")

    compare = subcommands.add_parser("compare-receipts", help="Compare two execution receipts.")
    compare.add_argument("left", type=Path)
    compare.add_argument("right", type=Path)
    receipt_verify = subcommands.add_parser(
        "verify-receipt", help="Verify receipt files and optional Ed25519 signature."
    )
    receipt_verify.add_argument("receipt", type=Path)
    receipt_verify.add_argument("--public-key", type=Path)
    receipt_verify.add_argument("--require-signature", action="store_true")
    receipt_sign = subcommands.add_parser("sign-receipt", help="Sign an execution receipt.")
    receipt_sign.add_argument("receipt", type=Path)
    receipt_sign.add_argument("output", type=Path)
    receipt_sign.add_argument("--private-key", type=Path, required=True)
    key = subcommands.add_parser("key", help="Manage artifact-signing keys.")
    key_commands = key.add_subparsers(dest="key_command", required=True)
    key_generate = key_commands.add_parser("generate", help="Generate an Ed25519 key pair.")
    key_generate.add_argument("private_key", type=Path)
    key_generate.add_argument("public_key", type=Path)

    bundle = subcommands.add_parser("bundle", help="Create, verify, or extract project bundles.")
    bundle_commands = bundle.add_subparsers(dest="bundle_command", required=True)
    bundle_create = bundle_commands.add_parser("create", help="Create a verified .ccb.zip bundle.")
    bundle_create.add_argument("plan", type=Path)
    bundle_create.add_argument("output", type=Path)
    bundle_create.add_argument("--asset", action="append", type=Path, default=[])
    bundle_create.add_argument("--license-note")
    bundle_create.add_argument("--fallback-font", action="append", default=[])
    bundle_create.add_argument("--signing-key", type=Path)
    bundle_verify = bundle_commands.add_parser("verify", help="Verify bundle files and signature.")
    bundle_verify.add_argument("bundle", type=Path)
    bundle_verify.add_argument("--public-key", type=Path)
    bundle_verify.add_argument("--require-signature", action="store_true")
    bundle_extract = bundle_commands.add_parser(
        "extract", help="Verify and safely extract a bundle."
    )
    bundle_extract.add_argument("bundle", type=Path)
    bundle_extract.add_argument("destination", type=Path)
    bundle_extract.add_argument("--public-key", type=Path)
    bundle_extract.add_argument("--require-signature", action="store_true")

    policy = subcommands.add_parser("policy", help="Validate execution against a policy profile.")
    policy_commands = policy.add_subparsers(dest="policy_command", required=True)
    policy_check = policy_commands.add_parser("check", help="Check a plan against a policy.")
    policy_check.add_argument("plan", type=Path)
    policy_check.add_argument("policy", type=Path)
    policy_check.add_argument("--replace", action="store_true")
    policy_check.add_argument("--receipt", type=Path)
    policy_check.add_argument("--inspected", action="store_true")
    policy_check.add_argument("--signed-bundle", action="store_true")

    pipeline = subcommands.add_parser("pipeline", help="Validate or execute multi-document work.")
    pipeline_commands = pipeline.add_subparsers(dest="pipeline_command", required=True)
    pipeline_validate = pipeline_commands.add_parser("validate", help="Validate a pipeline DAG.")
    pipeline_validate.add_argument("pipeline", type=Path)
    pipeline_execute = pipeline_commands.add_parser("execute", help="Execute a pipeline in order.")
    pipeline_execute.add_argument("pipeline", type=Path)
    pipeline_execute.add_argument("--executable")
    pipeline_execute.add_argument("--policy", type=Path)
    pipeline_execute.add_argument("--receipt-dir", type=Path)
    pipeline_execute.add_argument("--replace", action="store_true")

    preview = subcommands.add_parser("preview", help="Show execution without changing files.")
    preview.add_argument("plan", type=Path)
    preview.add_argument("--executable")
    execute = subcommands.add_parser("execute", help="Execute a plan transactionally.")
    execute.add_argument("plan", type=Path)
    execute.add_argument("--replace", action="store_true")
    execute.add_argument("--backup", type=Path)
    execute.add_argument("--receipt", type=Path)
    execute.add_argument("--signing-key", type=Path)
    execute.add_argument("--executable")
    execute.add_argument("--render-preview", type=Path)
    execute.add_argument("--only", action="append", default=[])
    execute.add_argument("--skip", action="append", default=[])
    execute.add_argument("--from", dest="from_operation")
    execute.add_argument("--state", type=Path)
    execute.add_argument("--resume", action="store_true")
    execute.add_argument("--policy", type=Path)
    execute.add_argument("--bundle", type=Path)
    execute.add_argument("--public-key", type=Path)
    subcommands.add_parser("doctor", help="Report native application availability.")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = _dispatch(args)
        return result
    except PlanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "capabilities":
        payload = manifest(args.adapter) if args.adapter else all_manifests()
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            entries = payload if isinstance(payload, list) else [payload]
            for entry in entries:
                print(f"{entry['application']}: {', '.join(entry['operations'])}")
        return 0
    if args.command == "doctor":
        report = {
            "blender": shutil.which("blender"),
            "inkscape": shutil.which("inkscape"),
            "gimp": GimpAdapter().executable,
        }
        print(json.dumps(report, indent=2))
        return 0 if all(report.values()) else 1
    if args.command == "inspect":
        _print(inspect_document(args.document, executable=args.executable))
        return 0
    if args.command == "diff":
        report = compare_documents(
            args.before,
            args.after,
            before_executable=args.before_executable,
            after_executable=args.after_executable,
        )
        _print(report)
        return 0 if report["equivalent"] else 1
    if args.command == "compatibility":
        _print(compatibility(args.plan))
        return 0
    if args.command == "retarget":
        print(retarget(args.plan, args.adapter, args.output))
        return 0
    if args.command == "conformance":
        report = run_conformance(args.adapter, executable=args.executable, native=args.native)
        _print(report)
        return 0 if report["passed"] else 1
    if args.command == "compare-receipts":
        _print(compare_receipts(args.left, args.right))
        return 0
    if args.command == "verify-receipt":
        report = verify_receipt(
            args.receipt, public_key=args.public_key, require_signature=args.require_signature
        )
        _print(report)
        return 0 if report["verified"] else 1
    if args.command == "sign-receipt":
        print(sign_receipt(args.receipt, args.output, args.private_key))
        return 0
    if args.command == "key":
        private, public = generate_keypair(args.private_key, args.public_key)
        _print({"private_key": str(private), "public_key": str(public), "algorithm": "Ed25519"})
        return 0
    if args.command == "bundle":
        return _bundle(args)
    if args.command == "policy":
        plan = load_plan(args.plan)
        report = check_policy(
            plan,
            load_policy(args.policy),
            replace=args.replace,
            receipt=args.receipt,
            inspected=args.inspected,
            signed_bundle=args.signed_bundle,
        )
        _print(report)
        return 0 if report["valid"] else 1
    if args.command == "pipeline":
        if args.pipeline_command == "validate":
            _print(load_pipeline(args.pipeline))
        else:
            _print(
                execute_pipeline(
                    args.pipeline,
                    _adapter,
                    executable=args.executable,
                    policy_path=args.policy,
                    receipt_dir=args.receipt_dir,
                    replace=args.replace,
                )
            )
        return 0

    plan = load_plan(args.plan)
    if args.command == "validate":
        print(f"Valid v{plan.version} plan for {plan.adapter}: {len(plan.operations)} operations")
        return 0
    if args.command == "explain":
        _print(explain_plan(plan, replace=args.replace))
        return 0
    if args.command == "lint":
        report = lint_plan(plan, document=args.document, executable=args.executable)
        _print(report)
        return 0 if report["valid"] else 1
    if args.command == "normalize":
        _print(coordinate_report(plan))
        return 0
    adapter = _adapter(plan.adapter, args.executable)
    if args.command == "preview":
        _print(adapter.preview(plan))
        return 0
    return _execute(args, plan, adapter)


def _bundle(args: argparse.Namespace) -> int:
    if args.bundle_command == "create":
        print(
            create_bundle(
                args.plan,
                args.output,
                assets=args.asset,
                license_notes=args.license_note,
                fallback_fonts=args.fallback_font,
                signing_key=args.signing_key,
            )
        )
        return 0
    if args.bundle_command == "verify":
        report = verify_bundle(
            args.bundle, public_key=args.public_key, require_signature=args.require_signature
        )
        _print(report)
        return 0 if report["valid"] else 2
    print(
        extract_bundle(
            args.bundle,
            args.destination,
            public_key=args.public_key,
            require_signature=args.require_signature,
        )
    )
    return 0


def _execute(args: argparse.Namespace, plan: Plan, adapter: ExecutableAdapter) -> int:
    if args.render_preview and plan.adapter != "inkscape":
        raise PlanError("--render-preview is only supported by the Inkscape adapter.")
    signed_bundle = False
    if args.bundle:
        report = verify_bundle(
            args.bundle, public_key=args.public_key, require_signature=args.public_key is not None
        )
        signed_bundle = report["valid"] and report["signature"].get("verified") is True
        if not report["valid"]:
            raise PlanError("Execution bundle verification failed.")
        plan_name = report["manifest"].get("plan")
        plan_record = next(
            (item for item in report["manifest"].get("files", []) if item.get("path") == plan_name),
            None,
        )
        if not plan_record or hashlib.sha256(args.plan.read_bytes()).hexdigest() != plan_record.get(
            "sha256"
        ):
            raise PlanError("Execution plan does not match the verified bundle plan.")
    inspected = False
    policy = load_policy(args.policy) if args.policy else None
    if policy and policy["require_inspection"] and plan.input_path:
        inspect_document(plan.input_path, executable=args.executable)
        inspected = True
    if policy:
        enforce_policy(
            plan,
            policy,
            replace=args.replace,
            receipt=args.receipt,
            inspected=inspected,
            signed_bundle=signed_bundle,
        )
    started = time.monotonic()
    checkpointed = bool(args.only or args.skip or args.from_operation or args.state or args.resume)
    if checkpointed:
        result = execute_checkpointed(
            plan,
            adapter,
            only=set(args.only) or None,
            skip=set(args.skip) or None,
            from_operation=args.from_operation,
            state_path=args.state,
            resume=args.resume,
            replace_output=args.replace,
            backup_path=args.backup,
        )
    else:
        result = execute_transactionally(
            plan,
            adapter,
            replace_output=args.replace,
            backup_path=args.backup,
        )
    if args.render_preview:
        assert isinstance(adapter, InkscapeAdapter)
        adapter._render(result.output, args.render_preview)
    _print(
        {
            "output": str(result.output),
            "backup": str(result.backup) if result.backup else None,
            "completed": list(result.completed),
            "state": str(result.state) if result.state else None,
        }
    )
    if args.receipt:
        receipt = build_receipt(
            result.executed_plan,
            started=started,
            application_version=_application_version(adapter),
        )
        if args.signing_key:
            receipt["signature"] = sign_payload(receipt, args.signing_key)
        print(write_receipt(args.receipt, receipt))
    return 0


def _adapter(name: str, executable: str | None) -> ExecutableAdapter:
    if name == "blender":
        return BlenderAdapter(executable)
    if name == "inkscape":
        return InkscapeAdapter(executable)
    return GimpAdapter(executable)


def _application_version(adapter: ExecutableAdapter) -> str | None:
    method = getattr(adapter, "application_version", None)
    return method() if callable(method) else None


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
