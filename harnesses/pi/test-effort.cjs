// Run after compiling effort-adapter.ts into a temporary output directory.
const assert = require('node:assert/strict');
const {applyEffort, registerEffortHook} = require(process.argv[2]);
let effort='low', stopped=false, entries=[], callback;
const pi={setThinkingLevel:v=>effort=v,getThinkingLevel:()=>effort,
  appendEntry:(k,d)=>entries.push(d),on:(event,cb)=>{assert.equal(event,'turn_start');callback=cb}};
const ctx={model:{id:'gpt-6-luna'},abort:()=>{stopped=true}};
const b={session:'fixture',model:'gpt-6-luna',epoch:1,generation:0,allowed:['low','high'],qualified:true};
const d={...b,effort:'high',decisionId:'synthetic-1'};
applyEffort(pi,ctx,b,d);assert.equal(effort,'high');assert.equal(entries.length,1);
assert.throws(()=>applyEffort(pi,ctx,b,{...d,session:'other'}));assert.equal(stopped,true);
stopped=false;pi.setThinkingLevel=()=>{effort='low'};
assert.throws(()=>applyEffort(pi,ctx,b,d));assert.equal(stopped,true);assert.equal(entries.length,1);
pi.setThinkingLevel=v=>effort=v;
(async()=>{
 let binding={...b};stopped=false;
 registerEffortHook(pi,()=>binding,async()=>{binding={...b,epoch:2};return d});
 await assert.rejects(callback({},ctx));assert.equal(stopped,true);
 console.log('PASS: Pi adapter apply, stale binding, clamp and awaited re-observation (structural fixtures only)');
})().catch(e=>{console.error(e);process.exitCode=1});
