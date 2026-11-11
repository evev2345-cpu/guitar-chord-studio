// Execute the actual app.js display selector at unchanged default controls.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=require('node:path').resolve(__dirname,'../..'),mode=process.argv[2]||'github';
const run=process.env.GCS_EVAL_RUN||root+'/evaluation/runs/current_20261111_v1';
const source=mode==='github'?run+'/github_source':root;
const elements=new Map();
function element(key){if(!elements.has(key))elements.set(key,{value:key==='#capo'?'0':key==='#notation'?'concert':'0.2',checked:['#onset','#context','#beat-grid'].includes(key),textContent:'',classList:{add(){},remove(){},toggle(){}},addEventListener(){},replaceChildren(){},append(){}});return elements.get(key);}
const c=vm.createContext({document:{querySelector:element,createElement:()=>element('new')},fetch:async()=>({ok:true,json:async()=>[]}),setTimeout,requestAnimationFrame(){}});
vm.runInContext(fs.readFileSync(source+'/chord_studio_v2/static/app.js','utf8'),c);
const rows=JSON.parse(fs.readFileSync(run+'/'+mode+'/ui_audit/sample.json'));
for(const row of rows){c.row=row;const actual=vm.runInContext('display(row)',c);assert.equal(JSON.stringify(actual),JSON.stringify(row.onset_presentation.display_candidates));}
console.log(mode+': '+rows.length+' actual UI-default samples exactly match backend B; manual BPM/edit/vision overrides excluded.');
