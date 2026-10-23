"""Write exact observed GIMP evidence after the required real-XCF test gate."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from creative_capability_bridge.adapters import GimpAdapter
from creative_capability_bridge.conformance import run_conformance

environment = dict(os.environ, CCB_REQUIRE_GIMP="1")
semantic = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_gimp_native.py", "--no-cov"],
    env=environment,
    check=True,
)
report = run_conformance("gimp", native=True)
if not report["passed"]:
    raise SystemExit("GIMP native conformance failed")
payload = {
    "application_version": GimpAdapter().application_version(),
    "conformance": report,
    "semantic_test_exit_code": semantic.returncode,
    "semantic_test_command": "CCB_REQUIRE_GIMP=1 pytest tests/test_gimp_native.py --no-cov",
    "packages": subprocess.run(
        ["dpkg-query", "-W", "gimp", "fonts-dejavu-core"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines(),
    "boundary": "Saved text/update, offsets, measured scale and guards only. No rotation, pixel fidelity or other-OS claim.",
}
Path("verified-gimp-native.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps(payload, indent=2))
