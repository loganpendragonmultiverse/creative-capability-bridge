"""Command-line interface for validating and executing capability plans."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Sequence

from .adapters import BlenderAdapter, InkscapeAdapter
from .capabilities import all_manifests, manifest
from .schema import ADAPTERS, PlanError, load_plan


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="creative-capability-bridge")
    subcommands = root.add_subparsers(dest="command", required=True)
    capabilities = subcommands.add_parser("capabilities", help="Show adapter capability manifests.")
    capabilities.add_argument("adapter", choices=ADAPTERS, nargs="?")
    capabilities.add_argument("--json", action="store_true")
    validate = subcommands.add_parser("validate", help="Validate a plan without executing it.")
    validate.add_argument("plan", type=Path)
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
        plan = load_plan(args.plan)
        if args.command == "validate":
            print(
                f"Valid v{plan.version} plan for {plan.adapter}: {len(plan.operations)} operations"
            )
            return 0
        adapter = _adapter(plan.adapter, args.executable)
        if args.command == "preview":
            print(json.dumps(adapter.preview(plan), indent=2))
            return 0
        if plan.adapter == "blender" and args.render_preview:
            raise PlanError("--render-preview is only supported by the Inkscape adapter.")
        if isinstance(adapter, InkscapeAdapter):
            output = adapter.execute(plan, replace=args.replace, render_preview=args.render_preview)
        else:
            output = adapter.execute(plan, replace=args.replace)
        print(output)
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
