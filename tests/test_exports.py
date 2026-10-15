from __future__ import annotations

import json
import struct
import subprocess
import zlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from creative_capability_bridge.cli import main
from creative_capability_bridge.exports import (
    ExportJob,
    _verify_png,
    execute_export,
    export_preflight,
    load_export_job,
)
from creative_capability_bridge.schema import PlanError

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><rect width="8" height="8" fill="#123456"/></svg>'


def png(width: int = 8, height: int = 8) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\0" + b"\x12\x34\x56\xff" * width) * height))
        + chunk(b"IEND", b"")
    )


def fixture(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    (tmp_path / "in.svg").write_text(SVG, encoding="utf-8")
    payload = {
        "export_version": 1,
        "format": "png",
        "source": "in.svg",
        "output": "out.png",
        "receipt": "receipt.json",
        "width": 8,
        "height": 8,
    }
    path = tmp_path / "job.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, payload


def fake_renderer(args: list[str], **kwargs: Any) -> SimpleNamespace:
    Path(next(a.split("=", 1)[1] for a in args if a.startswith("--export-filename="))).write_bytes(
        png()
    )
    assert kwargs["timeout"] == 120 and kwargs["check"] is False
    assert "--export-type=png" in args
    return SimpleNamespace(returncode=0)


def test_export_preflight_execution_and_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _ = fixture(tmp_path)
    job = load_export_job(path)
    original = job.source.read_bytes()
    assert export_preflight(job, "fake")["ready"]
    assert not job.output.exists() and not job.receipt.exists()
    monkeypatch.setattr("creative_capability_bridge.exports.subprocess.run", fake_renderer)
    assert main(["export", str(path), "--preflight", "--executable", "fake"]) == 0
    assert main(["export", str(path), "--executable", "fake"]) == 0
    receipt = json.loads(job.receipt.read_text())
    assert receipt["receipt_kind"] == "svg-png-export"
    assert receipt["input"]["sha256"] and receipt["output"]["sha256"]
    assert job.source.read_bytes() == original
    assert main(["export", str(path), "--executable", "fake"]) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"export_version": True},
        {"export_version": 2},
        {"format": "pdf"},
        {"width": True},
        {"width": 0},
        {"width": 8193},
        {"width": 8192, "height": 8192},
        {"source": 4},
        {"output": "in.svg"},
        {"receipt": "job.json"},
        {"output": "out.jpg"},
        {"extra": "unknown"},
    ],
)
def test_invalid_jobs(tmp_path: Path, changes: dict[str, Any]) -> None:
    path, payload = fixture(tmp_path)
    payload.update(changes)
    path.write_text(json.dumps(payload))
    with pytest.raises(PlanError):
        load_export_job(path)


@pytest.mark.parametrize(
    "raw", ["[]", "{}", "not JSON", '{"format":"png","format":"pdf"}', " " * 64001]
)
def test_malformed_jobs(tmp_path: Path, raw: str) -> None:
    path = tmp_path / "job.json"
    path.write_text(raw)
    with pytest.raises(PlanError):
        load_export_job(path)


@pytest.mark.parametrize(
    "content",
    [
        '<!DOCTYPE svg [<!ENTITY x "expanded">]><svg xmlns="http://www.w3.org/2000/svg">&x;</svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.test/private"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
        '<svg xmlns="http://www.w3.org/2000/svg" style="fill:red"/>',
        '<svg xmlns="http://www.w3.org/2000/svg"><rect fill="url(file:///private)"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><use href="#a"/></svg>',
        "<html/>",
        "<svg",
    ],
)
def test_unsafe_svg_never_launches_native(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    path, _ = fixture(tmp_path)
    (tmp_path / "in.svg").write_text(content)

    def no_native(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("unsupported SVG reached native application")

    monkeypatch.setattr("creative_capability_bridge.exports.subprocess.run", no_native)
    with pytest.raises(PlanError):
        execute_export(load_export_job(path), "fake")
    assert not (tmp_path / "out.png").exists()


def test_source_encoding_limits_and_local_fragments(tmp_path: Path) -> None:
    path, _ = fixture(tmp_path)
    job = load_export_job(path)
    job.source.write_bytes(SVG.encode("utf-16"))
    with pytest.raises(PlanError):
        export_preflight(job, "fake")
    job.source.write_bytes(b"x" * 4_000_001)
    with pytest.raises(PlanError):
        export_preflight(job, "fake")
    job.source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><rect fill="url(#local)"/></svg>'
    )
    assert export_preflight(job, "fake")["ready"]
    job.source.unlink()
    with pytest.raises(PlanError):
        export_preflight(job, "fake")


@pytest.mark.parametrize(
    "kind", ["failure", "timeout", "bad-png", "source-drift", "output-race", "receipt-race"]
)
def test_failures_preserve_sources_and_existing_destinations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    path, _ = fixture(tmp_path)
    job = load_export_job(path)

    def render(args: list[str], **kwargs: Any) -> SimpleNamespace:
        if kind == "timeout":
            raise subprocess.TimeoutExpired("fake", 120)
        if kind == "failure":
            return SimpleNamespace(returncode=1)
        result = fake_renderer(args, **kwargs)
        target = Path(next(a.split("=", 1)[1] for a in args if a.startswith("--export-filename=")))
        if kind == "bad-png":
            target.write_bytes(b"not PNG")
        if kind == "source-drift":
            job.source.write_text(SVG + " ")
        if kind == "output-race":
            job.output.write_bytes(b"keep output")
        if kind == "receipt-race":
            job.receipt.write_bytes(b"keep receipt")
        return result

    monkeypatch.setattr("creative_capability_bridge.exports.subprocess.run", render)
    with pytest.raises(PlanError):
        execute_export(job, "fake")
    if kind == "output-race":
        assert job.output.read_bytes() == b"keep output"
    else:
        assert not job.output.exists()
    if kind == "receipt-race":
        assert job.receipt.read_bytes() == b"keep receipt"
    else:
        assert not job.receipt.exists()
    assert job.source.read_text().strip() == SVG


@pytest.mark.parametrize(
    "raw", [b"bad", png(2, 2), png()[:-3], png()[:33], png()[:-1] + b"x", png() + b"extra"]
)
def test_png_structure_rejected(tmp_path: Path, raw: bytes) -> None:
    path = tmp_path / "out.png"
    path.write_bytes(raw)
    with pytest.raises(PlanError):
        _verify_png(path, 8, 8)


def test_unavailable_native_and_missing_destination_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _ = fixture(tmp_path)
    job = load_export_job(path)
    monkeypatch.setattr("creative_capability_bridge.exports.shutil.which", lambda _: None)
    assert main(["export", str(path), "--preflight"]) == 1
    with pytest.raises(PlanError):
        execute_export(job)
    missing = ExportJob(job.source, tmp_path / "missing/out.png", job.receipt, 8, 8)
    with pytest.raises(PlanError):
        export_preflight(missing, "fake")
