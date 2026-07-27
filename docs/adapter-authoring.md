# Adapter authoring

Adapters translate validated plans; they do not weaken protocol validation. A conforming adapter must:

1. Publish application, transport, operations, fields, and guarantees in a capability manifest.
2. Preserve the source and require a distinct output.
3. Refuse output replacement unless the caller explicitly authorizes it.
4. Use argument arrays rather than shell-built command strings.
5. Bound external execution with a timeout and surface useful errors.
6. Reject missing targets and collisions rather than guessing.
7. Include deterministic unit tests and at least one native application smoke test where installation is automatable.
8. Document application versions and semantic exceptions.
9. Pass `ccb conformance ADAPTER`; native adapters should also pass the generated fixture where installation is automatable.
10. Accept adapter-native normalized coordinates and produce an output that read-only inspection can verify.

An adapter may support fewer fields than another adapter. Honest capability negotiation is preferable to a misleading lowest-common-denominator implementation.

Third-party adapters can reuse `check_adapter_contract()` with their adapter object and capability manifest. The object must expose `preview()`, `execute()`, `application_version()`, and its resolved executable. Execution is wrapped by CCB's transaction boundary; adapters must not replace the final destination themselves.
