# Security model

CCB treats plans and creative documents as untrusted input.

- JSON fields are allow-listed and bounded.
- Application processes receive argument arrays with timeouts; the shell is not invoked.
- Blender plans are encoded as data inside a fixed reviewed script instead of becoming Python source.
- The Blender command disables no security control and does not enable embedded-file script auto-execution.
- SVG parsing uses the Python standard library and does not resolve external XML entities.
- Existing outputs are refused unless `--replace` is explicit.
- Execution stages an output in the destination directory, inspects it, and uses an atomic replacement. Existing outputs are copied to a distinct rollback path before replacement.
- Inputs are never output targets.
- The browser builder has no network, storage, or application-execution capability.
- Inspection is read-only; Blender inspection runs a fixed script and never invokes a save operation.
- GIMP execution and inspection use generated Script-Fu loaded through GIMP 3's noninteractive batch interpreter; plan values are serialized as data and no shell is invoked.
- Bundle verification rejects absolute paths, parent traversal, drive-qualified paths, duplicate entries, and hash or length mismatches.
- Bundle extraction runs verification first, refuses an existing destination, and writes only declared files into the new directory.
- Receipt creation is opt-in and refuses to overwrite an existing receipt.
- Receipt verification only reads and hashes the paths recorded in the receipt; it never restores or modifies them.
- Resume state is accepted only when both its canonical plan hash and current output hash match.
- Policies fail closed on denied adapters, capabilities, output roots, sizes, replacement, missing evidence, or unsigned-bundle requirements.
- Optional Ed25519 signatures authenticate canonical manifest or receipt bytes against an operator-supplied public key. Private keys are read only during signing and are never embedded in artifacts.

Receipts include absolute local paths and platform details. Review or redact them before public sharing. Unsigned bundle hashes detect corruption or changes but do not authenticate the publisher. A valid signature proves control of the paired private key, not the legal identity or licensing status of its holder.

Native applications may load complex documents and have their own security advisories. Keep them updated, avoid untrusted files, and use a sandbox where appropriate. CCB is not a sandbox. Report vulnerabilities privately through GitHub's security advisory interface.
