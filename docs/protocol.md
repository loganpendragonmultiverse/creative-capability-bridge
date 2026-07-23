# Protocol v1

A plan contains `version`, `adapter`, optional `input`, required `output`, and one to 100 ordered `operations`. Paths are relative to the plan file unless absolute. Inputs and outputs cannot resolve to the same path.

Targets use portable identifiers beginning with a letter followed by at most 63 letters, numbers, underscores, or hyphens. Adapters may match a bridge-managed identifier or a native object identifier when documented.

## Operations

- `text.create` requires `content`. Optional fields are `font_family`, `font_size`, `alignment`, `fill`, and initial position.
- `text.update` changes only supplied text properties and requires an existing text target.
- `transform.set` sets supplied position, Z rotation in degrees, and scale values. Omitted values retain adapter defaults in newly created documents or remain unchanged when an adapter can preserve them.

Colors use `#RRGGBB` or `#RRGGBBAA`. Scales and font sizes must be positive. Coordinates are bounded finite numbers. Inkscape rejects Z-axis parameters.

Protocol v1 deliberately does not define pivots, unit conversion, arbitrary scripts, nested operation graphs, live selections, or undo synchronization.

