"""Command-line interface for validating and executing capability plans."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from .adapters import BlenderAdapter, InkscapeAdapter
from .bundles import create_bundle, extract_bundle, verify_bundle
from .capabilities import all_manifests, manifest
from .explain import explain_plan
from .inspection import inspect_document
from .linting import lint_plan
from .negotiation import compatibility, retarget
from .receipts import build_receipt, compare_receipts, verify_receipt, write_receipt
from .schema import ADAPTERS, PlanError, load_plan


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
    lint.add_argument(
        "--document", type=Path, help="Inspect a document to confirm existing targets."
    )
    lint.add_argument("--executable", help="Blender executable path for .blend inspection.")
    inspect = subcommands.add_parser("inspect", help="Read document targets without modifying it.")
    inspect.add_argument("document", type=Path)
    inspect.add_argument("--executable", help="Blender executable path for .blend inspection.")
    compatible = subcommands.add_parser(
        "compatibility", help="Report exact, approximate, and unsupported adapters."
    )
    compatible.add_argument("plan", type=Path)
    retarget_parser = subcommands.add_parser(
        "retarget", help="Write a concrete plan for one compatible adapter."
    )
    retarget_parser.add_argument("plan", type=Path)
    retarget_parser.add_argument("--adapter", choices=ADAPTERS, required=True)
    retarget_parser.add_argument(
        "--output", type=Path, required=True, help="Destination JSON plan."
    )
    compare = subcommands.add_parser("compare-receipts", help="Compare two execution receipts.")
    compare.add_argument("left", type=Path)
    compare.add_argument("right", type=Path)
    receipt_verify = subcommands.add_parser(
        "verify-receipt", help="Re-hash receipt files and report drift or missing files."
    )
    receipt_verify.add_argument("receipt", type=Path)
    bundle = subcommands.add_parser("bundle", help="Create or verify portable project bundles.")
    bundle_commands = bundle.add_subparsers(dest="bundle_command", required=True)
    bundle_create = bundle_commands.add_parser(
        "create", help="Create a hash-verified .ccb.zip bundle."
    )
    bundle_create.add_argument("plan", type=Path)
    bundle_create.add_argument("output", type=Path)
    bundle_create.add_argument("--asset", action="append", type=Path, default=[])
    bundle_create.add_argument("--license-note")
    bundle_create.add_argument("--fallback-font", action="append", default=[])
    bundle_verify = bundle_commands.add_parser(
        "verify", help="Verify bundle paths and file hashes."
    )
    bundle_verify.add_argument("bundle", type=Path)
    bundle_extract = bundle_commands.add_parser(
        "extract", help="Verify and extract a bundle into a new directory."
    )
    bundle_extract.add_argument("bundle", type=Path)
    bundle_extract.add_argument("destination", type=Path)
    preview = subcommands.add_parser(
        "preview", help="Show the execution boundary without changing files."
    )
    preview.add_argument("plan", type=Path)
    preview.add_argument("--executable")
    execute = subcommands.add_parser(
        "execute", help="Execute a validated plan into a new output file."
    )
    execute.add_argument("plan", type=Path)
    execute.add_argument(
        "--replace", action="store_true", help="Allow replacement of the output only."
    )
    execute.add_argument(
        "--receipt", type=Path, help="Write a JSON execution receipt after success."
    )
    execute.add_argument("--executable", help="Application executable path.")
    execute.add_argument(
        "--render-preview", type=Path, help="Inkscape only: render the SVG through Inkscape."
    )
    subcommands.add_parser("doctor", help="Report native application availability.")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
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
            report = {name: shutil.which(name) for name in ADAPTERS}
            print(json.dumps(report, indent=2))
            return 0 if all(report.values()) else 1
        if args.command == "inspect":
            print(json.dumps(inspect_document(args.document, executable=args.executable), indent=2))
            return 0
        if args.command == "compatibility":
            print(json.dumps(compatibility(args.plan), indent=2))
            return 0
        if args.command == "retarget":
            print(retarget(args.plan, args.adapter, args.output))
            return 0
        if args.command == "compare-receipts":
            print(json.dumps(compare_receipts(args.left, args.right), indent=2))
            return 0
        if args.command == "verify-receipt":
            report = verify_receipt(args.receipt)
            print(json.dumps(report, indent=2))
            return 0 if report["verified"] else 1
        if args.command == "bundle":
            if args.bundle_command == "create":
                print(
                    create_bundle(
                        args.plan,
                        args.output,
                        assets=args.asset,
                        license_notes=args.license_note,
                        fallback_fonts=args.fallback_font,
                    )
                )
            elif args.bundle_command == "verify":
                report = verify_bundle(args.bundle)
                print(json.dumps(report, indent=2))
                if not report["valid"]:
                    return 2
            else:
                print(extract_bundle(args.bundle, args.destination))
            return 0
        plan = load_plan(args.plan)
        if args.command == "validate":
            print(
                f"Valid v{plan.version} plan for {plan.adapter}: {len(plan.operations)} operations"
            )
            return 0
        if args.command == "explain":
            print(json.dumps(explain_plan(plan, replace=args.replace), indent=2))
            return 0
        if args.command == "lint":
            report = lint_plan(plan, document=args.document, executable=args.executable)
            print(json.dumps(report, indent=2))
            return 0 if report["valid"] else 1
        adapter = _adapter(plan.adapter, args.executable)
        if args.command == "preview":
            print(json.dumps(adapter.preview(plan), indent=2))
            return 0
        if plan.adapter == "blender" and args.render_preview:
            raise PlanError("--render-preview is only supported by the Inkscape adapter.")
        started = time.monotonic()
        if isinstance(adapter, InkscapeAdapter):
            output = adapter.execute(plan, replace=args.replace, render_preview=args.render_preview)
        else:
            output = adapter.execute(plan, replace=args.replace)
        print(output)
        if args.receipt:
            receipt = build_receipt(
                plan, started=started, application_version=adapter.application_version()
            )
            print(write_receipt(args.receipt, receipt))
        return 0
    except PlanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _adapter(name: str, executable: str | None) -> BlenderAdapter | InkscapeAdapter:
    if name == "blender":
        return BlenderAdapter(executable)
    return InkscapeAdapter(executable)


if __name__ == "__main__":
    raise SystemExit(main())
