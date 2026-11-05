// Pure JS contract checks; no browser rendering or browser access involved.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map();
function element(key){if(!elements.has(key))elements.set(key,{value:key==='#capo'?'1':key==='#notation'?'shape':'0.2',textContent:'',classList:{add(){},remove(){},toggle(){}},addEventListener(){},replaceChildren(){},append(){}});return elements.get(key);}
const context=vm.createContext({document:{querySelector:element,createElement:()=>element('new')},fetch:async()=>({ok:true,json:async()=>[]}),setTimeout,requestAnimationFrame:()=>{}});
vm.runInContext(fs.readFileSync('webapp/static/app.js','utf8'),context);
const evaluate=code=>vm.runInContext(code,context);
assert.equal(evaluate("label({root_pc:0,symbol:'C6',quality:'6'})"),'B6');
assert.equal(evaluate("label({root_pc:9,symbol:'Am7',quality:'m7'})"),'G#m7');
assert.equal(evaluate("label({root_pc:1,symbol:'Dbm7',quality:'m7'})"),'Cm7');
assert.equal(evaluate("display({top3:[{root_pc:0,quality:'6',score:1},{root_pc:9,quality:'m7',score:1}],tied_top1_count:2,display:{display_candidate:{root_pc:0}}}).length"),2);
assert.equal(evaluate("display({top3:[],tied_top1_count:0,display:{display_candidate:null}}).length"),0);
console.log('5 frontend contract checks passed (rendering unverified).');
