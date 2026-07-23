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

Native tests are opt-in locally because Blender and Inkscape are large external applications:

```bash
CCB_REQUIRE_NATIVE=1 pytest tests/test_native.py
```

GitHub CI installs both applications on Ubuntu and requires those smoke tests.

## Adapter rule

An adapter must preserve the input, refuse an existing output by default, expose a manifest, report unsupported fields before launching the application, avoid arbitrary shell evaluation, enforce timeouts, and prove semantic results with fixtures. See `docs/adapter-authoring.md`.

## Releases

Update version metadata, changelog, compatibility documentation, README claims, examples, release assets, repository description/topics, and the Forge catalog together. Tags use `vMAJOR.MINOR.PATCH`.

