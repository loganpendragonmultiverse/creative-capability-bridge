import assert from "node:assert/strict";
import test from "node:test";
import { buildPlan, makeTextOperation, makeTransformOperation, normalizeNumber } from "../site/core.js";

test("buildPlan creates the canonical envelope", () => {
  const operation = { capability: "text.create", target: "title", parameters: { content: "Hi" } };
  assert.deepEqual(buildPlan({ adapter: "inkscape", input: "", output: "out.svg" }, [operation]), {
    version: 1, adapter: "inkscape", input: null, output: "out.svg", operations: [operation]
  });
});

test("buildPlan rejects empty operations", () => {
  assert.throws(() => buildPlan({ adapter: "inkscape", output: "out.svg" }, []), /operation/);
});

test("text operation includes z only for Blender", () => {
  const base = { target: "title", content: "Hello", fontSize: "40", x: "2", y: "3", z: "4" };
  assert.equal(makeTextOperation({ ...base, adapter: "blender" }).parameters.z, 4);
  assert.equal("z" in makeTextOperation({ ...base, adapter: "inkscape" }).parameters, false);
});

test("transform defaults are deterministic", () => {
  const operation = makeTransformOperation({ adapter: "inkscape", target: "title" });
  assert.deepEqual(operation.parameters, { x: 0, y: 0, rotation_degrees: 0, scale_x: 1, scale_y: 1 });
});

test("numeric validation rejects non-finite values", () => {
  assert.equal(normalizeNumber("", 7), 7);
  assert.throws(() => normalizeNumber("not-a-number", 0), /finite/);
});

