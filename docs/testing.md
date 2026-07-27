# Testing strategy

The test pyramid distinguishes protocol correctness from native compatibility and human usability.

- Unit tests cover plan validation, field bounds, capability manifests, script generation, CLI exit codes, and browser plan construction.
- Adapter conformance tests verify source preservation, target lookup, semantic SVG output, collision handling, and external-process boundaries.
- Native smoke tests launch Blender and Inkscape on Ubuntu and require non-empty application-produced artifacts.
- GIMP 3 command generation, guards, manifests, and conformance contracts run in the ordinary suite. `ccb conformance gimp --native` performs the installation-specific XCF fixture check when GIMP 3 is available.
- Transaction tests cover atomic placement, rollback copies, partial failure cleanup, checkpoint resume, and drift rejection.
- Security-focused tests cover policy violations, pipeline cycles, archive traversal, Ed25519 verification, mismatched keys, and signed-artifact tampering.
- Release checks build Python distributions and the static site.
- Human review evaluates layout, keyboard access, wording, and whether the shared interaction actually improves comprehension.

Pixel-perfect snapshots are not the primary oracle because fonts and renderers differ. Tests inspect semantic document state wherever possible.
