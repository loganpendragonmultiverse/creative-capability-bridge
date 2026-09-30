import { CAPABILITIES, buildPlan, makeTextOperation, makeTransformOperation, validatePlanPayload, reviewOperations, changeQueue } from "./core.js";
const form=document.querySelector("#plan-form"), operationsList=document.querySelector("#operations"),output=document.querySelector("#plan-output"),status=document.querySelector("#status"),adapter=document.querySelector("#adapter"),outputPath=document.querySelector("#output-path"),zFields=document.querySelectorAll("[data-3d]");
let operations=[], extra={}, undo=[], redo=[], editing=-1, previousAdapter=adapter.value;
const values=()=>Object.fromEntries(new FormData(form).entries());
const snapshot=()=>({operations:structuredClone(operations),extra:structuredClone(extra),adapter:adapter.value,input:form.elements.input.value,output:outputPath.value});
function remember(){editing=-1;document.querySelector("#operation-editor").hidden=true;undo.push(snapshot());if(undo.length>50)undo.shift();redo=[];}
function restore(s){editing=-1;document.querySelector("#operation-editor").hidden=true;operations=s.operations;extra=s.extra;adapter.value=s.adapter;previousAdapter=s.adapter;form.elements.input.value=s.input;outputPath.value=s.output;updateAdapter();render();}
function announce(message,kind="ok"){status.textContent=message;status.dataset.kind=kind;}
function currentPlan(){return validatePlanPayload({...buildPlan(values(),operations),...extra});}
function updateAdapter(){zFields.forEach(f=>{f.hidden=CAPABILITIES[adapter.value].dimensions!==3;});document.querySelector("#transport").textContent=CAPABILITIES[adapter.value].transport;}
function render(){
 operationsList.replaceChildren();
 operations.forEach((operation,index)=>{
  const item=document.createElement("li"),label=document.createElement("span"),title=document.createElement("strong"),detail=document.createElement("small");title.textContent=operation.capability;detail.textContent=operation.target;label.append(title,detail);item.append(label);
  for(const [text,action] of [["↑","up"],["↓","down"],["Edit","edit"],["Remove","remove"]]){
   const button=document.createElement("button");button.type="button";button.textContent=text;button.setAttribute("aria-label",text+" operation "+(index+1));button.disabled=(action==="up"&&index===0)||(action==="down"&&index===operations.length-1);
   button.addEventListener("click",()=>{if(action==="edit"){editing=index;document.querySelector("#operation-editor").hidden=false;document.querySelector("#operation-json").value=JSON.stringify(operation,null,2);document.querySelector("#operation-json").focus();return;}remember();operations=changeQueue(operations,index,action);render();});item.append(button);
  }
  operationsList.append(item);
 });
 document.querySelector("#undo").disabled=!undo.length;document.querySelector("#redo").disabled=!redo.length;
 try{const plan=currentPlan();output.textContent=JSON.stringify(plan,null,2);const findings=reviewOperations(operations,Boolean(plan.input));document.querySelector("#plan-review").textContent=findings.length?findings.map(f=>f.level+" · operation "+f.operation+": "+f.message).join("\n"):"No queue-order findings. Validate with the CLI before execution.";}
 catch(e){output.textContent=e.message;document.querySelector("#plan-review").textContent="The current plan needs correction before download.";}
}
adapter.addEventListener("change",()=>{
 const next=adapter.value;adapter.value=previousAdapter;
 const old=snapshot();adapter.value=next;
 if(operations.length){try{validatePlanPayload({...buildPlan({...values(),output:CAPABILITIES[next].output},operations),...extra});}catch(e){adapter.value=previousAdapter;announce(e.message+" Keep the current adapter or edit those operations first.","error");return;}}
 editing=-1;document.querySelector("#operation-editor").hidden=true;undo.push(old);if(undo.length>50)undo.shift();redo=[];previousAdapter=next;outputPath.value=CAPABILITIES[next].output;updateAdapter();render();
});
for(const [id,maker] of [["#add-text",makeTextOperation],["#add-transform",makeTransformOperation]]) document.querySelector(id).addEventListener("click",()=>{
 try{const op=maker(values());validatePlanPayload({...buildPlan(values(),[...operations,op]),...extra});remember();operations.push(op);announce("Operation added.");render();}catch(e){announce(e.message,"error");}
});
document.querySelector("#save-operation").addEventListener("click",()=>{
 try{const op=JSON.parse(document.querySelector("#operation-json").value),next=changeQueue(operations,editing,"replace",op);validatePlanPayload({...buildPlan(values(),next),...extra});remember();operations=next;editing=-1;document.querySelector("#operation-editor").hidden=true;announce("Operation updated.");render();}catch(e){announce(e.message,"error");}
});
document.querySelector("#cancel-operation").addEventListener("click",()=>{editing=-1;document.querySelector("#operation-editor").hidden=true;});
document.querySelector("#undo").addEventListener("click",()=>{if(undo.length){redo.push(snapshot());restore(undo.pop());announce("Queue change undone.");}});
document.querySelector("#redo").addEventListener("click",()=>{if(redo.length){undo.push(snapshot());restore(redo.pop());announce("Queue change restored.");}});
document.querySelector("#import-plan").addEventListener("change",async(event)=>{
 const file=event.target.files?.[0];if(!file)return;
 try{if(file.size>1000000)throw new Error("Plans must be smaller than 1 MB.");const plan=validatePlanPayload(JSON.parse(await file.text()));remember();operations=plan.operations;extra=plan.coordinate_space?{coordinate_space:plan.coordinate_space}:{};adapter.value=plan.adapter;previousAdapter=plan.adapter;form.elements.input.value=plan.input??"";outputPath.value=plan.output;updateAdapter();announce("Imported plan for review. No document was executed.");render();}
 catch(e){announce(e.message,"error");}finally{event.target.value="";}
});
document.querySelector("#download").addEventListener("click",()=>{
 try{const plan=currentPlan();if(reviewOperations(plan.operations,Boolean(plan.input)).some(f=>f.level==="error"))throw new Error("Resolve the queue-order errors before downloading.");const blob=new Blob([JSON.stringify(plan,null,2)+"\n"],{type:"application/json"}),link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download="creative-capability-plan.json";link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);announce("Plan downloaded. Run ccb preflight and ccb validate before execution.");}catch(e){announce(e.message,"error");}
});
form.addEventListener("submit",e=>e.preventDefault());
form.addEventListener("input",render);
updateAdapter();render();
