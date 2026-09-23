# Development guide

## Product boundary

Creative Capability Bridge v1 proves that shared, explicit creative intents can be validated and translated through application-specific adapters. It is not a universal GUI, a UI automation recorder, an AI agent, or a promise that unlike application concepts are equivalent.

Protocol changes require examples, adapter conformance tests, compatibility notes, and a clear failure mode for unsupported applications. Prefer capability negotiation over adapter conditionals in the interface.

## Setup and checks

```bash
python -m venv .venv
# activate the environment
python -m pip install -e ".[dev]"
python -m pip install --upgrade pip
ruff format --check .
ruff check .
mypy src tests
pytest
python -m pip_audit
npm test
npm run check
npm run build
python -m build
```

Native tests are opt-in locally because Blender, Inkscape, and GIMP are large external applications:

```bash
CCB_REQUIRE_NATIVE=1 pytest tests/test_native.py
```

GitHub CI installs both applications on Ubuntu and requires those smoke tests.

GIMP 3 conformance is currently an explicit operator check:

```bash
ccb conformance gimp --native
```

## Adapter rule

An adapter must preserve the input, refuse an existing output by default, expose a manifest, report unsupported fields before launching the application, avoid arbitrary shell evaluation, enforce timeouts, and prove semantic results with fixtures. See `docs/adapter-authoring.md`.

## Releases

Update version metadata, changelog, compatibility documentation, README claims, examples, release assets, repository description/topics, and the Forge catalog together. Tags use `vMAJOR.MINOR.PATCH`.

## Version 1.4.0: reviewed improvements

Add portable font mappings with missing-font diagnostics, transform/pivot fixture generation and version-scoped conformance evidence.

The fonts command maps requested families per adapter, reports missing/unmapped families, accepts an optional operator-supplied family inventory, and writes a new resolved plan only when no blocking findings remain. Blender mappings use validated local TTF/OTF files through font_file and actually load the font; file presence alone is not a rendering claim. The fixture generator writes 12 transform cases plus 12 round-trip plans with explicit adapter-specific pivot semantics. conformance-matrix records exact observed application versions, separates contract-only/native-smoke/document-adapter evidence, and verifies Blender transform round-trips when available. CI requires real Blender transforms/font loading and Inkscape rendering, then uploads the measured version matrix. GIMP native semantic acceptance remains unverified when unavailable. Sources are preserved and existing output files are refused.

```shell
ccb fonts plan.json --map font-map.json --inventory installed-families.json --output mapped-plan.json
ccb conformance-fixtures new-fixtures
ccb conformance-matrix --native --output new-version-matrix.json
```
