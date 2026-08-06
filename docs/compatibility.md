# Compatibility policy

The Python protocol and direct SVG adapter support Python 3.10 through 3.14 on Windows, macOS, and Linux. The reference interface targets current evergreen browsers.

Version 1.3.1 uses `cryptography` 50.x for Ed25519 signing and verification. Upstream 50.x wheels
cover the architectures published by `cryptography`; installations without a compatible wheel may
require that project's documented source-build toolchain. The cross-platform CI matrix installs the
declared dependency before making a platform claim.

GitHub CI performs native Ubuntu smoke tests against the Blender and Inkscape versions supplied by the current Ubuntu runner repositories. Those checks prove basic creation and rendering, not every operating-system and application combination.

The GIMP adapter targets GIMP 3.0 and newer through the documented Script-Fu batch interpreter. Its generated scripts and conformance contract are covered by the ordinary suite; operators can run `ccb conformance gimp --native` against their installed build. A native GIMP CI claim is not made until a stable runner package is available and explicitly required by the workflow.

Application releases can alter command-line flags, object semantics, font resolution, or file behavior. Compatibility reports must include exact versions and a minimal synthetic plan. A release claim is updated only after repeatable evidence.

`ccb compatibility` reports protocol-level support before a native application is launched. `exact` means every supplied field has a direct adapter representation; `approximate` names any semantic caveat; `unsupported` includes the validation reason. This report is not a claim that the native executable is installed—use `ccb doctor` for availability, `ccb conformance ADAPTER --native` for a fixture, and an execution receipt for the observed version.
