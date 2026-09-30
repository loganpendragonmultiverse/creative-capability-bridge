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
  },
  gimp: {
    label: "GIMP 3",
    output: "output.xcf",
    dimensions: 2,
    transport: "GIMP 3 Script-Fu batch adapter"
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

export function validatePlanPayload(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload) || payload.version !== 1) throw new Error("Choose a version 1 plan object.");
  const unknown = Object.keys(payload).filter((key) => !["version","adapter","input","output","operations","coordinate_space"].includes(key));
  if (unknown.length) throw new Error("Unsupported plan fields: " + unknown.join(", "));
  if (typeof payload.adapter !== "string" || !Object.hasOwn(CAPABILITIES,payload.adapter)) throw new Error("Choose a supported adapter.");
  if (payload.input !== null && payload.input !== undefined && typeof payload.input !== "string") throw new Error("Input must be a path or null.");
  if (typeof payload.output !== "string" || !payload.output.trim() || !payload.output.toLowerCase().endsWith({blender:".blend",inkscape:".svg",gimp:".xcf"}[payload.adapter])) throw new Error("Output extension must match the selected application.");
  if (payload.input && payload.input.trim() === payload.output.trim()) throw new Error("Input and output must be different.");
  if (!Array.isArray(payload.operations) || payload.operations.length < 1 || payload.operations.length > 100) throw new Error("A plan requires 1–100 operations.");
  const ids = new Set();
  payload.operations.forEach((op) => {
    if (!op || typeof op !== "object" || !["text.create","text.update","transform.set"].includes(op.capability) || typeof op.target !== "string" || !/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(op.target)) throw new Error("Operation capability or target is invalid.");
    if (Object.keys(op).some((key) => !["capability","target","parameters","id","tags"].includes(key))) throw new Error("Unknown operation fields.");
    if (op.id !== undefined && (typeof op.id !== "string" || !/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(op.id) || ids.has(op.id))) throw new Error("Operation IDs must be valid and unique.");
    if (op.id) ids.add(op.id);
    if (op.tags !== undefined && (!Array.isArray(op.tags) || op.tags.length > 20 || op.tags.some((t) => typeof t !== "string" || !/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(t)))) throw new Error("Operation tags are invalid.");
    const p = op.parameters;
    if (!p || typeof p !== "object" || Array.isArray(p)) throw new Error("Operation parameters must be an object.");
    const allowed = op.capability === "transform.set" ? ["x","y","z","rotation_degrees","scale_x","scale_y","scale_z"] : ["content","font_family","font_file","font_size","alignment","fill",...(op.capability === "text.create" ? ["x","y","z"] : [])];
    if (Object.keys(p).some((key) => !allowed.includes(key))) throw new Error("Unsupported operation parameters.");
    if (payload.adapter !== "blender" && ["z","scale_z","font_file"].some((key) => key in p)) throw new Error("This operation requires Blender-specific parameters.");
    if (op.capability === "text.create" && !("content" in p)) throw new Error("Text creation needs content.");
    if ("content" in p && (typeof p.content !== "string" || !p.content.length || p.content.length > 10000)) throw new Error("Text content must contain 1–10,000 characters.");
    if ("font_family" in p && typeof p.font_family !== "string") throw new Error("Font family must be text.");
    if ("font_file" in p && (typeof p.font_file !== "string" || !/^(?:\/|[A-Za-z]:[\\/])/.test(p.font_file))) throw new Error("Font files require an absolute local path.");
    if ("alignment" in p && !["left","center","right"].includes(p.alignment)) throw new Error("Text alignment is invalid.");
    if ("fill" in p && !/^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$/.test(p.fill)) throw new Error("Fill must be a hex color.");
    for (const key of ["x","y","z","rotation_degrees","font_size","scale_x","scale_y","scale_z"]) {
      if (key in p && (typeof p[key] !== "number" || !Number.isFinite(p[key]) || Math.abs(p[key]) > 1000000 || (["font_size","scale_x","scale_y","scale_z"].includes(key) && p[key] <= 0))) throw new Error("Numeric parameters are outside supported bounds.");
    }
  });
  if (payload.coordinate_space !== undefined) {
    const c=payload.coordinate_space;
    if (!c || typeof c!=="object" || Array.isArray(c) || Object.keys(c).some((k)=>!["unit","origin","y_axis","dpi","width","height"].includes(k))) throw new Error("Coordinate space is invalid.");
    if (!["px","pt","mm","cm","in","blender-unit"].includes(c.unit ?? "px") || !["top-left","bottom-left","center"].includes(c.origin ?? "top-left") || !["up","down"].includes(c.y_axis ?? "down")) throw new Error("Coordinate space conventions are invalid.");
    for (const k of ["dpi","width","height"]) if (k in c && (typeof c[k]!=="number" || !Number.isFinite(c[k]) || c[k]<=0 || c[k]>1000000)) throw new Error("Coordinate dimensions are invalid.");
    if (c.origin && c.origin!=="top-left" && (!("width" in c)||!("height" in c))) throw new Error("This origin requires width and height.");
  }
  return structuredClone(payload);
}
export function reviewOperations(operations, hasInput=false) {
  const created=new Set(), findings=[];
  operations.forEach((op,index)=>{
    if(op.capability==="text.create") {
      if(created.has(op.target)) findings.push({level:"error",operation:index+1,message:"A text target is created twice."});
      created.add(op.target);
    } else if(!created.has(op.target)) findings.push({level:hasInput?"warning":"error",operation:index+1,message:hasInput?"Verify this target in the input document.":"This target is not created earlier in the plan."});
  });
  return findings;
}
export function changeQueue(queue,index,action,value) {
  const next=structuredClone(queue);
  if(index<0||index>=next.length) throw new Error("Operation no longer exists.");
  if(action==="remove") next.splice(index,1);
  else if(action==="up" && index>0) [next[index-1],next[index]]=[next[index],next[index-1]];
  else if(action==="down" && index<next.length-1) [next[index+1],next[index]]=[next[index],next[index+1]];
  else if(action==="replace") next[index]=structuredClone(value);
  return next;
}
