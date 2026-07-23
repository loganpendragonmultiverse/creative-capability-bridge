import { CAPABILITIES, buildPlan, makeTextOperation, makeTransformOperation } from "./core.js";

const form = document.querySelector("#plan-form");
const operationsList = document.querySelector("#operations");
const output = document.querySelector("#plan-output");
const status = document.querySelector("#status");
const adapter = document.querySelector("#adapter");
const outputPath = document.querySelector("#output-path");
const zFields = document.querySelectorAll("[data-3d]");
let operations = [];

function values() {
  return Object.fromEntries(new FormData(form).entries());
}

function announce(message, kind = "ok") {
  status.textContent = message;
  status.dataset.kind = kind;
}

function render() {
  operationsList.replaceChildren();
  operations.forEach((operation, index) => {
    const item = document.createElement("li");
    item.innerHTML = `<span><strong>${operation.capability}</strong><small>${operation.target}</small></span>`;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => {
      operations.splice(index, 1);
      render();
    });
    item.append(remove);
    operationsList.append(item);
  });
  try {
    const plan = buildPlan(values(), operations);
    output.textContent = JSON.stringify(plan, null, 2);
  } catch {
    output.textContent = "Add an operation to generate a plan.";
  }
}

adapter.addEventListener("change", () => {
  const selected = CAPABILITIES[adapter.value];
  outputPath.value = selected.output;
  zFields.forEach((field) => { field.hidden = selected.dimensions !== 3; });
  document.querySelector("#transport").textContent = selected.transport;
  render();
});

document.querySelector("#add-text").addEventListener("click", () => {
  try {
    operations.push(makeTextOperation(values()));
    announce("Text operation added.");
    render();
  } catch (error) {
    announce(error.message, "error");
  }
});

document.querySelector("#add-transform").addEventListener("click", () => {
  try {
    operations.push(makeTransformOperation(values()));
    announce("Transform operation added.");
    render();
  } catch (error) {
    announce(error.message, "error");
  }
});

document.querySelector("#download").addEventListener("click", () => {
  try {
    const plan = buildPlan(values(), operations);
    const blob = new Blob([`${JSON.stringify(plan, null, 2)}\n`], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "creative-capability-plan.json";
    link.click();
    URL.revokeObjectURL(link.href);
    announce("Plan downloaded. Validate it with ccb validate before execution.");
  } catch (error) {
    announce(error.message, "error");
  }
});

form.addEventListener("input", render);
adapter.dispatchEvent(new Event("change"));

