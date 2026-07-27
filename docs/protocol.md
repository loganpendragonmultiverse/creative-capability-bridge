# Protocol v1

A plan contains `version`, `adapter`, optional `input`, required `output`, and one to 100 ordered `operations`. Paths are relative to the plan file unless absolute. Inputs and outputs cannot resolve to the same path. Each operation may have a unique portable `id` and up to 20 portable `tags`; plans without them remain valid.

Targets use portable identifiers beginning with a letter followed by at most 63 letters, numbers, underscores, or hyphens. Adapters may match a bridge-managed identifier or a native object identifier when documented.

## Operations

- `text.create` requires `content`. Optional fields are `font_family`, `font_size`, `alignment`, `fill`, and initial position.
- `text.update` changes only supplied text properties and requires an existing text target.
- `transform.set` sets supplied position, Z rotation in degrees, and scale values. Omitted values retain adapter defaults in newly created documents or remain unchanged when an adapter can preserve them.

Colors use `#RRGGBB` or `#RRGGBBAA`. Scales and font sizes must be positive. Coordinates are bounded finite numbers. Inkscape and GIMP reject Z-axis parameters.

An optional `coordinate_space` declares `unit`, `origin`, `y_axis`, `dpi`, and document extents. Execution normalizes pixels, points, millimeters, centimeters, inches, and Blender units into the selected adapter's native space. Protocol v1 still does not define arbitrary pivots, arbitrary scripts, live selections, or GUI undo synchronization.

## Intent plans and negotiation

An intent plan may use `"adapter": "auto"` and an extensionless output. It is not executable. `ccb compatibility` validates a concrete projection for every bundled adapter and reports each as `exact`, `approximate`, or `unsupported`. `ccb retarget` writes a new concrete plan with the correct output extension and runs the ordinary strict validator before writing it.

This separation is intentional: negotiation can discuss portability, while execution never guesses an application.

## Evidence formats

Bundle manifests, execution receipts, checkpoint state, policy profiles, and pipeline documents are independently versioned at `1`. They do not change protocol plan version 1. A bundle uses archive-relative paths and SHA-256 file hashes. A receipt records a completed execution, its output hash, operation results, versions, warnings, and elapsed time. Bundle manifests and receipts may include an Ed25519 signature over their canonical JSON payload.

Semantic linting is also outside the wire protocol. Schema validation answers whether a plan is structurally executable; `ccb lint` additionally checks target flow. Without a document, references not established earlier in the plan are warnings. With `--document`, read-only inspection turns missing target references into errors.

## Execution and orchestration

Execution is transactional: the adapter writes a temporary same-format document, CCB inspects that document, and only then atomically places it at the requested destination. Replacing an existing output retains a separate rollback copy.

Selective execution matches operation IDs or tags. Checkpoint state binds completed operation IDs to the canonical plan hash and current output hash; resume fails if either has drifted. A pipeline is a separate dependency graph whose steps reference ordinary plan files. Dependency cycles and missing steps fail before execution.
