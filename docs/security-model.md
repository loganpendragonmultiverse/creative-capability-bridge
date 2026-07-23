# Security model

CCB treats plans and creative documents as untrusted input.

- JSON fields are allow-listed and bounded.
- Application processes receive argument arrays with timeouts; the shell is not invoked.
- Blender plans are encoded as data inside a fixed reviewed script instead of becoming Python source.
- The Blender command disables no security control and does not enable embedded-file script auto-execution.
- SVG parsing uses the Python standard library and does not resolve external XML entities.
- Existing outputs are refused unless `--replace` is explicit.
- Inputs are never output targets.
- The browser builder has no network, storage, or application-execution capability.

Native applications may load complex documents and have their own security advisories. Keep them updated, avoid untrusted files, and use a sandbox where appropriate. CCB is not a sandbox. Report vulnerabilities privately through GitHub's security advisory interface.

