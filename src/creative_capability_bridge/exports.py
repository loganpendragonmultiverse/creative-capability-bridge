"""Separate, bounded SVG-to-PNG export contract; native document plans stay version 1."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .schema import PlanError

SVG = "http://www.w3.org/2000/svg"
TAGS = {
    "svg",
    "g",
    "defs",
    "rect",
    "circle",
    "ellipse",
    "line",
    "polyline",
    "polygon",
    "path",
    "text",
    "tspan",
    "linearGradient",
    "radialGradient",
    "stop",
    "clipPath",
}
ATTRS = {
    "id",
    "width",
    "height",
    "viewBox",
    "preserveAspectRatio",
    "x",
    "y",
    "x1",
    "y1",
    "x2",
    "y2",
    "cx",
    "cy",
    "r",
    "rx",
    "ry",
    "d",
    "points",
    "transform",
    "fill",
    "fill-opacity",
    "fill-rule",
    "stroke",
    "stroke-width",
    "stroke-opacity",
    "stroke-linecap",
    "stroke-linejoin",
    "opacity",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "text-anchor",
    "dx",
    "dy",
    "offset",
    "stop-color",
    "stop-opacity",
    "gradientUnits",
    "gradientTransform",
    "clip-path",
    "clipPathUnits",
    "data-ccb-id",
}


@dataclass(frozen=True)
class ExportJob:
    source: Path
    output: Path
    receipt: Path
    width: int
    height: int


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PlanError("Duplicate export-job key.")
        result[key] = value
    return result


def load_export_job(path: Path) -> ExportJob:
    try:
        if path.stat().st_size > 64_000:
            raise PlanError("Export job exceeds 64 KB.")
        raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
        if not isinstance(raw, dict) or set(raw) != {
            "export_version",
            "format",
            "source",
            "output",
            "receipt",
            "width",
            "height",
        }:
            raise PlanError(
                "Expected exact version, format, source, output, receipt and dimensions."
            )
        if (
            type(raw["export_version"]) is not int
            or raw["export_version"] != 1
            or raw["format"] != "png"
        ):
            raise PlanError("Only export_version 1 with PNG format is supported.")
        if (
            any(type(raw[k]) is not int or not 1 <= raw[k] <= 8192 for k in ("width", "height"))
            or raw["width"] * raw["height"] > 16_000_000
        ):
            raise PlanError(
                "Export dimensions exceed the 8192-per-side or 16-million-pixel bounds."
            )
        if any(
            not isinstance(raw[k], str) or not raw[k].strip()
            for k in ("source", "output", "receipt")
        ):
            raise PlanError("Export paths must be non-empty text.")
        base = path.resolve().parent
        source = (base / raw["source"]).resolve()
        # Keep destination names intact: resolving a final dangling symlink would
        # hide the occupied name from preflight and redirect publication.
        output, receipt = (
            (base / raw[k]).parent.resolve() / (base / raw[k]).name for k in ("output", "receipt")
        )
        if len({source, output, receipt, path.resolve()}) != 4:
            raise PlanError("Source, output, receipt and job must be distinct paths.")
        if (
            source.suffix.lower() != ".svg"
            or output.suffix.lower() != ".png"
            or receipt.suffix.lower() != ".json"
        ):
            raise PlanError("Export requires SVG source, PNG output and JSON receipt suffixes.")
        return ExportJob(source, output, receipt, raw["width"], raw["height"])
    except (OSError, ValueError, UnicodeError) as exc:
        raise PlanError("Could not read a valid export job.") from exc


def _svg(job: ExportJob) -> bytes:
    try:
        if not job.source.is_file() or job.source.stat().st_size > 4_000_000:
            raise PlanError("SVG source is missing or exceeds 4 MB.")
        raw = job.source.read_bytes()
        raw.decode("utf-8-sig")
        if b"\0" in raw:
            raise PlanError("NUL bytes and UTF-16 SVG are unsupported.")
    except (OSError, UnicodeError) as exc:
        raise PlanError("Could not read UTF-8 SVG source.") from exc
    if re.search(rb"<!\s*(?:DOCTYPE|ENTITY)", raw, re.IGNORECASE):
        raise PlanError("SVG declarations and entities are unsupported.")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise PlanError("SVG source could not be parsed.") from exc
    if root.tag != "{" + SVG + "}svg":
        raise PlanError("Source must be an SVG document.")
    for element in root.iter():
        if element.tag not in {"{" + SVG + "}" + tag for tag in TAGS}:
            raise PlanError(
                "Unsupported SVG element; export accepts the documented static subset only."
            )
        for key, value in element.attrib.items():
            if key not in ATTRS:
                raise PlanError(
                    "Unsupported SVG attribute; external resources, CSS and events are refused."
                )
            if re.search(r"url\s*\(", value, re.IGNORECASE) and not re.fullmatch(
                r"url\(#[A-Za-z_][A-Za-z0-9_.:-]*\)", value
            ):
                raise PlanError("Only local SVG fragment references are supported.")
    return raw


def export_preflight(job: ExportJob, executable: str | None = None) -> dict[str, Any]:
    if len({job.source.resolve(), job.output.resolve(), job.receipt.resolve()}) != 3:
        raise PlanError("Export source, output and receipt must differ.")
    if (
        any(type(v) is not int or not 1 <= v <= 8192 for v in (job.width, job.height))
        or job.width * job.height > 16_000_000
    ):
        raise PlanError("Export dimensions are outside the supported bounds.")
    if (
        job.source.suffix.lower() != ".svg"
        or job.output.suffix.lower() != ".png"
        or job.receipt.suffix.lower() != ".json"
    ):
        raise PlanError("Unsupported export filename suffix.")
    _svg(job)
    for target in (job.output, job.receipt):
        if target.exists() or target.is_symlink() or not target.parent.is_dir():
            raise PlanError("Output and receipt need existing parents and new destinations.")
    native = executable or shutil.which("inkscape")
    return {
        "export_version": 1,
        "format": "png",
        "ready": bool(native),
        "width": job.width,
        "height": job.height,
        "source_preserved": True,
        "native_required": "inkscape",
        "subset": "static SVG without external resources, CSS, scripts or images",
    }


def _verify_png(path: Path, width: int, height: int) -> str:
    if not path.is_file() or path.stat().st_size > 32_000_000:
        raise PlanError("Native export did not produce a bounded PNG.")
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise PlanError("Native output is not PNG.")
    offset = 8
    seen_data = False
    seen_header = False
    while offset + 12 <= len(raw):
        length = struct.unpack(">I", raw[offset : offset + 4])[0]
        kind = raw[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(raw):
            raise PlanError("PNG is truncated.")
        data = raw[offset + 8 : offset + 8 + length]
        crc = struct.unpack(">I", raw[end - 4 : end])[0]
        if zlib.crc32(kind + data) & 0xFFFFFFFF != crc:
            raise PlanError("PNG checksum is invalid.")
        if not seen_header:
            if kind != b"IHDR" or length != 13 or struct.unpack(">II", data[:8]) != (width, height):
                raise PlanError("PNG dimensions do not match the export job.")
            seen_header = True
        if kind == b"IDAT":
            seen_data = True
        if kind == b"IEND":
            if length != 0 or not seen_data or end != len(raw):
                raise PlanError("PNG end marker is invalid.")
            return hashlib.sha256(raw).hexdigest()
        offset = end
    raise PlanError("PNG end marker is missing.")


def execute_export(job: ExportJob, executable: str | None = None) -> dict[str, Any]:
    export_preflight(job, executable)
    native = executable or shutil.which("inkscape")
    if not native:
        raise PlanError("Inkscape executable is required for PNG export.")
    raw = _svg(job)
    source_hash = hashlib.sha256(raw).hexdigest()
    try:
        with tempfile.TemporaryDirectory(prefix=".ccb-export-", dir=job.output.parent) as directory:
            stage = Path(directory)
            snapshot, png, receipt = (
                stage / "input.svg",
                stage / "output.png",
                stage / "receipt.json",
            )
            root = ET.fromstring(raw)
            root.set("width", str(job.width))
            root.set("height", str(job.height))
            snapshot.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
            result = subprocess.run(
                [
                    native,
                    str(snapshot),
                    "--export-type=png",
                    "--export-area-page",
                    f"--export-width={job.width}",
                    f"--export-height={job.height}",
                    f"--export-filename={png}",
                ],
                capture_output=True,
                timeout=120,
                check=False,
            )
            if result.returncode:
                raise PlanError("Native PNG export failed; no output was published.")
            digest = _verify_png(png, job.width, job.height)
            if hashlib.sha256(job.source.read_bytes()).hexdigest() != source_hash:
                raise PlanError("Source changed during export; no output was published.")
            payload = {
                "receipt_version": 1,
                "receipt_kind": "svg-png-export",
                "export_version": 1,
                "status": "completed",
                "ccb_version": __version__,
                "adapter": "inkscape",
                "input": {"path": str(job.source), "sha256": source_hash},
                "output": {"path": str(job.output), "sha256": digest},
                "width": job.width,
                "height": job.height,
                "operations": [],
                "warnings": [
                    "Static SVG subset; system fonts and native renderer affect visual fidelity."
                ],
            }
            receipt.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            output_linked = False
            try:
                # Hard links atomically refuse existing destinations, including races.
                os.link(png, job.output)
                output_linked = True
                os.link(receipt, job.receipt)
            except OSError:
                if output_linked and job.output.exists() and job.output.samefile(png):
                    job.output.unlink()
                raise
            return payload
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PlanError("Export failed; existing destinations were preserved.") from exc
