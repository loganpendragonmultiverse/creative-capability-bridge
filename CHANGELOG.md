# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and Semantic Versioning.

## [1.3.0] - 2026-07-26

### Added

- Semantic before/after document comparison for object additions, removals, and changed properties.
- Transactional execution through inspected temporary outputs, atomic destination placement, and retained rollback backups when replacing an existing output.
- Stable operation IDs and tags, selective `--only`, `--skip`, and `--from` execution, hash-bound checkpoint state, and safe resume.
- Reusable adapter conformance checks with optional native fixture execution.
- Coordinate normalization for pixels, points, physical units, Blender units, origins, Y-axis direction, and rotation direction.
- GIMP 3 Script-Fu adapter for XCF text and transform operations plus read-only layer inspection.
- Versioned policy profiles for adapter, capability, path, size, receipt, inspection, replacement, and signed-bundle controls.
- Versioned dependency-aware multi-document pipelines with cycle and missing-dependency rejection.
- Optional Ed25519 key generation and signatures for bundle manifests and execution receipts.

### Changed

- Execution now uses a transaction boundary by default while retaining version 1 plan compatibility.
- Capability negotiation, inspection, diagnostics, and documentation now include GIMP 3.
- The Python package now depends on `cryptography` for optional asymmetric signatures.

## [1.2.0] - 2026-07-26

### Added

- Semantic plan linting for operation order, duplicate creation, and target existence, with optional read-only document inspection.
- Verified bundle extraction into a new destination with path, length, hash, and collision guards.
- Receipt verification that re-hashes recorded inputs and outputs to report missing files or drift.

### Changed

- Replaced generic wording with specific execution-summary language.

## [1.1.0] - 2026-07-26

### Added

- Read-only SVG and Blender document inspection with target, text, font, and transform reporting.
- Clear execution summaries covering file effects, targets, requirements, and approximations.
- Hash-verified portable project bundles with optional assets, license notes, and fallback fonts.
- Opt-in JSON execution receipts and deterministic receipt comparison.
- Adapter-neutral intent plans, exact/approximate/unsupported compatibility reports, and safe retargeting.

### Changed

- Capability manifests now publish tested native-application version ranges.
- Project documentation and browser reference page now describe the complete portable workflow and its limits.

## [1.0.0] - 2026-07-22

### Added

- Versioned JSON capability-plan protocol with strict validation and source-preserving output rules.
- Blender background-Python adapter for text creation, text updates, transforms, materials, and `.blend` output.
- Inkscape SVG document adapter with optional native CLI preview rendering.
- Machine-readable capability manifests, validation, preview, execution, and environment-diagnostic commands.
- Local browser plan builder with downloadable plans and a public research roadmap.
- Cross-platform core CI, native Ubuntu adapter smoke tests, CodeQL, dependency audits, release builds, and project-specific documentation.

[1.3.0]: https://github.com/loganpendragonmultiverse/creative-capability-bridge/releases/tag/v1.3.0
[1.2.0]: https://github.com/loganpendragonmultiverse/creative-capability-bridge/releases/tag/v1.2.0
[1.1.0]: https://github.com/loganpendragonmultiverse/creative-capability-bridge/releases/tag/v1.1.0
[1.0.0]: https://github.com/loganpendragonmultiverse/creative-capability-bridge/releases/tag/v1.0.0
