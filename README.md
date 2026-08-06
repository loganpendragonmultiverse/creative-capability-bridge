# Creative Capability Bridge

[![CI](https://github.com/loganpendragonmultiverse/creative-capability-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/loganpendragonmultiverse/creative-capability-bridge/actions/workflows/ci.yml)
[![CodeQL](https://github.com/loganpendragonmultiverse/creative-capability-bridge/actions/workflows/codeql.yml/badge.svg)](https://github.com/loganpendragonmultiverse/creative-capability-bridge/actions/workflows/codeql.yml)
[![MIT License](https://img.shields.io/badge/license-MIT-17201d.svg)](LICENSE)

Creative Capability Bridge (CCB) is a versioned protocol, adapter toolkit, and reference plan builder for expressing common creative operations once and translating them for different applications.

Version 1.3 supports text creation, text updates, and explicit transforms through Blender, Inkscape, and GIMP 3 adapters. It adds transactional execution, rollback backups, resumable and selective plans, semantic document diffs, coordinate normalization, policy profiles, dependency-aware multi-document pipelines, adapter conformance checks, and optional Ed25519 signatures for bundles and receipts. Version 1.3.1 updates the signing dependency to the patched `cryptography` 50.x release line.

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
 Blender adapter       Inkscape adapter       GIMP 3 adapter
 background Python     SVG + optional render  Script-Fu batch
```

The protocol is the stable center. Applications remain installed separately, upstream code is not forked, and every output path is explicit.

## Current capabilities

| Capability | Blender | Inkscape | GIMP 3 |
|---|---:|---:|---:|
| Create text | Yes | Yes | Yes |
| Update bridge-managed or identified text | Yes | Yes | Yes |
| Font family request | Recorded; native resolution is application-dependent | SVG `font-family` | GIMP font resource |
| Font size, alignment, fill | Yes | Yes | Yes |
| Position and Z rotation | Yes | Yes | Yes |
| X/Y scale | Yes | Yes | Yes |
| Z position and scale | Yes | Not applicable | Not applicable |
| Read-only structural inspection | Yes | Yes | Yes |
| Native conformance fixture | Yes | Yes | Yes when GIMP is installed |

Use `ccb capabilities --json` for the machine-readable manifests.

## Portable workflow

CCB adds reviewable stages around execution:

```bash
ccb inspect source.svg
ccb explain plan.json
ccb lint plan.json --document source.svg
ccb compatibility examples/portable-text.json
ccb retarget examples/portable-text.json --adapter inkscape --output inkscape-plan.json
ccb bundle create inkscape-plan.json project.ccb.zip --asset LICENSE.txt --fallback-font sans-serif
ccb bundle verify project.ccb.zip
ccb bundle extract project.ccb.zip unpacked-project
ccb execute inkscape-plan.json --receipt receipt.json
ccb verify-receipt receipt.json
ccb compare-receipts receipt-a.json receipt-b.json
ccb diff source.svg output.svg
ccb normalize plan.json
ccb conformance inkscape --native
```

- `inspect` reads `.svg` metadata directly and uses Blender's background mode for `.blend`; it does not save the source.
- `explain` lists files read/created, replacement state, created/modified targets, requirements, and known approximations.
- `lint` checks operation order and target lifecycles; with `--document`, it confirms referenced targets through read-only inspection.
- Bundles contain `plan.json`, optional `assets/`, and a manifest with SHA-256 hashes, license notes, fallback fonts, and archive-relative paths.
- `bundle extract` verifies hashes and paths first, then writes only into a new destination directory.
- Receipts record tool/application versions, hashes, operations, warnings, platform, and elapsed time after a successful execution. They contain paths and may expose local directory names, so review them before sharing.
- `verify-receipt` re-hashes the recorded input and output to detect missing or changed files.
- `adapter: "auto"` is valid for compatibility and retargeting only. Execution still requires a concrete, validated adapter plan.
- Every execution is staged into a temporary same-format document and inspected before an atomic destination replacement. Existing outputs receive a retained rollback backup.
- Operation IDs and tags enable `--only`, `--skip`, and `--from`; `--state` plus `--resume` verifies the output hash before continuing from recorded checkpoints.
- Policy profiles constrain adapters, capabilities, output roots, operation counts, input size, replacement, inspection, receipts, and signed-bundle requirements.
- Pipeline files order multiple plans through explicit `depends_on` relationships and reject missing or cyclic dependencies.
- Bundles and receipts can be signed and verified with local Ed25519 key pairs. Private keys are never placed in bundles or receipts.

## Three-minute start

Requires Python 3.10 or newer. Native execution requires the selected application on `PATH`; GIMP support targets GIMP 3's bundled Script-Fu batch interpreter. Inkscape is optional unless native rendering is requested because ordinary SVG editing is handled directly.

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

For GIMP 3:

```bash
ccb preview examples/gimp-text.json
ccb conformance gimp --native
ccb execute examples/gimp-text.json --receipt gimp-receipt.json
```

For guarded, resumable work:

```bash
ccb key generate ccb-private.pem ccb-public.pem
ccb bundle create plan.json project.ccb.zip --signing-key ccb-private.pem
ccb bundle verify project.ccb.zip --public-key ccb-public.pem --require-signature
ccb execute plan.json --only titles --state run.state.json --receipt run.json
ccb execute plan.json --state run.state.json --resume --receipt resumed.json
ccb policy check plan.json examples/safe-policy.json --receipt run.json
ccb pipeline validate examples/two-document-pipeline.json
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
      "id": "create-title",
      "tags": ["titles"],
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
  ],
  "coordinate_space": {
    "unit": "px",
    "origin": "top-left",
    "y_axis": "down",
    "dpi": 96,
    "width": 1200,
    "height": 800
  }
}
```

Paths are resolved relative to the plan file. Input and output must differ. Existing outputs are refused unless the user explicitly passes `--replace`; that flag never authorizes changing the input. Operation IDs and tags are optional, so existing version 1 plans remain valid.

See [protocol details](docs/protocol.md) and [adapter authoring](docs/adapter-authoring.md).

## Architecture and safety

- Plans are plain JSON and can be reviewed before execution.
- Unknown operations, fields, adapters, dimensions, and unsafe same-file outputs fail closed.
- Bundle verification rejects duplicate or traversal paths and validates declared lengths and SHA-256 hashes before use.
- Inkscape editing uses its documented SVG format; optional native preview invokes the Inkscape CLI.
- Blender receives a generated background Python script containing a base64-encoded, already-validated plan.
- GIMP 3 receives a generated Script-Fu program through its documented noninteractive batch interpreter.
- Execution writes and inspects a temporary document before atomically placing it at the requested output. A replacement preserves the prior output as a separate rollback file.
- Ed25519 signatures authenticate canonical bundle manifests and receipt payloads when the operator supplies a trusted public key.
- Originals are never overwritten.
- No network request, telemetry, cloud service, model call, or runtime AI is used.
- A plan can modify or create creative documents, so review plans from untrusted sources before execution.

Read the complete [security model](docs/security-model.md).

## Honest limitations

- Version 1 is file-oriented. It does not synchronize with a selection in an already-open GUI.
- Inspection exposes supported metadata, not a complete application scene graph, and cannot guarantee that every native object is semantically editable.
- Unsigned bundles verify integrity but not publisher identity or asset licensing; license notes remain operator-supplied. Optional signatures prove possession of a private key, not the real-world identity behind that key.
- Receipts record and hash one local execution. Optional signatures protect the receipt payload from later alteration but do not independently prove that the native application behaved honestly.
- Blender, Inkscape, and GIMP are not interchangeable. CCB exposes a common core and rejects unsupported dimensions rather than inventing equivalence.
- The Blender font-family field records the requested family because reliable cross-platform font resolution needs a future explicit font-mapping contract.
- Inkscape document edits are deterministic SVG operations; Inkscape itself is invoked only for optional native preview rendering.
- Coordinate conversion covers pixels, points, physical units, Blender units, origins, and Y-axis direction. Arbitrary pivots and full transform-order negotiation remain outside protocol v1.
- GIMP inspection reports portable layer identifiers, dimensions, and offsets; it does not expose every XCF property or claim full semantic equivalence with SVG or Blender scenes.
- Intuitiveness requires real user research and cannot be established by automated tests alone.
- Native compatibility is version-sensitive. See the [compatibility policy](docs/compatibility.md).

## Research roadmap

These are potential directions under investigation, not promised features or release dates:

1. **Live adapter sessions** — small, local in-application bridges for selection, state, undo groups, transactions, and event synchronization.
2. **FreeCAD and additional adapters** — only after their semantics can be expressed through the conformance suite without hiding important differences.
3. **Additional capability families** — color fills, export profiles, asset browsing, parameter editing, and timelines.
4. **Pivot and transform-order contracts** — extend the shipped unit, origin, and axis conversion model to application-specific pivot behavior.
5. **Adapter registry and conformance badges** — distributable third-party manifests, version ranges, and reproducible compatibility evidence.
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

The ordinary suite tests schema rejection, transactions and rollback, resume drift, policies, pipelines, signatures, coordinate conversion, semantic diffs, adapter conformance, generated Blender/GIMP scripts, SVG semantics, CLI behavior, and the plan-builder core. GitHub CI also runs native Blender and Inkscape smoke tests on Ubuntu. GIMP native conformance is available through `ccb conformance gimp --native` on systems with GIMP 3 installed.

## Privacy and platforms

CCB runs locally on Windows, macOS, and Linux wherever Python and the selected application are available. The static plan builder runs in modern browsers and does not transmit or store content.

## Contributing and maintenance

Contributions are welcome through reviewed pull requests. Start with [CONTRIBUTING.md](CONTRIBUTING.md), the [development guide](DEVELOPMENT.md), and the adapter contract. Compatibility reports should include the operating system, application version, plan, expected semantic result, and actual result using synthetic fixtures where possible.

Version 1.3.1 is feature-complete for its documented scope. Maintenance prioritizes transaction safety, compatibility evidence, explicit policy, and backward-compatible protocol changes over rapidly adding application-specific commands.

## License

[MIT](LICENSE) © 2026 Logan Pendragon Multiverse.

## More open-source projects

This project is part of the [Logan Pendragon Forge open-source collection](https://www.loganpendragonforge.com/open-source/). Browse the catalog for other released tools, source repositories, live demos, and downloads.
