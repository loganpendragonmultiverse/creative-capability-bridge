# Creative Capability Bridge

[![CI](https://github.com/loganpendragonmultiverse/creative-capability-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/loganpendragonmultiverse/creative-capability-bridge/actions/workflows/ci.yml)
[![CodeQL](https://github.com/loganpendragonmultiverse/creative-capability-bridge/actions/workflows/codeql.yml/badge.svg)](https://github.com/loganpendragonmultiverse/creative-capability-bridge/actions/workflows/codeql.yml)
[![MIT License](https://img.shields.io/badge/license-MIT-17201d.svg)](LICENSE)

Creative Capability Bridge (CCB) is a versioned protocol, adapter toolkit, and reference plan builder for expressing common creative operations once and translating them for different applications.

Version 1.0 supports text creation, text updates, and explicit transforms through Blender and Inkscape adapters. It is deliberately a small proof of the capability-oriented architecture—not a replacement interface for every creative application.

**[Open the plan builder](https://loganpendragonmultiverse.github.io/creative-capability-bridge/)**

## Why this exists

Creative applications repeatedly implement text, transforms, colors, exports, asset browsers, and similar capabilities with different interaction models. CCB separates the user's intent from application-specific commands:

```text
reference interface or JSON authoring
                 ↓
       CCB protocol v1 plan
                 ↓
     validate and negotiate support
                 ↓
 Blender adapter       Inkscape adapter
 background Python     SVG + optional CLI render
```

The protocol is the stable center. Applications remain installed separately, upstream code is not forked, and every output path is explicit.

## Current capabilities

| Capability | Blender | Inkscape |
|---|---:|---:|
| Create text | Yes | Yes |
| Update bridge-managed or identified text | Yes | Yes |
| Font family request | Recorded; native font resolution is application-dependent | SVG `font-family` |
| Font size, alignment, fill | Yes | Yes |
| Position and Z rotation | Yes | Yes |
| X/Y scale | Yes | Yes |
| Z position and scale | Yes | Not applicable |
| Native preview rendering | Through Blender output | Optional Inkscape CLI PNG export |

Use `ccb capabilities --json` for the machine-readable manifests.

## Three-minute start

Requires Python 3.10 or newer. Native Blender execution requires Blender on `PATH`. Inkscape is optional unless a native PNG preview is requested.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install .
ccb validate examples/inkscape-text.json
ccb preview examples/inkscape-text.json
ccb execute examples/inkscape-text.json
```

The example writes `examples/output/inkscape-text.svg`. It does not change an input file.

For Blender:

```bash
ccb doctor
ccb preview examples/blender-text.json
ccb execute examples/blender-text.json
```

The [browser plan builder](https://loganpendragonmultiverse.github.io/creative-capability-bridge/) creates JSON locally. It does not upload documents or execute applications.

## Plan format

```json
{
  "version": 1,
  "adapter": "inkscape",
  "input": null,
  "output": "output.svg",
  "operations": [
    {
      "capability": "text.create",
      "target": "title",
      "parameters": {
        "content": "A common interface",
        "font_family": "Liberation Sans",
        "font_size": 48,
        "alignment": "center",
        "fill": "#1D2522",
        "x": 600,
        "y": 300
      }
    }
  ]
}
```

Paths are resolved relative to the plan file. Input and output must differ. Existing outputs are refused unless the user explicitly passes `--replace`; that flag never authorizes changing the input.

See [protocol details](docs/protocol.md) and [adapter authoring](docs/adapter-authoring.md).

## Architecture and safety

- Plans are plain JSON and can be reviewed before execution.
- Unknown operations, fields, adapters, dimensions, and unsafe same-file outputs fail closed.
- Inkscape editing uses its documented SVG format; optional native preview invokes the Inkscape CLI.
- Blender receives a generated background Python script containing a base64-encoded, already-validated plan.
- Originals are never overwritten.
- No network request, telemetry, cloud service, model call, or runtime AI is used.
- A plan can modify or create creative documents, so review plans from untrusted sources before execution.

Read the complete [security model](docs/security-model.md).

## Honest limitations

- Version 1 is file-oriented. It does not synchronize with a selection in an already-open GUI.
- Blender and Inkscape are not interchangeable. CCB exposes a common core and rejects unsupported dimensions rather than inventing equivalence.
- The Blender font-family field records the requested family because reliable cross-platform font resolution needs a future explicit font-mapping contract.
- Inkscape document edits are deterministic SVG operations; Inkscape itself is invoked only for optional native preview rendering.
- Rotations use degrees around each application's document/object origin. Pivot negotiation is not part of protocol v1.
- Intuitiveness requires real user research and cannot be established by automated tests alone.
- Native compatibility is version-sensitive. See the [compatibility policy](docs/compatibility.md).

## Research roadmap

These are potential directions under investigation, not promised features or release dates:

1. **Live adapter sessions** — small, local in-application bridges for selection, state, undo groups, transactions, and event synchronization.
2. **GIMP and FreeCAD adapters** — only after their semantics can be expressed through the same conformance suite without hiding important differences.
3. **Additional capability families** — color fills, export profiles, asset browsing, parameter editing, and timelines.
4. **Units, pivots, and coordinate contracts** — explicit negotiation for pixels, physical units, document units, world units, origins, and transform order.
5. **Adapter registry and conformance badges** — signed manifests, version ranges, fixtures, and reproducible compatibility evidence.
6. **Accessibility and keyboard workflows** — shared interaction research rather than merely copying existing application controls.
7. **Guarded natural-language planning** — an optional planner that proposes visible protocol operations, validates them, and requires confirmation. Arbitrary generated scripts and silent execution are explicitly out of scope.

Roadmap proposals belong in GitHub Discussions before implementation so the shared model does not grow by accident.

## Testing

```bash
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
mypy src tests
pytest
npm test
npm run check
npm run build
python -m build
```

The ordinary suite tests schema rejection, adapter conformance, source preservation, generated Blender scripts, SVG semantics, CLI behavior, and the plan-builder core. GitHub CI also runs native Blender and Inkscape smoke tests on Ubuntu. Visual usability remains a human review concern.

## Privacy and platforms

CCB runs locally on Windows, macOS, and Linux wherever Python and the selected application are available. The static plan builder runs in modern browsers and does not transmit or store content.

## Contributing and maintenance

Contributions are welcome through reviewed pull requests. Start with [CONTRIBUTING.md](CONTRIBUTING.md), the [development guide](DEVELOPMENT.md), and the adapter contract. Compatibility reports should include the operating system, application version, plan, expected semantic result, and actual result using synthetic fixtures where possible.

Version 1.0.0 is feature-complete for its documented scope. Maintenance prioritizes correctness, safe file handling, compatibility evidence, and a small comprehensible protocol over rapidly adding application-specific commands.

## License

[MIT](LICENSE) © 2026 Logan Pendragon Multiverse.

## More open-source projects

This project is part of the [Logan Pendragon Forge open-source collection](https://www.loganpendragonforge.com/open-source/). Browse the catalog for other released tools, source repositories, live demos, and downloads.
