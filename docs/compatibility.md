# Compatibility policy

The pure-Python protocol and Inkscape SVG adapter support Python 3.10 through 3.14 on Windows, macOS, and Linux. The reference interface targets current evergreen browsers.

GitHub CI performs native Ubuntu smoke tests against the Blender and Inkscape versions supplied by the current Ubuntu runner repositories. Those tests prove basic creation and rendering, not every operating-system/application combination.

Application releases can alter command-line flags, object semantics, font resolution, or file behavior. Compatibility reports must include exact versions and a minimal synthetic plan. A release claim is updated only after repeatable evidence.

`ccb compatibility` reports protocol-level support before a native application is launched. `exact` means every supplied field has a direct adapter representation; `approximate` names any semantic caveat; `unsupported` includes the validation reason. This report is not a claim that the native executable is installed—use `ccb doctor` for availability and an execution receipt for the observed version.
