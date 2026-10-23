# Compatibility policy

The Python protocol and direct SVG adapter support Python 3.10 through 3.14 on Windows, macOS, and Linux. The reference interface targets current evergreen browsers.

Version 1.3.1 uses `cryptography` 50.x for Ed25519 signing and verification. Upstream 50.x wheels
cover the architectures published by `cryptography`; installations without a compatible wheel may
require that project's documented source-build toolchain. The cross-platform CI matrix installs the
declared dependency before making a platform claim.

GitHub CI performs native Ubuntu smoke tests against the Blender and Inkscape versions supplied by the current Ubuntu runner repositories. Those checks prove basic creation and rendering, not every operating-system and application combination.

The GIMP adapter targets GIMP 3.0 and newer through the documented Script-Fu batch interpreter. Its generated scripts and contract checks run in the ordinary suite. A separate required GIMP container job exercises saved XCF documents with real GIMP; operators can reproduce it with CCB_REQUIRE_GIMP=1 pytest tests/test_gimp_native.py --no-cov and ccb conformance gimp --native. Exact observed versions and results belong in the measured evidence, not in an open-ended tested-version range.

Application releases can alter command-line flags, object semantics, font resolution, or file behavior. Compatibility reports must include exact versions and a minimal synthetic plan. A release claim is updated only after repeatable evidence.

`ccb compatibility` reports protocol-level support before a native application is launched. `exact` means every supplied field has a direct adapter representation; `approximate` names any semantic caveat; `unsupported` includes the validation reason. This report is not a claim that the native executable is installed—use `ccb doctor` for availability, `ccb conformance ADAPTER --native` for a fixture, and an execution receipt for the observed version.

## Measured conformance matrix

CI uploads `verified-version-matrix` after its required native tests. It contains exact observed versions and individual results. `ccb conformance-matrix --native` regenerates the report for another installation. Contract-only and unavailable rows are not verified native compatibility. Blender transform tests inspect location, rotation, scale and preservation after a second saved document; SVG tests preserve the transform attribute through a text update. GIMP fixture plans document layer-center rotation and potential raster loss; no geometric equivalence to vector/object transforms is claimed.

## Measured 1.4.0 candidate results

[Exact CI evidence](verified-version-matrix-1.4.0.json) records Blender 4.0.2 native creation/inspection, four transform round trips and the separate CI font-loading test; Inkscape 1.2.2 native smoke and four SVG document round trips passed. GIMP native semantic acceptance was unavailable. These are tested versions, not a claim about every release in a major version family.

## 1.6.1 scope

GIMP inspection now decodes layer identifiers and text without using tab/newline content as record separators. Native calls use a fresh instance and terminate after their batch; inspection treats two offset return values as a list. Missing requested font resources fail explicitly; omitted fonts use GIMP context defaults. Partial position updates preserve the other axis. The required GIMP gate measures saved text creation/update, offsets and nonuniform dimensions. Rotation, arbitrary XCF fidelity and other operating systems remain outside that acceptance. Image/package versions are measured at execution time; the Docker recipe is a setup recipe, not a pinned application-version promise.

[Measured 1.6.1 GIMP evidence](verified-gimp-native-1.6.1.json) records GIMP 3.2.2 on Linux Ubuntu 26.04 in an isolated nonroot container, including real saved-XCF acceptance and native conformance. It does not cover GIMP 3.0/3.1, arbitrary XCF files, Windows/macOS, rotation accuracy or pixel fidelity. Historical 1.4.0 evidence is retained unchanged.
