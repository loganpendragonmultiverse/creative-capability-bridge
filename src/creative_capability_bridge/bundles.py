"""Portable, hash-verified CCB project bundles."""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .schema import PlanError, load_plan

BUNDLE_VERSION = 1


def create_bundle(
    plan_path: Path,
    destination: Path,
    *,
    assets: Iterable[Path] = (),
    license_notes: str | None = None,
    fallback_fonts: Iterable[str] = (),
) -> Path:
    load_plan(plan_path)
    target = destination.resolve()
    if target.exists():
        raise PlanError(f"Bundle already exists: {target}")
    files: list[tuple[str, bytes]] = [("plan.json", plan_path.read_bytes())]
    seen = {"plan.json", "manifest.json"}
    for asset in assets:
        source = asset.resolve()
        if not source.is_file():
            raise PlanError(f"Bundle asset does not exist: {source}")
        archive_name = f"assets/{source.name}"
        if archive_name in seen:
            raise PlanError(f"Duplicate bundle asset name: {source.name}")
        seen.add(archive_name)
        files.append((archive_name, source.read_bytes()))
    manifest = {
        "bundle_version": BUNDLE_VERSION,
        "plan": "plan.json",
        "files": [
            {"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            for name, data in files
        ],
        "license_notes": license_notes,
        "fallback_fonts": list(dict.fromkeys(fallback_fonts)),
        "path_policy": "archive-relative",
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files:
            archive.writestr(name, data)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
    return target


def verify_bundle(path: Path) -> dict[str, Any]:
    source = path.resolve()
    try:
        with zipfile.ZipFile(source) as archive:
            names = archive.namelist()
            if any(_unsafe_name(name) for name in names):
                raise PlanError("Bundle contains an unsafe path.")
            if len(names) != len(set(names)) or "manifest.json" not in names:
                raise PlanError("Bundle has duplicate entries or no manifest.json.")
            manifest = json.loads(archive.read("manifest.json"))
            if not isinstance(manifest, dict):
                raise PlanError("Bundle manifest must be a JSON object.")
            if manifest.get("bundle_version") != BUNDLE_VERSION:
                raise PlanError("Bundle version is not supported.")
            checked = []
            for item in manifest.get("files", []):
                if not isinstance(item, dict):
                    raise PlanError("Bundle manifest file entries must be objects.")
                name = item.get("path")
                if not isinstance(name, str) or name not in names or _unsafe_name(name):
                    raise PlanError(f"Manifest references an invalid file: {name!r}")
                data = archive.read(name)
                valid = hashlib.sha256(data).hexdigest() == item.get("sha256") and len(
                    data
                ) == item.get("bytes")
                checked.append({"path": name, "valid": valid})
            declared = {item["path"] for item in manifest.get("files", [])}
            valid = (
                bool(checked)
                and all(item["valid"] for item in checked)
                and manifest.get("plan") in names
                and declared == set(names) - {"manifest.json"}
            )
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        raise PlanError(f"Could not verify bundle: {exc}") from exc
    return {"bundle": str(source), "valid": valid, "files": checked, "manifest": manifest}


def extract_bundle(path: Path, destination: Path) -> Path:
    report = verify_bundle(path)
    if not report["valid"]:
        raise PlanError("Bundle failed verification and was not extracted.")
    target = destination.resolve()
    if target.exists():
        raise PlanError(f"Extraction destination already exists: {target}")
    target.mkdir(parents=True)
    try:
        with zipfile.ZipFile(path.resolve()) as archive:
            names = ["manifest.json", *(item["path"] for item in report["manifest"]["files"])]
            for name in names:
                output = target / Path(name.replace("\\", "/"))
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(archive.read(name))
    except (OSError, KeyError, zipfile.BadZipFile):
        # The destination was newly created for this operation and contains only extraction output.
        for item in sorted(target.rglob("*"), key=lambda value: len(value.parts), reverse=True):
            if item.is_file():
                item.unlink()
            else:
                item.rmdir()
        target.rmdir()
        raise
    return target


def _unsafe_name(name: str) -> bool:
    candidate = Path(name.replace("\\", "/"))
    return candidate.is_absolute() or ".." in candidate.parts or ":" in name
