# Testing

Use the complete gates in [docs/testing.md](docs/testing.md) and DEVELOPMENT.md.

## Version 1.4.0: reviewed improvements

Add portable font mappings with missing-font diagnostics, transform/pivot fixture generation and version-scoped conformance evidence.

The fonts command maps requested families per adapter, reports missing/unmapped families, accepts an optional operator-supplied family inventory, and writes a new resolved plan only when no blocking findings remain. Blender mappings use validated local TTF/OTF files through font_file and actually load the font; file presence alone is not a rendering claim. The fixture generator writes 12 transform cases plus 12 round-trip plans with explicit adapter-specific pivot semantics. conformance-matrix records exact observed application versions, separates contract-only/native-smoke/document-adapter evidence, and verifies Blender transform round-trips when available. CI requires real Blender transforms/font loading and Inkscape rendering, then uploads the measured version matrix. GIMP native semantic acceptance remains unverified when unavailable. Sources are preserved and existing output files are refused.

```shell
ccb fonts plan.json --map font-map.json --inventory installed-families.json --output mapped-plan.json
ccb conformance-fixtures new-fixtures
ccb conformance-matrix --native --output new-version-matrix.json
```
