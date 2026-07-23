export const CAPABILITIES = {
  blender: {
    label: "Blender",
    output: "output.blend",
    dimensions: 3,
    transport: "Background Python adapter"
  },
  inkscape: {
    label: "Inkscape",
    output: "output.svg",
    dimensions: 2,
    transport: "SVG document adapter + optional CLI preview"
  }
};

export function normalizeNumber(value, fallback) {
  if (value === "" || value === null || value === undefined) return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) throw new Error("Numeric fields must contain finite numbers.");
  return parsed;
}

export function buildPlan(values, operations = []) {
  if (!CAPABILITIES[values.adapter]) throw new Error("Choose a supported adapter.");
  const output = String(values.output || "").trim();
  if (!output) throw new Error("Choose an output file.");
  if (operations.length === 0) throw new Error("Add at least one operation.");
  return {
    version: 1,
    adapter: values.adapter,
    input: String(values.input || "").trim() || null,
    output,
    operations
  };
}

export function makeTextOperation(values) {
  const content = String(values.content || "");
  if (!content) throw new Error("Text content cannot be empty.");
  if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(values.target)) {
    throw new Error("Target must start with a letter and use only letters, numbers, _ or -.");
  }
  const parameters = {
    content,
    font_family: String(values.fontFamily || "Liberation Sans"),
    font_size: normalizeNumber(values.fontSize, 48),
    alignment: values.alignment || "left",
    fill: values.fill || "#1D2522",
    x: normalizeNumber(values.x, 0),
    y: normalizeNumber(values.y, 0)
  };
  if (values.adapter === "blender") parameters.z = normalizeNumber(values.z, 0);
  return { capability: "text.create", target: values.target, parameters };
}

export function makeTransformOperation(values) {
  const parameters = {
    x: normalizeNumber(values.x, 0),
    y: normalizeNumber(values.y, 0),
    rotation_degrees: normalizeNumber(values.rotation, 0),
    scale_x: normalizeNumber(values.scaleX, 1),
    scale_y: normalizeNumber(values.scaleY, 1)
  };
  if (values.adapter === "blender") {
    parameters.z = normalizeNumber(values.z, 0);
    parameters.scale_z = normalizeNumber(values.scaleZ, 1);
  }
  return { capability: "transform.set", target: values.target, parameters };
}

