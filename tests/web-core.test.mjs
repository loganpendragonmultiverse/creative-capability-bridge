import assert from "node:assert/strict";
import test from "node:test";
import { CAPABILITIES, buildPlan, makeTextOperation, makeTransformOperation, normalizeNumber } from "../site/core.js";

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
  assert.equal("z" in makeTextOperation({ ...base, adapter: "gimp" }).parameters, false);
});

test("GIMP plans use XCF output and Script-Fu transport", () => {
  assert.equal(CAPABILITIES.gimp.output, "output.xcf");
  assert.match(CAPABILITIES.gimp.transport, /Script-Fu/);
});

test("transform defaults are deterministic", () => {
  const operation = makeTransformOperation({ adapter: "inkscape", target: "title" });
  assert.deepEqual(operation.parameters, { x: 0, y: 0, rotation_degrees: 0, scale_x: 1, scale_y: 1 });
});

test("numeric validation rejects non-finite values", () => {
  assert.equal(normalizeNumber("", 7), 7);
  assert.throws(() => normalizeNumber("not-a-number", 0), /finite/);
});

import { validatePlanPayload, reviewOperations, changeQueue } from "../site/core.js";
const reviewedPlan=()=>({version:1,adapter:"inkscape",input:null,output:"out.svg",operations:[{id:"create",capability:"text.create",target:"title",parameters:{content:"Hello"}}]});
test("plan import retains coordinates and metadata without mutating input",()=>{const p=reviewedPlan();p.coordinate_space={unit:"mm",origin:"top-left",dpi:96};const loaded=validatePlanPayload(p);assert.deepEqual(loaded,p);loaded.operations[0].parameters.content="Changed";assert.equal(p.operations[0].parameters.content,"Hello");});
test("import rejects unsafe shape, bounds, IDs and adapter mismatches",()=>{
 for(const change of [
  p=>{p.operations=[];},p=>{p.output="out.blend";},p=>{p.input="out.svg";},p=>{p.unknown=true;},
  p=>{p.operations[0].parameters.z=1;},p=>{p.operations[0].parameters.content="";},
  p=>{p.operations[0].parameters.font_size=-2;},p=>{p.operations[0].parameters.x=Infinity;},
  p=>{p.operations[0].parameters.fill="red";},p=>{p.operations[0].target="<script>";},
  p=>{p.operations.push(structuredClone(p.operations[0]));},p=>{p.coordinate_space={origin:"center"};},
  p=>{p.operations[0].tags=[123];},p=>{p.operations[0].parameters.bad=true;},
  p=>{p.operations[0].capability="shell.run";},
 ]){const p=reviewedPlan();change(p);assert.throws(()=>validatePlanPayload(p));}
 assert.throws(()=>validatePlanPayload(null));
 const p=reviewedPlan();p.adapter="blender";p.output="out.blend";p.operations[0].parameters.font_file="C:\\Fonts\\font.ttf";assert.equal(validatePlanPayload(p).adapter,"blender");
});
test("queue review distinguishes existing input targets from missing new targets",()=>{
 const p=reviewedPlan(), transform={capability:"transform.set",target:"title",parameters:{x:5}};
 assert.deepEqual(reviewOperations([...p.operations,transform]),[]);
 assert.equal(reviewOperations([transform])[0].level,"error");
 assert.equal(reviewOperations([transform],true)[0].level,"warning");
 assert.equal(reviewOperations([...p.operations,...p.operations])[0].level,"error");
});
test("queue edits reorder copies and preserve original operations",()=>{
 const q=[{target:"one"},{target:"two"}];assert.equal(changeQueue(q,1,"up")[0].target,"two");assert.equal(changeQueue(q,0,"down")[1].target,"one");assert.equal(changeQueue(q,0,"remove").length,1);assert.equal(changeQueue(q,0,"replace",{target:"new"})[0].target,"new");assert.equal(q[0].target,"one");assert.throws(()=>changeQueue(q,8,"remove"));
});

test("import rejects inherited adapters and coerced targets", () => {
 const p={version:1,adapter:"toString",input:null,output:"undefined",operations:[{capability:"text.create",target:"title",parameters:{content:"text"}}]};
 assert.throws(()=>validatePlanPayload(p));p.adapter="inkscape";p.output="out.svg";p.operations[0].target=true;assert.throws(()=>validatePlanPayload(p));
});
