'use strict';
const $=s=>document.querySelector(s), player=$('#player');
const names=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
const QUALITY_SUFFIX={major:'',minor:'m',dim:'dim',aug:'aug',sus2:'sus2',sus4:'sus4','6':'6',m6:'m6','7':'7',maj7:'maj7',m7:'m7',m7b5:'m7b5',add9:'add9'};
const QUALITY_PCS={major:[0,4,7],minor:[0,3,7],dim:[0,3,6],aug:[0,4,8],sus2:[0,2,7],sus4:[0,5,7],'6':[0,4,7,9],m6:[0,3,7,9],'7':[0,4,7,10],maj7:[0,4,7,11],m7:[0,3,7,10],m7b5:[0,3,6,10],add9:[0,4,7,2]};
const QUALITY_PREF={major:3.0,minor:3.0,m7:2.7,'7':2.6,maj7:2.5,sus4:1.4,add9:1.0,sus2:0.8,'6':0.5,m6:0.5,dim:0.2,aug:0.2,m7b5:0.2};
let result=null,currentJob=null,rows=[],segments=[],loading=false,selection=0,lastRendered=-1;
let visionOverlay=[],timelinePxPerSec=56;
let calibratingMode=false,calibPoints=[],userCalibratedCorners=null,usingGuitarStem=false;
let perspectiveK=0.0,dragTarget=null,hoveredTarget=null;

const clock=t=>`${String(Math.floor(t/60)).padStart(2,'0')}:${String(Math.floor(t%60)).padStart(2,'0')}`;
function label(c,shape=$('#notation')?.value==='shape'){
  if(!c)return '—';
  const base=c.base_symbol||(c.symbol?c.symbol.split('/')[0]:names[c.root_pc]+(QUALITY_SUFFIX[c.quality]??''))||'';
  const offset=shape?Number($('#capo')?.value||0):0;
  const root=(c.root_pc-offset+12)%12,bass=Number.isInteger(c.bass_pc)?(c.bass_pc-offset+12)%12:null;
  return names[root]+base.slice(names[c.root_pc].length)+(bass!==null&&bass!==root?'/'+names[bass]:'');
}
let clientId='';try{clientId=localStorage.getItem('chord_studio_client_id')||'';if(!clientId){clientId='c_'+Math.random().toString(36).slice(2,10)+Date.now().toString(36);localStorage.setItem('chord_studio_client_id',clientId);}}catch(e){clientId='c_anon';}
async function api(url,options={}){const opt={...options};opt.headers={...(opt.headers||{}),'X-Client-Id':clientId};const response=await fetch(url,opt);const data=await response.json();if(!response.ok)throw Error(data.error||'요청에 실패했습니다.');return data;}
function notice(text=''){$('#notice').textContent=text;}
function busy(value){loading=value;if($('#demo'))$('#demo').disabled=value;$('#file').disabled=value;}
function identity(c){return c?`${c.root_pc}:${c.quality}:${c.bass_pc??c.root_pc}`:'none';}
function fullKey(cands){return (cands||[]).map(identity).sort().join('|');}
function activeContext(row){if($('#vision').checked){const v=$('#onset').checked?row.vision_onset_context:row.vision_context;if(v)return v;}return $('#onset').checked&&row.onset_context?row.onset_context:row.context;}
function activePresentation(row){if($('#vision').checked){const v=$('#onset').checked?row.vision_onset_presentation:row.vision_presentation;if(v)return v;}return $('#onset').checked&&row.onset_presentation?row.onset_presentation:row.presentation;}
function basePresentationCandidates(row){
  const p=activePresentation(row);
  if(!p)return activeContext(row)?.display_candidates||[];
  if(p.status==='user_edited_segment')return p.display_candidates||[];
  return p.frame_display_candidates||p.display_candidates||[];
}
function resolveSingleCandidate(cands,leftC,rightC,songCounts,rootCounts,frameIdxs,targetRows){
  if(!cands||cands.length<=1)return cands;
  const obsBass=[];
  frameIdxs.forEach(fi=>{const pc=targetRows[fi]?.context?.bass?.pc;if(Number.isInteger(pc))obsBass.push(pc);});
  let best=cands[0],bestSc=-1e9;
  cands.forEach(c=>{
    const cid=`${c.root_pc}:${c.quality}`,root=c.root_pc;
    let sc=(QUALITY_PREF[c.quality]??0.5)+0.35*Math.min(songCounts.get(cid)||0,15)+0.10*Math.min(rootCounts.get(root)||0,20);
    if(leftC){
      if(leftC.root_pc===root&&leftC.quality===c.quality)sc+=10;
      else if(leftC.root_pc===root)sc+=4;
      else if((leftC.root_pc-root+12)%12===7)sc+=6;
      else if([5,7].includes((root-leftC.root_pc+12)%12))sc+=1.5;
    }
    if(rightC){
      if(rightC.root_pc===root&&rightC.quality===c.quality)sc+=10;
      else if(rightC.root_pc===root)sc+=4;
      else if((root-rightC.root_pc+12)%12===7)sc+=3;
    }
    if(obsBass.length)sc+=2.5*(obsBass.filter(pc=>pc===root).length/obsBass.length);
    sc+=(c.adjusted_score??c.score??0)*0.1;
    if(sc>bestSc){bestSc=sc;best=c;}
  });
  return [best];
}
function quantizeRowsToBeatGrid(targetRows,bpm,offsetS=0){
  if(!targetRows?.length||!(bpm>0))return;
  const sixteenthS=60/Number(bpm)/4,origin=((Number(offsetS)||0)%sixteenthS+sixteenthS)%sixteenthS;
  const slotMap=new Map(),uniqueSlots=[];
  targetRows.forEach((row,i)=>{
    const k=Math.floor((row.time_s-origin+1e-9)/sixteenthS);
    if(!slotMap.has(k)){slotMap.set(k,[]);uniqueSlots.push(k);}
    slotMap.get(k).push(i);
  });
  const slotCands=[],slotFrames=[],slotLowInv=[];
  uniqueSlots.forEach(k=>{
    const idxs=slotMap.get(k);slotFrames.push(idxs);
    const votes=new Map(),rep=new Map();
    idxs.forEach(i=>{
      const cands=basePresentationCandidates(targetRows[i]);
      if(!cands?.length)return;
      const isUserEdit=cands.some(c=>c.user_edited);
      const fk=fullKey(cands),w=(isUserEdit?100:Math.max(...cands.map(c=>c.score??0.8),0.8))+(cands.length===1?0.15:0);
      votes.set(fk,(votes.get(fk)||0)+w);
      if(!rep.has(fk)||cands.length<rep.get(fk).length)rep.set(fk,cands);
    });
    let bestFk='',bestW=-1;
    votes.forEach((w,fk)=>{if(w>bestW){bestW=w;bestFk=fk;}});
    const chosen=bestFk?rep.get(bestFk):[];
    slotCands.push(chosen);
    slotLowInv.push(chosen.some(c=>(c.bass_display_status==='low_string_below_root_inversion'&&String(c.symbol||'').includes('/'))||c.user_edited));
  });
  function slotRuns(seq){
    const r=[];let s=0;
    for(let i=1;i<=seq.length;i++){if(i===seq.length||fullKey(seq[i])!==fullKey(seq[s])){r.push([s,i]);s=i;}}
    return r;
  }
  const songCounts=new Map(),rootCounts=new Map();
  slotCands.forEach(cands=>{
    if(cands.length===1){
      const c=cands[0],cid=`${c.root_pc}:${c.quality}`;
      songCounts.set(cid,(songCounts.get(cid)||0)+1);
      rootCounts.set(c.root_pc,(rootCounts.get(c.root_pc)||0)+1);
    }
  });
  let rlist=slotRuns(slotCands);
  rlist.forEach(([s,e],rIdx)=>{
    if(slotCands[s].length>1){
      let leftC=null,rightC=null;
      for(let l=rIdx-1;l>=0;l--){if(slotCands[rlist[l][0]].length===1){leftC=slotCands[rlist[l][0]][0];break;}}
      for(let n=rIdx+1;n<rlist.length;n++){if(slotCands[rlist[n][0]].length===1){rightC=slotCands[rlist[n][0]][0];break;}}
      const fIdxs=[];for(let j=s;j<e;j++)fIdxs.push(...slotFrames[j]);
      const resolved=resolveSingleCandidate(slotCands[s],leftC,rightC,songCounts,rootCounts,fIdxs,targetRows);
      for(let j=s;j<e;j++)slotCands[j]=resolved;
    }
  });
  slotRuns(slotCands).forEach(([s,e])=>{if(!slotCands[s].length&&s>0&&(e-s)<=3&&slotCands[s-1].length){for(let j=s;j<e;j++)slotCands[j]=slotCands[s-1];}});
  rlist=slotRuns(slotCands);
  rlist.forEach(([s,e],rIdx)=>{
    const spanLen=e-s;
    if(!slotCands[s].length||spanLen>3||slotLowInv.slice(s,e).some(Boolean))return;
    const prevEmpty=rIdx===0||!slotCands[rlist[rIdx-1][0]].length;
    const nextEmpty=rIdx+1===rlist.length||!slotCands[rlist[rIdx+1][0]].length;
    if(!prevEmpty)return;
    const c0=slotCands[s][0],fIdxs=[];
    for(let j=s;j<e;j++)fIdxs.push(...slotFrames[j]);
    const rawHits=fIdxs.filter(fi=>(targetRows[fi].top3||[]).some(c=>c.root_pc===c0.root_pc&&c.quality===c0.quality)).length;
    const rawRatio=fIdxs.length?rawHits/fIdxs.length:0,sc0=c0.score??0;
    if(nextEmpty){
      if(['aug','dim','m7b5'].includes(c0.quality)||rawRatio<=0.65||sc0<0.78){for(let j=s;j<e;j++)slotCands[j]=[];}
    }else if(rawRatio<0.50||(sc0<0.75&&rawRatio<=0.65)){
      for(let j=s;j<e;j++)slotCands[j]=[];
    }
  });
  for(let pass=0;pass<2;pass++){
    rlist=slotRuns(slotCands);
    for(let r=0;r<rlist.length;r++){
      const [s,e]=rlist[r];
      if(!slotCands[s].length||(e-s)>2||slotLowInv.slice(s,e).some(Boolean))continue;
      const roots=new Set(slotCands[s].map(c=>c.root_pc));
      const sameRoots=other=>other.length&&other.every(c=>roots.has(c.root_pc))&&other.length===roots.size;
      if(r>0&&(rlist[r-1][1]-rlist[r-1][0])>=3&&!slotLowInv.slice(rlist[r-1][0],rlist[r-1][1]).some(Boolean)&&sameRoots(slotCands[rlist[r-1][0]])){for(let j=s;j<e;j++)slotCands[j]=slotCands[rlist[r-1][0]];continue;}
      if(r+1<rlist.length&&(rlist[r+1][1]-rlist[r+1][0])>=3&&!slotLowInv.slice(rlist[r+1][0],rlist[r+1][1]).some(Boolean)&&sameRoots(slotCands[rlist[r+1][0]])){for(let j=s;j<e;j++)slotCands[j]=slotCands[rlist[r+1][0]];}
    }
  }
  const modeFam=q=>['minor','m7','m6','m7b5'].includes(q)?1:['dim','dim7','diminished','aug'].includes(q)?2:0;
  const offsetSlot=Math.round(((Number(offsetS)||0)-origin)/sixteenthS);
  const metWeight=sIdx=>{const m=(((uniqueSlots[sIdx]-offsetSlot)%16)+16)%16;return m===0?4:m===8?3:(m===4||m===12)?2:(m%2===0)?1:0;};
  for(let pass=0;pass<2;pass++){
    rlist=slotRuns(slotCands);let changed=false;
    for(let r=0;r<rlist.length-1;r++){
      const [s,e]=rlist[r],[rs,re]=rlist[r+1],frontLen=e-s,backLen=re-rs;
      if(!slotCands[s].length||slotCands[rs].length!==1||frontLen>6||backLen<6||slotLowInv.slice(s,re).some(Boolean))continue;
      if(r>0&&slotCands[rlist[r-1][0]].length&&metWeight(rs)>metWeight(s))continue;
      const bCand=slotCands[rs][0],bRoot=bCand.root_pc,bMode=modeFam(bCand.quality),bPcs=new Set(bCand.pcs||[]);
      const sameRoot=slotCands[s].every(c=>c.root_pc===bRoot&&modeFam(c.quality)===bMode)&&frontLen<backLen;
      const sharedPcs=frontLen<=4&&slotCands[s].some(c=>(c.pcs||[]).filter(pc=>bPcs.has(pc)).length>=3);
      const frontIdxs=[];for(let j=s;j<e;j++)frontIdxs.push(...slotFrames[j]);
      const supCount=frontIdxs.filter(fi=>[...(targetRows[fi].top3||[]),...(targetRows[fi].context?.top3||[])].some(c=>c.root_pc===bRoot&&c.quality===bCand.quality)).length;
      const supRatio=frontIdxs.length?supCount/frontIdxs.length:0;
      if(sameRoot||(sharedPcs&&supRatio>=0.70-1e-9)){for(let j=s;j<e;j++)slotCands[j]=slotCands[rs];changed=true;}
    }
    if(!changed)break;
  }
  rlist=slotRuns(slotCands);
  for(let r=0;r<rlist.length-1;r++){
    const [s,e]=rlist[r],[rs,re]=rlist[r+1];
    if(!slotCands[s].length||!slotCands[rs].length||(e-s)>6||(re-rs)<(e-s)||slotLowInv.slice(s,re).some(Boolean))continue;
    const c0=slotCands[s][0],c1=slotCands[rs][0];
    if(c0.root_pc===c1.root_pc&&modeFam(c0.quality)===modeFam(c1.quality)){
      const pick=(QUALITY_PREF[c1.quality]??0.5)>=(QUALITY_PREF[c0.quality]??0.5)?slotCands[rs]:slotCands[s];
      for(let j=s;j<re;j++)slotCands[j]=pick;
    }
  }
  for(let pass=0;pass<2;pass++){
    rlist=slotRuns(slotCands);let changed=false;
    for(let r=1;r<rlist.length;r++){
      const [ls,le]=rlist[r-1],[s,e]=rlist[r],mainLen=le-ls,tailLen=e-s;
      if(slotCands[ls].length!==1||!slotCands[s].length||mainLen<5||tailLen>5||tailLen>mainLen||slotLowInv.slice(s,e).some(Boolean))continue;
      const mainRoot=slotCands[ls][0].root_pc,mainMode=modeFam(slotCands[ls][0].quality);
      if(slotCands[s].every(c=>c.root_pc===mainRoot&&modeFam(c.quality)===mainMode)){for(let j=s;j<e;j++)slotCands[j]=slotCands[ls];changed=true;}
    }
    if(!changed)break;
  }
  rlist=slotRuns(slotCands);
  for(let r=0;r<rlist.length-1;r++){
    const [s,e]=rlist[r],[rs,re]=rlist[r+1];
    if(!slotCands[s].length||!slotCands[rs].length||(e-s)>6||(re-rs)<(e-s)||slotLowInv.slice(s,re).some(Boolean))continue;
    const c0=slotCands[s][0],c1=slotCands[rs][0];
    if(c0.root_pc===c1.root_pc&&modeFam(c0.quality)===modeFam(c1.quality)){
      const pick=(QUALITY_PREF[c1.quality]??0.5)>=(QUALITY_PREF[c0.quality]??0.5)?slotCands[rs]:slotCands[s];
      for(let j=s;j<re;j++)slotCands[j]=pick;
    }
  }
  rlist=slotRuns(slotCands);
  for(let r=1;r<rlist.length-1;r++){
    const [ls,le]=rlist[r-1],[s,e]=rlist[r],[rs,re]=rlist[r+1];
    if((e-s)<=2&&slotCands[ls].length&&slotCands[rs].length&&!slotLowInv.slice(s,e).some(Boolean)){
      const lRoot=slotCands[ls][0].root_pc,rRoot=slotCands[rs][0].root_pc,sRoot=slotCands[s][0]?.root_pc??-1;
      const lMode=modeFam(slotCands[ls][0].quality),rMode=modeFam(slotCands[rs][0].quality);
      if(lRoot===rRoot&&lMode===rMode&&(fullKey(slotCands[ls])===fullKey(slotCands[rs])||sRoot!==lRoot)){
        const pick=(le-ls)>=(re-rs)?slotCands[ls]:slotCands[rs];
        for(let j=s;j<e;j++)slotCands[j]=pick;
      }
    }
  }
  rlist=slotRuns(slotCands);
  let cIdx=0;
  while(cIdx<rlist.length){
    const [s0,e0]=rlist[cIdx];
    if(!slotCands[s0].length||(e0-s0)>4||slotLowInv.slice(s0,e0).some(Boolean)){cIdx++;continue;}
    const root0=slotCands[s0][0].root_pc,mode0=modeFam(slotCands[s0][0].quality);
    let endIdx=cIdx+1;
    while(endIdx<rlist.length){
      const [sn,en]=rlist[endIdx];
      if(!slotCands[sn].length||(en-sn)>4||slotCands[sn][0].root_pc!==root0||modeFam(slotCands[sn][0].quality)!==mode0||slotLowInv.slice(sn,en).some(Boolean))break;
      endIdx++;
    }
    if(endIdx-cIdx>=2){
      const lens=[];for(let k=cIdx;k<endIdx;k++)lens.push(rlist[k][1]-rlist[k][0]);
      if(Math.min(...lens)<=4){
        const weights=new Map(),reps=new Map();
        for(let k=cIdx;k<endIdx;k++){
          const [sk,ek]=rlist[k],c=slotCands[sk][0],cid=`${c.root_pc}:${c.quality}`;
          weights.set(cid,(weights.get(cid)||0)+(ek-sk)+0.6*(QUALITY_PREF[c.quality]??0.5));
          reps.set(cid,slotCands[sk]);
        }
        let bestCid='',bestW=-1;
        weights.forEach((w,cid)=>{if(w>bestW){bestW=w;bestCid=cid;}});
        const bestRep=reps.get(bestCid);
        for(let j=rlist[cIdx][0];j<rlist[endIdx-1][1];j++)slotCands[j]=bestRep;
      }
    }
    cIdx=endIdx;
  }
  function unifyDim(){
    const rl=slotRuns(slotCands);
    let dIdx=0;
    while(dIdx<rl.length){
      const [s0]=rl[dIdx];
      if(!slotCands[s0].length||!['dim','dim7','diminished'].includes(slotCands[s0][0].quality)){dIdx++;continue;}
      const axis=slotCands[s0][0].root_pc%3;
      let endIdx=dIdx+1;
      while(endIdx<rl.length){
        const [sn]=rl[endIdx];
        if(!slotCands[sn].length||!['dim','dim7','diminished'].includes(slotCands[sn][0].quality)||(slotCands[sn][0].root_pc%3)!==axis)break;
        endIdx++;
      }
      if(endIdx-dIdx>=2){
        const nextRoot=(endIdx<rl.length&&slotCands[rl[endIdx][0]].length)?slotCands[rl[endIdx][0]][0].root_pc:null;
        let bestRep=null,bestW=-1;
        for(let k=dIdx;k<endIdx;k++){
          const [sk,ek]=rl[k],c=slotCands[sk][0];
          let w=ek-sk;
          if(nextRoot!==null&&(nextRoot-c.root_pc+12)%12===1)w+=10;
          if(w>bestW){bestW=w;bestRep=slotCands[sk];}
        }
        if(bestRep){for(let j=rl[dIdx][0];j<rl[endIdx-1][1];j++)slotCands[j]=bestRep;}
      }
      dIdx=endIdx;
    }
  }
  unifyDim();
  rlist=slotRuns(slotCands);
  const isAnchor=rlist.map(([s,e])=>slotCands[s].length>0&&((e-s)>=3||(slotLowInv.slice(s,e).some(Boolean)&&(e-s)>=2)));
  let idx=0;
  while(idx<rlist.length){
    if(isAnchor[idx]||!slotCands[rlist[idx][0]].length){idx++;continue;}
    let endIdx=idx;
    while(endIdx<rlist.length&&!isAnchor[endIdx]&&slotCands[rlist[endIdx][0]].length)endIdx++;
    const spanStart=rlist[idx][0],spanEnd=rlist[endIdx-1][1],totalSlots=spanEnd-spanStart;
    const left=idx>0&&isAnchor[idx-1]?slotCands[rlist[idx-1][0]]:null;
    const right=endIdx<rlist.length&&isAnchor[endIdx]?slotCands[rlist[endIdx][0]]:null;
    if(totalSlots<=4&&!slotLowInv.slice(spanStart,spanEnd).some(Boolean)){
      if(left&&right&&fullKey(left)===fullKey(right)){
        for(let j=spanStart;j<spanEnd;j++)slotCands[j]=left;
      }else if(left&&right){
        const rightRoots=new Set(right.map(c=>c.root_pc));
        const rightFlags=[];
        for(let j=spanStart;j<spanEnd;j++){
          rightFlags.push(slotFrames[j].some(fi=>(targetRows[fi].top3||[]).slice(0,2).some(c=>rightRoots.has(c.root_pc))));
        }
        let splitOffset=totalSlots;
        while(splitOffset>0&&rightFlags[splitOffset-1])splitOffset--;
        for(let off=0;off<totalSlots;off++)slotCands[spanStart+off]=off>=splitOffset?right:left;
      }else if(left){
        for(let j=spanStart;j<spanEnd;j++)slotCands[j]=left;
      }else if(right){
        for(let j=spanStart;j<spanEnd;j++)slotCands[j]=right;
      }
    }
    idx=endIdx;
  }
  rlist=slotRuns(slotCands);
  for(let r=0;r<rlist.length;r++){
    const [s,e]=rlist[r];
    if(!slotCands[s].length||(e-s)>2||slotLowInv.slice(s,e).some(Boolean))continue;
    const roots=new Set(slotCands[s].map(c=>c.root_pc));
    const sameRoots=other=>other.length&&other.every(c=>roots.has(c.root_pc))&&other.length===roots.size;
    if(r+1<rlist.length&&(rlist[r+1][1]-rlist[r+1][0])>=3&&!slotLowInv.slice(rlist[r+1][0],rlist[r+1][1]).some(Boolean)&&sameRoots(slotCands[rlist[r+1][0]])){for(let j=s;j<e;j++)slotCands[j]=slotCands[rlist[r+1][0]];continue;}
    if(r>0&&(rlist[r-1][1]-rlist[r-1][0])>=3&&!slotLowInv.slice(rlist[r-1][0],rlist[r-1][1]).some(Boolean)&&sameRoots(slotCands[rlist[r-1][0]])){for(let j=s;j<e;j++)slotCands[j]=slotCands[rlist[r-1][0]];}
  }
  slotRuns(slotCands).forEach(([s,e])=>{if(!slotCands[s].length&&s>0&&(e-s)<=3&&slotCands[s-1].length){for(let j=s;j<e;j++)slotCands[j]=slotCands[s-1];}});
  unifyDim();
  for(let pass=0;pass<2;pass++){
    rlist=slotRuns(slotCands);
    const runReps=rlist.map(([s])=>slotCands[s]);
    let changed=false;
    for(let r=1;r<rlist.length;r++){
      const [ls,le]=rlist[r-1],[s,e]=rlist[r],lLen=le-ls,rLen=e-s;
      if(!runReps[r-1].length||!runReps[r].length||slotLowInv[s]||slotLowInv[s-1])continue;
      const mod16=(((uniqueSlots[s]-offsetSlot)%16)+16)%16;
      if((mod16===15||mod16===7)&&lLen>=2&&rLen>=3){slotCands[s]=runReps[r-1];changed=true;}
      else if((mod16===1||mod16===9)&&lLen>=3&&rLen>=2){slotCands[s-1]=runReps[r];changed=true;}
      else if(mod16===6&&lLen>=4&&rLen>=4&&s+1<slotCands.length&&!slotLowInv[s+1]){slotCands[s]=runReps[r-1];slotCands[s+1]=runReps[r-1];changed=true;}
      else if((mod16===2||mod16===10)&&lLen>=6&&rLen>=4&&(lLen%8)===2&&s>=2&&!slotLowInv[s-2]){slotCands[s-2]=runReps[r];slotCands[s-1]=runReps[r];changed=true;}
      else if(mod16===14&&lLen>=4&&rLen>=6&&s+1<slotCands.length&&!slotLowInv[s+1]){
        const lRoot=runReps[r-1][0].root_pc,fIdxs=[...slotFrames[s],...slotFrames[s+1]];
        const prevSup=fIdxs.some(fi=>[...(targetRows[fi].top3||[]),...(targetRows[fi].context?.top3||[])].some(c=>c.root_pc===lRoot));
        if(prevSup||rLen>=17){slotCands[s]=runReps[r-1];slotCands[s+1]=runReps[r-1];changed=true;}
      }else if((mod16===3||mod16===11)&&lLen>=2&&rLen>=3){slotCands[s]=runReps[r-1];changed=true;}
      else if((mod16===5||mod16===13)&&lLen>=3&&rLen>=2){slotCands[s-1]=runReps[r];changed=true;}
    }
    if(!changed)break;
  }
  rlist=slotRuns(slotCands);
  for(let r=0;r<rlist.length-1;r++){
    const [s,e]=rlist[r],[rs,re]=rlist[r+1];
    if(!slotCands[s].length||!slotCands[rs].length||(e-s)>6||(re-rs)<(e-s)||slotLowInv.slice(s,re).some(Boolean))continue;
    const c0=slotCands[s][0],c1=slotCands[rs][0];
    if(c0.root_pc===c1.root_pc&&modeFam(c0.quality)===modeFam(c1.quality)){
      const pick=(QUALITY_PREF[c1.quality]??0.5)>=(QUALITY_PREF[c0.quality]??0.5)?slotCands[rs]:slotCands[s];
      for(let j=s;j<re;j++)slotCands[j]=pick;
    }
  }
  slotFrames.forEach((idxs,kIdx)=>{idxs.forEach(fi=>{targetRows[fi]._grid_candidates=slotCands[kIdx];});});
}

function getVideoTransform(){
  const stage=$('.stage');
  if(!player.videoWidth||!stage)return null;
  const videoRect=player.getBoundingClientRect(),stageRect=stage.getBoundingClientRect();
  const scale=Math.min(videoRect.width/player.videoWidth,videoRect.height/player.videoHeight);
  const dx=videoRect.left-stageRect.left+(videoRect.width-player.videoWidth*scale)/2;
  const dy=videoRect.top-stageRect.top+(videoRect.height-player.videoHeight*scale)/2;
  return {scale,dx,dy,videoW:player.videoWidth,videoH:player.videoHeight};
}

function drawCornersAndGrid(ctx,corners,tf,color='#6ce7c6',isEditing=false){
  function line(pts,stroke,width=2,closed=false){
    ctx.strokeStyle=stroke;ctx.lineWidth=width;ctx.beginPath();
    pts.forEach((p,i)=>i?ctx.lineTo(tf.dx+p[0]*tf.scale,tf.dy+p[1]*tf.scale):ctx.moveTo(tf.dx+p[0]*tf.scale,tf.dy+p[1]*tf.scale));
    if(closed)ctx.closePath();ctx.stroke();
  }
  if(corners.length===4){
    line(corners,color,2,true);
    for(let s=0;s<6;s++){
      const u=0.1+0.8*s/5;
      line([
        [corners[0][0]*(1-u)+corners[3][0]*u,corners[0][1]*(1-u)+corners[3][1]*u],
        [corners[1][0]*(1-u)+corners[2][0]*u,corners[1][1]*(1-u)+corners[2][1]*u]
      ],'#7c9dca88',1.5);
    }
    const totalFrets=Math.max(12,Math.min(24,Number($('#total-frets')?.value)||20));
    const denom=1-Math.pow(2,-totalFrets/12);
    const k=perspectiveK||0.0;
    const markerFrets=[3,5,7,9,15,17,19,21];
    let prevRatio=0.0;

    for(let n=1;n<=totalFrets;n++){
      const un=(1-Math.pow(2,-n/12))/denom;
      const ratio=un<1.0?((1+k)*un/(1+k*un)):1.0;
      const top=[corners[0][0]*(1-ratio)+corners[1][0]*ratio,corners[0][1]*(1-ratio)+corners[1][1]*ratio];
      const bot=[corners[3][0]*(1-ratio)+corners[2][0]*ratio,corners[3][1]*(1-ratio)+corners[2][1]*ratio];

      const isFret12=(n===12);
      const isHovered12=isEditing&&(hoveredTarget?.type==='fret12'||dragTarget?.type==='fret12');
      const fretStroke=isFret12?(isHovered12?'#38ef7d':'#ffd700'):(n<=12?'#ffcf66aa':'#ffcf6655');
      const fretWidth=isFret12?(isHovered12?3.5:2.5):1.2;
      line([top,bot],fretStroke,fretWidth);

      // Inlay dots between frets
      if(markerFrets.includes(n)){
        const midR=(prevRatio+ratio)/2;
        const mt=[corners[0][0]*(1-midR)+corners[1][0]*midR,corners[0][1]*(1-midR)+corners[1][1]*midR];
        const mb=[corners[3][0]*(1-midR)+corners[2][0]*midR,corners[3][1]*(1-midR)+corners[2][1]*midR];
        const dx=tf.dx+((mt[0]+mb[0])/2)*tf.scale,dy=tf.dy+((mt[1]+mb[1])/2)*tf.scale;
        ctx.fillStyle='#ffffff66';ctx.beginPath();ctx.arc(dx,dy,2.5,0,Math.PI*2);ctx.fill();
      }else if(n===12){
        const midR=(prevRatio+ratio)/2;
        const mt=[corners[0][0]*(1-midR)+corners[1][0]*midR,corners[0][1]*(1-midR)+corners[1][1]*midR];
        const mb=[corners[3][0]*(1-midR)+corners[2][0]*midR,corners[3][1]*(1-midR)+corners[2][1]*midR];
        const cX1=tf.dx+(mt[0]*.62+mb[0]*.38)*tf.scale,cY1=tf.dy+(mt[1]*.62+mb[1]*.38)*tf.scale;
        const cX2=tf.dx+(mt[0]*.38+mb[0]*.62)*tf.scale,cY2=tf.dy+(mt[1]*.38+mb[1]*.62)*tf.scale;
        ctx.fillStyle='#ffffff77';ctx.beginPath();ctx.arc(cX1,cY1,2.5,0,Math.PI*2);ctx.fill();
        ctx.beginPath();ctx.arc(cX2,cY2,2.5,0,Math.PI*2);ctx.fill();

        // 12F interactive handle
        if(isEditing){
          const fx=tf.dx+((top[0]+bot[0])/2)*tf.scale,fy=tf.dy+((top[1]+bot[1])/2)*tf.scale;
          ctx.save();
          ctx.fillStyle=isHovered12?'#38ef7d':'#ffd700';
          ctx.strokeStyle='#0d1118';ctx.lineWidth=1.5;
          const bw=38,bh=17;
          ctx.beginPath();
          if(ctx.roundRect)ctx.roundRect(fx-bw/2,fy-bh/2,bw,bh,4);
          else ctx.rect(fx-bw/2,fy-bh/2,bw,bh);
          ctx.fill();ctx.stroke();
          ctx.fillStyle='#0d1118';ctx.font='bold 9px sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';
          ctx.fillText('12F ⇔',fx,fy);
          ctx.restore();
        }
      }
      prevRatio=ratio;
    }
  }else if(corners.length>1){
    line(corners,color,2,false);
  }
  corners.forEach((p,idx)=>{
    const cx=tf.dx+p[0]*tf.scale,cy=tf.dy+p[1]*tf.scale;
    const isHovered=isEditing&&(hoveredTarget?.type==='corner'&&hoveredTarget.index===idx);
    const isDragged=isEditing&&(dragTarget?.type==='corner'&&dragTarget.index===idx);
    if(isHovered||isDragged){
      ctx.beginPath();ctx.arc(cx,cy,15,0,Math.PI*2);
      ctx.fillStyle='rgba(56,239,125,0.35)';ctx.fill();
      ctx.strokeStyle='#38ef7d';ctx.lineWidth=1.5;ctx.stroke();
    }
    const r=(isHovered||isDragged)?9:7;
    ctx.fillStyle=(isHovered||isDragged)?'#38ef7d':'#ffcf66';
    ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.fill();
    ctx.strokeStyle='#0d1118';ctx.lineWidth=1.5;ctx.stroke();
    ctx.fillStyle='#0d1118';ctx.font='bold 10px sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';
    ctx.fillText(String(idx+1),cx,cy);
  });
}

function drawVision(time){
  const canvas=$('#vision-canvas');if(!canvas||!canvas.getContext)return;
  const ctx=canvas.getContext('2d'),stage=$('.stage');
  if(!stage)return;
  canvas.width=stage.clientWidth;canvas.height=stage.clientHeight;
  ctx.clearRect(0,0,canvas.width,canvas.height);
  const tf=getVideoTransform();
  if(!tf)return;
  if(calibratingMode){
    drawCornersAndGrid(ctx,calibPoints,tf,'#6ce7c6',true);
    return;
  }
  if(!$('#skeleton').checked)return;
  if(userCalibratedCorners&&!visionOverlay.length){
    drawCornersAndGrid(ctx,userCalibratedCorners,tf,'#f5bd66',false);
    return;
  }
  if(!visionOverlay.length)return;
  const fps=result.vision_config?.fps||24,index=Math.round(time*fps),obs=visionOverlay[index];
  if(!obs||Math.abs(obs.time_s-time)>.5/fps+1e-4)return;
  function line(points,color,closed=false){ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(tf.dx+p[0]*tf.scale,tf.dy+p[1]*tf.scale):ctx.moveTo(tf.dx+p[0]*tf.scale,tf.dy+p[1]*tf.scale));if(closed)ctx.closePath();ctx.stroke();}
  if(obs.corners){line(obs.corners,'#f5bd66',true);for(let s=0;s<6;s++){let u=.1+.8*s/5;line([[obs.corners[0][0]*(1-u)+obs.corners[3][0]*u,obs.corners[0][1]*(1-u)+obs.corners[3][1]*u],[obs.corners[1][0]*(1-u)+obs.corners[2][0]*u,obs.corners[1][1]*(1-u)+obs.corners[2][1]*u]],'#7c9dca88');}}
  if(obs.hand)[[0,1,2,3,4],[0,5,6,7,8],[0,9,10,11,12],[0,13,14,15,16],[0,17,18,19,20]].forEach((chain,i)=>line(chain.map(j=>obs.hand[j]),['white','cyan','lime','orange','magenta'][i]));
}

function display(row){
  if(!row)return [];
  if($('#context').checked&&row.context){
    const p=activePresentation(row);
    if(p?.status==='user_edited_segment')return p.display_candidates;
    if(row._grid_candidates!==undefined)return row._grid_candidates;
    if($('#beat-grid')&&$('#beat-grid').checked===false)return p?.frame_display_candidates||p?.display_candidates||activeContext(row).display_candidates;
    return p?.display_candidates||activeContext(row).display_candidates;
  }
  const top=row.top3,chosen=row.display.display_candidate;
  if(top.length>1&&row.tied_top1_count>1){
    const tied=top.filter(c=>Math.abs(c.score-top[0].score)<=1e-10);
    if(tied.length>1)return tied;
  }
  return chosen?[chosen]:[];
}
function signature(row){return display(row).map(identity).sort().join('|')||'none';}

function activeTempo(){
  const autoBpm=result?.tempo?.auto_bpm??result?.tempo?.bpm??120;
  const autoOffset=Number(result?.tempo?.offset_s??0);
  let bpm=Number($('#bpm')?.value);
  bpm=Number.isFinite(bpm)&&bpm>=40&&bpm<=240?bpm:autoBpm;
  let offsetS=Number($('#beat-offset')?.value);
  offsetS=Number.isFinite(offsetS)&&offsetS>=-10&&offsetS<=120?offsetS:autoOffset;
  if(Math.abs(offsetS-Number(autoOffset.toFixed(2)))<=1e-3)offsetS=autoOffset;
  return {bpm,offsetS,autoBpm,autoOffset};
}
function formatBeatPosition(timeS,bpm,offsetS){
  const sixteenthS=60/Math.max(40,bpm)/4;
  if(timeS+1e-3<offsetS){
    return {bar:0,beat:0,sub:0,text:`인트로 대기 · 1마디 시작 ${offsetS.toFixed(2)}s (${bpm} BPM)`};
  }
  const totalSixteenths=Math.floor((timeS-offsetS+1e-9)/sixteenthS);
  const bar=Math.floor(totalSixteenths/16)+1;
  const inBar=((totalSixteenths%16)+16)%16;
  const beat=Math.floor(inBar/4)+1;
  const sub=(inBar%4)+1;
  return {bar,beat,sub,text:`${bar}마디 · ${beat}박 · ${sub}칸 (${bpm} BPM)`};
}
function renderBeatRuler(durationS,bpm,offsetS,pxPerSec){
  const ruler=$('#beat-ruler'),track=$('#timeline-track');
  if(!ruler||!durationS)return;
  ruler.replaceChildren();
  if(track?.querySelectorAll)track.querySelectorAll('.bar-guide').forEach(el=>el.remove());
  const sixteenthS=60/Math.max(40,bpm)/4;
  const startSlot=Math.max(0,Math.ceil((-offsetS)/sixteenthS));
  const endSlot=Math.floor((durationS-offsetS)/sixteenthS);
  for(let k=startSlot;k<=endSlot;k++){
    const t=offsetS+k*sixteenthS;
    if(t<0||t>durationS)continue;
    const mod16=((k%16)+16)%16;
    if(mod16%2!==0)continue;
    const tick=document.createElement('div');
    const leftPx=t*pxPerSec;
    tick.style.left=`${leftPx.toFixed(1)}px`;
    if(mod16===0){
      const barNum=Math.floor(k/16)+1;
      tick.className='ruler-tick bar';
      const labelEl=document.createElement('span');
      labelEl.textContent=`${barNum}마디`;
      tick.append(labelEl);
      if(track){
        const guide=document.createElement('div');
        guide.className='bar-guide';
        guide.style.left=`${leftPx.toFixed(1)}px`;
        track.append(guide);
      }
    }else if(mod16%4===0){
      tick.className='ruler-tick beat';
    }else{
      tick.className='ruler-tick sub';
    }
    ruler.append(tick);
  }
  ruler.onclick=e=>{
    if(!ruler.getBoundingClientRect)return;
    const rect=ruler.getBoundingClientRect();
    const clickX=e.clientX-rect.left;
    player.currentTime=Math.max(0,Math.min(durationS-1e-4,clickX/pxPerSec));
    update();
  };
}

function rebuild(){
  lastRendered=-1;
  rows=result.branches?.[$('#window')?.value]||result.branches?.['0.2']||result.branches?.['0.4']||[];
  segments=[];
  const {bpm,offsetS,autoBpm,autoOffset}=activeTempo();
  if($('#bpm'))$('#bpm').value=bpm;
  if($('#beat-offset'))$('#beat-offset').value=offsetS.toFixed(2);
  const useGrid=!$('#beat-grid')||$('#beat-grid').checked!==false;
  if($('#context').checked&&useGrid&&(Math.abs(bpm-autoBpm)>1e-3||Math.abs(offsetS-autoOffset)>1e-3)){
    quantizeRowsToBeatGrid(rows,bpm,offsetS);
  }else{
    rows.forEach(r=>{delete r._grid_candidates;});
  }
  const sixteenthS=60/Math.max(40,bpm)/4;
  const dt=rows.length>1?rows[1].time_s-rows[0].time_s:1/24;
  rows.forEach((row,i)=>{
    const prev=segments.at(-1),key=signature(row),endT=Math.min(result.duration_s,row.time_s+dt);
    const edited=Boolean(display(row)[0]?.user_edited);
    if(prev&&prev.key===key)prev.end=endT;
    else{
      let startT=row.time_s;
      if(useGrid&&i>0){
        const nearGrid=offsetS+Math.round((row.time_s-offsetS)/sixteenthS)*sixteenthS;
        if(nearGrid>0&&nearGrid<result.duration_s&&Math.abs(nearGrid-row.time_s)<=dt*1.1&&(!prev||nearGrid>prev.start+1e-4)){
          startT=nearGrid;
          if(prev)prev.end=nearGrid;
        }
      }
      segments.push({key,start:startT,end:endT,row,index:i,edited});
    }
  });
  if(segments.length)segments.at(-1).end=result.duration_s;
  timelinePxPerSec=Math.max(56,1100/Math.max(1,result.duration_s));
  const totalWidth=Math.max(800,Math.round(result.duration_s*timelinePxPerSec));
  if($('#timeline-track')?.style)$('#timeline-track').style.width=`${totalWidth}px`;
  renderBeatRuler(result.duration_s,bpm,offsetS,timelinePxPerSec);
  renderLeadSheet();
  const container=$('#timeline');container.replaceChildren();
  segments.forEach(segment=>{
    const button=document.createElement('button');
    const text=display(segment.row).map(c=>label(c)).join(' / ')||'보류';
    const slots=Math.max(1,Math.round((segment.end-segment.start)/sixteenthS));
    const widthPx=Math.max(6,(segment.end-segment.start)*timelinePxPerSec);
    button.textContent=widthPx>=24?text:'·';
    button.title=`${clock(segment.start)}~${clock(segment.end)} · ${text} (${slots}칸 · ${(segment.end-segment.start).toFixed(2)}초)${segment.edited?' [사용자 수정됨]':''}`;
    button.style.width=`${widthPx.toFixed(2)}px`;
    button.classList.toggle('unknown',segment.key==='none');
    button.classList.toggle('edited',Boolean(segment.edited));
    button.onclick=()=>{player.currentTime=segment.start+1e-4;update();};
    segment.button=button;container.append(button);
  });
  update();
}

function syncEditorWithCurrent(seg,choices){
  if(!seg)return;
  if($('#edit-target-range'))$('#edit-target-range').textContent=`${clock(seg.start)} ~ ${clock(seg.end)} (${(seg.end-seg.start).toFixed(2)}s)`;
  const c=choices?.[0];
  if(!c)return;
  const isShape=$('#notation').value==='shape';
  const offset=isShape?Number($('#capo').value):0;
  const dispRoot=(c.root_pc-offset+12)%12;
  const dispBass=Number.isInteger(c.bass_pc)&&c.bass_pc!==c.root_pc?(c.bass_pc-offset+12)%12:'';
  if($('#edit-root'))$('#edit-root').value=String(dispRoot);
  if($('#edit-quality')&&QUALITY_SUFFIX[c.quality]!==undefined)$('#edit-quality').value=c.quality;
  if($('#edit-bass'))$('#edit-bass').value=String(dispBass);
}

async function applyChordEditToCurrentSegment(concertRootPc,quality,concertBassPc=null){
  if(!currentJob||!segments.length)return;
  const time=Math.min(player.currentTime,Math.max(0,result.duration_s-1e-6));
  const segIndex=segments.findIndex(s=>s.start<=time&&s.end>time);
  const seg=segments[segIndex>=0?segIndex:selection];
  if(!seg)return;
  const rootPc=((Number(concertRootPc)%12)+12)%12;
  const bassPc=concertBassPc!==null&&concertBassPc!==''&&Number.isInteger(Number(concertBassPc))?((Number(concertBassPc)%12)+12)%12:null;
  const pcs=(QUALITY_PCS[quality]||[0,4,7]).map(i=>(rootPc+i)%12);
  const baseSymbol=names[rootPc]+(QUALITY_SUFFIX[quality]??quality);
  const symbol=baseSymbol+(bassPc!==null&&bassPc!==rootPc?'/'+names[bassPc]:'');
  const editedCand={
    root_pc:rootPc,
    quality,
    pcs,
    base_symbol:baseSymbol,
    symbol,
    bass_pc:bassPc,
    score:1.0,
    adjusted_score:1.0,
    bass_display_status:bassPc!==null&&bassPc!==rootPc?'user_edited_slash':'user_edited',
    user_edited:true
  };
  rows.forEach(row=>{
    if(row.time_s>=seg.start-1e-4&&row.time_s<seg.end-1e-4){
      ['presentation','onset_presentation','vision_presentation','vision_onset_presentation'].forEach(k=>{
        if(row[k]){
          row[k].display_candidates=[editedCand];
          row[k].frame_display_candidates=[editedCand];
          row[k].status='user_edited_segment';
        }
      });
    }
  });
  rebuild();
  try{
    await api(`/api/jobs/${currentJob.id}/edit`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        window:$('#window').value,
        start_s:seg.start,
        end_s:seg.end,
        root_pc:rootPc,
        quality,
        bass_pc:bassPc
      })
    });
    notice(`구간 (${clock(seg.start)}~${clock(seg.end)}) 코드가 '${label(editedCand)}'(으)로 수정·저장되었습니다.`);
  }catch(e){
    notice(`로컬 화면에는 반영되었으나 서버 저장 중 오류: ${e.message}`);
  }
}

const STANDARD_VOICINGS={
  '0:major':{frets:[-1,3,2,0,1,0],baseFret:1},
  '0:minor':{frets:[-1,3,5,5,4,3],baseFret:3},
  '0:7':{frets:[-1,3,2,3,1,0],baseFret:1},
  '0:m7':{frets:[-1,3,5,3,4,3],baseFret:3},
  '0:maj7':{frets:[-1,3,2,0,0,0],baseFret:1},
  '1:major':{frets:[-1,4,6,6,6,4],baseFret:4},
  '1:minor':{frets:[-1,4,6,6,5,4],baseFret:4},
  '2:major':{frets:[-1,-1,0,2,3,2],baseFret:1},
  '2:minor':{frets:[-1,-1,0,2,3,1],baseFret:1},
  '2:7':{frets:[-1,-1,0,2,1,2],baseFret:1},
  '2:m7':{frets:[-1,-1,0,2,1,1],baseFret:1},
  '2:sus4':{frets:[-1,-1,0,2,3,3],baseFret:1},
  '3:major':{frets:[-1,6,8,8,8,6],baseFret:6},
  '4:major':{frets:[0,2,2,1,0,0],baseFret:1},
  '4:minor':{frets:[0,2,2,0,0,0],baseFret:1},
  '4:7':{frets:[0,2,0,1,0,0],baseFret:1},
  '4:m7':{frets:[0,2,0,0,0,0],baseFret:1},
  '4:maj7':{frets:[0,2,1,1,0,0],baseFret:1},
  '5:major':{frets:[1,3,3,2,1,1],baseFret:1},
  '5:minor':{frets:[1,3,3,1,1,1],baseFret:1},
  '6:major':{frets:[2,4,4,3,2,2],baseFret:2},
  '6:minor':{frets:[2,4,4,2,2,2],baseFret:2},
  '6:m7':{frets:[2,4,2,2,2,2],baseFret:2},
  '7:major':{frets:[3,2,0,0,0,3],baseFret:1},
  '7:minor':{frets:[3,5,5,3,3,3],baseFret:3},
  '7:7':{frets:[3,2,0,0,0,1],baseFret:1},
  '7:m7':{frets:[3,5,3,3,3,3],baseFret:3},
  '7:6':{frets:[3,2,0,0,0,0],baseFret:1},
  '8:major':{frets:[4,6,6,5,4,4],baseFret:4},
  '9:major':{frets:[-1,0,2,2,2,0],baseFret:1},
  '9:minor':{frets:[-1,0,2,2,1,0],baseFret:1},
  '9:7':{frets:[-1,0,2,0,2,0],baseFret:1},
  '9:m7':{frets:[-1,0,2,0,1,0],baseFret:1},
  '10:major':{frets:[-1,1,3,3,3,1],baseFret:1},
  '11:major':{frets:[-1,2,4,4,4,2],baseFret:2},
  '11:minor':{frets:[-1,2,4,4,3,2],baseFret:2},
  '11:7':{frets:[-1,2,1,2,0,2],baseFret:1},
  '11:m7':{frets:[-1,2,4,2,3,2],baseFret:2}
};

function getChordVoicing(root,quality){
  const k=`${root}:${quality}`;
  if(STANDARD_VOICINGS[k])return STANDARD_VOICINGS[k];
  const base=root>=4?root-4:root+8;
  const isM=quality.includes('m')&&quality!=='maj7';
  return {frets:isM?[base,base+2,base+2,base,base,base]:[base,base+2,base+2,base+1,base,base],baseFret:Math.max(1,base)};
}

function renderFretboardDiagram(cand){
  const svg=$('#chord-fretboard-svg');
  if(!svg||!cand)return;
  const offset=$('#notation')?.value==='shape'?Number($('#capo')?.value||0):0;
  const root=(cand.root_pc-offset+12)%12;
  const v=getChordVoicing(root,cand.quality);
  if(!v)return;

  const validFrets=v.frets.filter(f=>f>0);
  const minF=validFrets.length?Math.min(...validFrets):1;
  const maxF=validFrets.length?Math.max(...validFrets):1;
  const hasOpen=v.frets.some(f=>f===0);

  // 5 frets range
  const numFrets=5;
  let base=1;
  if(!hasOpen&&minF>=3&&maxF>4){
    base=minF;
  }else if(!hasOpen&&minF>3){
    base=minF;
  }

  const startX=44,startY=22,width=280,height=60;
  const fretW=width/numFrets,stringH=height/5;
  let items=[];

  // 1. Nut or Starting Fret line & TOP position indicator
  if(base===1){
    items.push(`<line x1="${startX}" y1="${startY}" x2="${startX}" y2="${startY+height}" stroke="#6ce7c6" stroke-width="4.5" stroke-linecap="round"/>`);
    items.push(`<text x="${startX+fretW/2}" y="${startY-8}" fill="#6ce7c6" font-size="10" font-weight="700" text-anchor="middle">OPEN (1F)</text>`);
  }else{
    items.push(`<line x1="${startX}" y1="${startY}" x2="${startX}" y2="${startY+height}" stroke="#485c78" stroke-width="2"/>`);
    // Dedicated Badge at TOP above Fret 1 (leaves string indicators clean on the left)
    items.push(`<rect x="${startX+fretW/2-21}" y="${startY-17}" width="42" height="15" rx="3.5" fill="#1b2838" stroke="#3d5573" stroke-width="1"/>`);
    items.push(`<text x="${startX+fretW/2}" y="${startY-6.5}" fill="#6ce7c6" font-size="10" font-weight="800" text-anchor="middle">${base}fr</text>`);
  }

  // 2. Fret divider lines (vertical)
  for(let f=1;f<=numFrets;f++){
    const x=startX+f*fretW;
    items.push(`<line x1="${x}" y1="${startY}" x2="${x}" y2="${startY+height}" stroke="#2a384c" stroke-width="1.5"/>`);
  }

  // 3. Fret numbers & Inlay markers at the BOTTOM
  const INLAYS=new Set([3,5,7,9,15,17,19,21]);
  for(let f=0;f<numFrets;f++){
    const curFret=base+f;
    const midX=startX+f*fretW+fretW/2;
    const isBaseFret=curFret===base&&base>1;
    items.push(`<text x="${midX}" y="${startY+height+13}" fill="${isBaseFret?'#6ce7c6':'#6d829e'}" font-size="9.5" font-weight="${isBaseFret?'800':'600'}" text-anchor="middle">${curFret}</text>`);
    if(curFret===12){
      items.push(`<circle cx="${midX-3.5}" cy="${startY+height+21}" r="1.8" fill="#5b7291"/>`);
      items.push(`<circle cx="${midX+3.5}" cy="${startY+height+21}" r="1.8" fill="#5b7291"/>`);
    }else if(INLAYS.has(curFret)){
      items.push(`<circle cx="${midX}" cy="${startY+height+21}" r="1.8" fill="#4d627e"/>`);
    }
  }

  // 4. Strings (horizontal) & String pitch names on the LEFT (e, B, G, D, A, E)
  const strNames=['e','B','G','D','A','E'];
  for(let s=0;s<6;s++){
    const y=startY+s*stringH;
    const sw=s===5?2.5:s>=3?1.8:1.2;
    items.push(`<line x1="${startX}" y1="${y}" x2="${startX+width}" y2="${y}" stroke="#425570" stroke-width="${sw}"/>`);
    items.push(`<text x="${startX-22}" y="${y+3.5}" fill="#6f829d" font-size="9.5" font-family="monospace" text-anchor="middle">${strNames[s]}</text>`);
  }

  // 5. Open/Mute indicators on the LEFT & Pressed finger dots
  v.frets.forEach((fret,idx6to1)=>{
    const s=5-idx6to1;
    const y=startY+s*stringH;
    if(fret===-1){
      items.push(`<text x="${startX-8}" y="${y+4}" fill="#f87171" font-size="11" font-weight="800" text-anchor="middle">×</text>`);
    }else if(fret===0){
      items.push(`<circle cx="${startX-8}" cy="${y}" r="3.5" fill="none" stroke="#6ce7c6" stroke-width="1.5"/>`);
    }else if(fret>=base&&fret<base+numFrets){
      const fRel=fret-base;
      const x=startX+fRel*fretW+fretW/2;
      items.push(`<circle cx="${x}" cy="${y}" r="6.5" fill="#6ce7c6"/>`);
    }
  });

  if(typeof svg.innerHTML!=='undefined') svg.innerHTML=items.join('');
  const info=$('#fretboard-voicing-info');
  if(info)info.textContent=`${label(cand)} · ${base===1?'오픈 포지션 (1~5F)':base+'프렛 포지션 ('+base+'~'+(base+numFrets-1)+'F)'}`;
}

let leadSheetMeasures=[];
function renderLeadSheet(){
  const container=$('#lead-sheet-grid');
  if(!container||!result)return;
  const {bpm,offsetS}=activeTempo();
  const barDuration=(60/bpm)*4;
  const totalBars=Math.ceil((result.duration_s-offsetS)/barDuration);
  leadSheetMeasures=[];
  container.replaceChildren();
  for(let b=1;b<=totalBars;b++){
    const startT=offsetS+(b-1)*barDuration;
    const endT=startT+barDuration;
    if(startT>=result.duration_s)break;
    const matchingSegs=segments.filter(s=>s.start<endT&&s.end>startT);
    let chordTexts=[];
    if(matchingSegs.length){
      chordTexts=[...new Set(matchingSegs.map(s=>display(s.row).map(c=>label(c)).join('/')||'보류'))];
    }else{
      chordTexts=['—'];
    }
    const barEl=document.createElement('div');
    barEl.className='sheet-bar';
    if(barEl.dataset){barEl.dataset.bar=b;barEl.dataset.start=startT;barEl.dataset.end=endT;}
    barEl.innerHTML=`<div class="sheet-bar-head"><span class="sheet-bar-num">#${b}</span><span class="sheet-bar-time">${clock(Math.max(0,startT))}</span></div><div class="sheet-chord-title">${chordTexts.slice(0,2).join(' → ')}</div><div class="sheet-slashes">𝄀 /  /  /  / 𝄀</div>`;
    barEl.onclick=()=>{player.currentTime=Math.max(0,startT);if(player.paused)update();};
    container.append(barEl);
    leadSheetMeasures.push({bar:b,startT,endT,element:barEl});
  }
}

let lastActiveBar=-1;
function updateLeadSheetHighlight(time){
  const panelSheet=$('#panel-sheet');
  if(!panelSheet||panelSheet.hidden)return;
  const activeMeasure=leadSheetMeasures.find(m=>m.startT<=time&&m.endT>time);
  if(activeMeasure&&activeMeasure.bar!==lastActiveBar){
    if(lastActiveBar!==-1){
      leadSheetMeasures.find(m=>m.bar===lastActiveBar)?.element?.classList?.remove('active');
    }
    activeMeasure.element?.classList?.add('active');
    lastActiveBar=activeMeasure.bar;
    if(activeMeasure.element?.scrollIntoView)activeMeasure.element.scrollIntoView({behavior:'smooth',block:'nearest'});
  }
}

function initDualViewSwitcher(){
  const tabInspector=$('#tab-inspector');
  const tabSheet=$('#tab-sheet');
  const panelInspector=$('#panel-inspector');
  const panelSheet=$('#panel-sheet');
  if(!tabInspector||!tabSheet)return;
  tabInspector.onclick=()=>{
    tabInspector.classList.add('active');
    tabSheet.classList.remove('active');
    if(panelInspector){panelInspector.classList.add('active');panelInspector.hidden=false;}
    if(panelSheet){panelSheet.classList.remove('active');panelSheet.hidden=true;}
  };
  tabSheet.onclick=()=>{
    tabSheet.classList.add('active');
    tabInspector.classList.remove('active');
    if(panelSheet){panelSheet.classList.add('active');panelSheet.hidden=false;}
    if(panelInspector){panelInspector.classList.remove('active');panelInspector.hidden=true;}
    if(result&&!leadSheetMeasures.length)renderLeadSheet();
    updateLeadSheetHighlight(player.currentTime||0);
  };
}

function update(){
  if(!rows.length)return;
  const time=Math.min(player.currentTime,Math.max(0,result.duration_s-1e-6));
  drawVision(time);
  $('#clock').textContent=`${clock(player.currentTime)} / ${clock(result.duration_s)}`;
  const {bpm,offsetS}=activeTempo();
  const beatPos=formatBeatPosition(time,bpm,offsetS);
  if($('#beat-position'))$('#beat-position').textContent=beatPos.text;
  const playhead=$('#timeline-playhead');
  if(playhead?.style){
    const x=time*timelinePxPerSec;
    playhead.style.left=`${x.toFixed(1)}px`;
    const scroller=$('#timeline-scroll');
    if(scroller&&!player.paused&&scroller.clientWidth>0){
      if(x<scroller.scrollLeft+40||x>scroller.scrollLeft+scroller.clientWidth-80){
        scroller.scrollLeft=Math.max(0,x-160);
      }
    }
  }
  let low=0,high=rows.length-1;
  while(low<high){const mid=Math.ceil((low+high)/2);if(rows[mid].time_s<=time)low=mid;else high=mid-1;}
  if(low===lastRendered)return;
  lastRendered=low;
  const row=rows[low],choices=display(row),text=choices.map(c=>label(c)).join(' / ')||'보류';
  const hasRealChord=choices.length>0&&text!=='보류'&&text!=='—';
  $('#chord').textContent=text;
  if($('#overlay-chord'))$('#overlay-chord').textContent=hasRealChord?text:'';
  if($('#overlay-pill'))$('#overlay-pill').style.display=hasRealChord?'inline-flex':'none';
  const isEdited=Boolean(choices[0]?.user_edited);
  const ctx=$('#context')?.checked?activeContext(row):null;
  const isAnchored=Boolean(choices[0]?.source==='full_mix_anchor'||choices[0]?.anchor_note||ctx?.status==='full_mix_harmonic_anchor');
  $('#state').textContent=isEdited?'사용자 직접 수정 확정 코드':isAnchored?'원곡 전체 음원 화성 보강':'현재 코드 후보';
  if($('#overlay-caption'))$('#overlay-caption').textContent=$('#state').textContent;
  $('#other-name').textContent=choices.length?(`${$('#notation').value==='shape'?'실음':'운지'}: `+choices.map(c=>label(c,$('#notation').value!=='shape')).join(' / '))+(isAnchored?' (기타 모호 구간 · 원곡 화성 앵커)':''):'현재 음 근거가 부족합니다.';
  const stable=$('#context').checked?activePresentation(row):null;
  const slashShown=choices.some(c=>Number.isInteger(c.bass_pc)&&c.bass_pc!==c.root_pc);
  if($('#overlay-sub'))$('#overlay-sub').textContent=isEdited?'사용자가 직접 교정·저장한 구간':isAnchored?'원곡 전체 음원 화성 기반 보강':stable&&stable.status==='quantized_16th_beat_grid'?`16박자 격자 전환 정렬 · ${bpm} BPM`:slashShown?'지속된 저음의 분수코드 후보':'오디오 + 16박자 격자 분석';
  const observed=stable?.observed_bass||ctx?.bass;
  $('#bass-hypothesis').textContent=observed?.pc!==null&&observed?.pc!==undefined?`실음 저음 후보 ${names[observed.pc]}${Math.floor(observed.midi/12)-1}`:'';
  const container=$('#candidates');container.replaceChildren();
  (ctx?.top3?.length?ctx.top3:row.top3).forEach(c=>{
    const div=document.createElement('div');div.className='candidate';
    const title=document.createElement('strong'),score=document.createElement('span'),btn=document.createElement('button');
    const tag=c.source==='full_mix_anchor'?' [원곡 앵커]':c.bonus_components?.full_mix>0?' [원곡 일치]':'';
    const baseSym=c.base_symbol||(c.symbol?c.symbol.split('/')[0]:names[c.root_pc]+(QUALITY_SUFFIX[c.quality]??''))||'—';
    title.textContent=label({...c,symbol:baseSym,base_symbol:baseSym,bass_pc:null})+tag;
    const adjusted=c.vision_adjusted_score??c.onset_adjusted_score??c.adjusted_score;
    score.textContent=adjusted!==undefined?`${c.score.toFixed(3)} + ${(adjusted-c.score).toFixed(3)}`:c.score.toFixed(3);
    btn.className='promote-btn';btn.textContent='이 코드로 변경';
    btn.onclick=()=>applyChordEditToCurrentSegment(c.root_pc,c.quality,null);
    div.append(title,score,btn);container.append(div);
  });
  const index=segments.findIndex(s=>s.start<=time&&s.end>time);
  if(index!==selection){segments[selection]?.button.classList.remove('active');selection=index;}
  segments[index]?.button.classList.add('active');
  syncEditorWithCurrent(segments[index],choices);
  if(choices.length) renderFretboardDiagram(choices[0]);
  updateLeadSheetHighlight(time);
  $('#next').textContent=segments[index+1]?display(segments[index+1].row).map(c=>label(c)).join(' / ')||'보류':'—';
}

const CALIB_PROMPTS=[
  '① 너트 위쪽 (6번줄 시작점)을 영상 위에서 클릭하세요',
  '② 마지막 프렛 위쪽 (6번줄 지판 끝)을 영상 위에서 클릭하세요',
  '③ 마지막 프렛 아래쪽 (1번줄 지판 끝)을 영상 위에서 클릭하세요',
  '④ 너트 아래쪽 (1번줄 시작점)을 영상 위에서 클릭하세요',
  '✓ 지판 전체 네 모서리(너트~마지막 프렛)가 지정되었습니다! [이 지판으로 비전 분석 실행]을 눌러주세요.'
];

function setCalibrating(active){
  calibratingMode=active;
  dragTarget=null;hoveredTarget=null;
  $('#calibrate-bar').hidden=!active;
  $('#vision-canvas').classList.toggle('calibrating',active);
  if(active){
    player.pause();
    const existing = currentJob?.user_calibration?.corners || userCalibratedCorners;
    if(existing && existing.length === 4){
      calibPoints = existing.map(p => [...p]);
      if(currentJob?.user_calibration?.total_frets && $('#total-frets')){
        $('#total-frets').value = String(currentJob.user_calibration.total_frets);
      }
      if(currentJob?.user_calibration?.perspective_k !== undefined){
        perspectiveK = Number(currentJob.user_calibration.perspective_k) || 0;
        if($('#fret-perspective')) $('#fret-perspective').value = Math.round(perspectiveK * 100);
        if($('#fret-persp-val')) $('#fret-persp-val').textContent = (perspectiveK > 0 ? '+' : '') + Math.round(perspectiveK * 100) + '%';
      }
      $('#calibrate-prompt').textContent = '✓ 4점이 로드되었습니다. 모서리 점과 [12F] 핸들을 드래그하여 미세조정한 뒤 [비전 분석 실행]을 누르세요';
      $('#apply-calibrate').disabled = false;
    } else {
      calibPoints = [];
      $('#calibrate-prompt').textContent = CALIB_PROMPTS[0];
      $('#apply-calibrate').disabled = true;
    }
  }
  drawVision(player.currentTime);
}

const vCanvas = $('#vision-canvas');
if(vCanvas){
  function distToSeg(p, a, b){
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const l2 = dx * dx + dy * dy;
    if(l2 === 0) return Math.hypot(p[0] - a[0], p[1] - a[1]);
    let t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2));
    return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
  }

  function getFret12Pos(tf){
    if(calibPoints.length !== 4) return null;
    const totalFrets = Math.max(12, Math.min(24, Number($('#total-frets')?.value) || 20));
    const denom = 1 - Math.pow(2, -totalFrets / 12);
    const un12 = 0.5 / denom;
    const k = perspectiveK || 0.0;
    const r12 = un12 < 1.0 ? ((1 + k) * un12 / (1 + k * un12)) : 1.0;
    const top12 = [calibPoints[0][0] * (1 - r12) + calibPoints[1][0] * r12, calibPoints[0][1] * (1 - r12) + calibPoints[1][1] * r12];
    const bot12 = [calibPoints[3][0] * (1 - r12) + calibPoints[2][0] * r12, calibPoints[3][0] * (1 - r12) + calibPoints[2][1] * r12];
    const midX = tf.dx + ((top12[0] + bot12[0]) / 2) * tf.scale;
    const midY = tf.dy + ((top12[1] + bot12[1]) / 2) * tf.scale;
    return {
      top: [tf.dx + top12[0] * tf.scale, tf.dy + top12[1] * tf.scale],
      bot: [tf.dx + bot12[0] * tf.scale, tf.dy + bot12[1] * tf.scale],
      mid: [midX, midY]
    };
  }

  vCanvas.onmousedown = e => {
    if(!calibratingMode) return;
    const tf = getVideoTransform();
    if(!tf) return;
    const stage = $('.stage');
    if(!stage) return;
    const stageRect = stage.getBoundingClientRect();
    const stageX = e.clientX - stageRect.left, stageY = e.clientY - stageRect.top;
    const vx = Math.max(0, Math.min(tf.videoW, (stageX - tf.dx) / tf.scale));
    const vy = Math.max(0, Math.min(tf.videoH, (stageY - tf.dy) / tf.scale));

    for(let i = 0; i < calibPoints.length; i++){
      const cx = tf.dx + calibPoints[i][0] * tf.scale, cy = tf.dy + calibPoints[i][1] * tf.scale;
      if(Math.hypot(stageX - cx, stageY - cy) <= 18){
        dragTarget = { type: 'corner', index: i };
        vCanvas.style.cursor = 'grabbing';
        drawVision(player.currentTime);
        return;
      }
    }

    if(calibPoints.length === 4){
      const f12 = getFret12Pos(tf);
      if(f12 && (Math.hypot(stageX - f12.mid[0], stageY - f12.mid[1]) <= 24 || distToSeg([stageX, stageY], f12.top, f12.bot) <= 12)){
        dragTarget = { type: 'fret12' };
        vCanvas.style.cursor = 'ew-resize';
        drawVision(player.currentTime);
        return;
      }
    }

    if(calibPoints.length < 4){
      calibPoints.push([vx, vy]);
      if(calibPoints.length === 4){
        $('#calibrate-prompt').textContent = '✓ 4점이 지정되었습니다. 모서리 점과 [12F] 핸들을 드래그하여 미세조정한 뒤 [비전 분석 실행]을 누르세요';
        $('#apply-calibrate').disabled = false;
      } else {
        $('#calibrate-prompt').textContent = CALIB_PROMPTS[calibPoints.length];
        $('#apply-calibrate').disabled = true;
      }
      drawVision(player.currentTime);
    }
  };

  vCanvas.onmousemove = e => {
    if(!calibratingMode) return;
    const tf = getVideoTransform();
    if(!tf) return;
    const stage = $('.stage');
    if(!stage) return;
    const stageRect = stage.getBoundingClientRect();
    const stageX = e.clientX - stageRect.left, stageY = e.clientY - stageRect.top;
    const vx = Math.max(0, Math.min(tf.videoW, (stageX - tf.dx) / tf.scale));
    const vy = Math.max(0, Math.min(tf.videoH, (stageY - tf.dy) / tf.scale));

    if(dragTarget){
      if(dragTarget.type === 'corner'){
        calibPoints[dragTarget.index] = [vx, vy];
      } else if(dragTarget.type === 'fret12'){
        const c = calibPoints;
        const nut = [(c[0][0] + c[3][0]) / 2, (c[0][1] + c[3][1]) / 2];
        const body = [(c[1][0] + c[2][0]) / 2, (c[1][1] + c[2][1]) / 2];
        const L = Math.hypot(body[0] - nut[0], body[1] - nut[1]);
        if(L > 10){
          const axisX = (body[0] - nut[0]) / L, axisY = (body[1] - nut[1]) / L;
          const proj = (vx - nut[0]) * axisX + (vy - nut[1]) * axisY;
          const s = Math.max(0.18, Math.min(0.90, proj / L));
          const totalFrets = Math.max(12, Math.min(24, Number($('#total-frets')?.value) || 20));
          const denom = 1 - Math.pow(2, -totalFrets / 12);
          const un12 = 0.5 / denom;
          if(s < 0.98 && un12 < 0.98){
            let k = (s - un12) / (un12 * (1 - s));
            k = Math.max(-0.60, Math.min(0.60, k));
            perspectiveK = k;
            if($('#fret-perspective')){
              $('#fret-perspective').value = Math.round(k * 100);
              if($('#fret-persp-val')) $('#fret-persp-val').textContent = (k > 0 ? '+' : '') + Math.round(k * 100) + '%';
            }
          }
        }
      }
      drawVision(player.currentTime);
      return;
    }

    let hovered = null;
    for(let i = 0; i < calibPoints.length; i++){
      const cx = tf.dx + calibPoints[i][0] * tf.scale, cy = tf.dy + calibPoints[i][1] * tf.scale;
      if(Math.hypot(stageX - cx, stageY - cy) <= 18){
        hovered = { type: 'corner', index: i };
        break;
      }
    }
    if(!hovered && calibPoints.length === 4){
      const f12 = getFret12Pos(tf);
      if(f12 && (Math.hypot(stageX - f12.mid[0], stageY - f12.mid[1]) <= 24 || distToSeg([stageX, stageY], f12.top, f12.bot) <= 12)){
        hovered = { type: 'fret12' };
      }
    }

    if(hovered?.type === 'corner'){
      vCanvas.style.cursor = 'grab';
    } else if(hovered?.type === 'fret12'){
      vCanvas.style.cursor = 'ew-resize';
    } else {
      vCanvas.style.cursor = calibPoints.length < 4 ? 'crosshair' : 'default';
    }

    if(JSON.stringify(hovered) !== JSON.stringify(hoveredTarget)){
      hoveredTarget = hovered;
      drawVision(player.currentTime);
    }
  };

  const endDrag = () => {
    if(dragTarget){
      dragTarget = null;
      vCanvas.style.cursor = hoveredTarget?.type === 'corner' ? 'grab' : hoveredTarget?.type === 'fret12' ? 'ew-resize' : (calibPoints.length < 4 ? 'crosshair' : 'default');
      drawVision(player.currentTime);
    }
  };
  vCanvas.onmouseup = endDrag;
  vCanvas.onmouseleave = endDrag;
}

if($('#start-calibrate'))$('#start-calibrate').onclick=()=>{
  if(!currentJob)return;
  if(currentJob.media_url.endsWith('.wav')){
    notice('오디오 전용 파일입니다. 영상 파일(.mp4)을 열었을 때 지판 직접 지정이 가능합니다.');
    return;
  }
  setCalibrating(!calibratingMode);
};
if($('#total-frets'))$('#total-frets').onchange=()=>drawVision(player.currentTime);
if($('#fret-perspective')){
  $('#fret-perspective').oninput=()=>{
    perspectiveK=Number($('#fret-perspective').value)/100;
    if($('#fret-persp-val'))$('#fret-persp-val').textContent=(perspectiveK>0?'+':'')+Math.round(perspectiveK*100)+'%';
    drawVision(player.currentTime);
  };
}
if($('#reset-calibrate'))$('#reset-calibrate').onclick=()=>{
  calibPoints=[];
  dragTarget=null;hoveredTarget=null;
  $('#calibrate-prompt').textContent=CALIB_PROMPTS[0];
  $('#apply-calibrate').disabled=true;
  drawVision(player.currentTime);
};
if($('#cancel-calibrate'))$('#cancel-calibrate').onclick=()=>setCalibrating(false);

function updateVisionIndicator(job = currentJob) {
  const ind = $('#vision-indicator');
  const label = $('#vision-indicator-label');
  if (!ind || !label) return;

  if (!job || !job.media_url || job.media_url.endsWith('.wav')) {
    ind.className = 'vision-indicator-pill state-disabled';
    label.textContent = '오디오 전용 (비전 없음)';
    ind.title = '오디오 전용 파일에서는 지판 비전 추적이 지원되지 않습니다.';
    return;
  }

  const vStatus = job.vision_status;
  if (vStatus === 'calibrating') {
    ind.className = 'vision-indicator-pill state-calibrating';
    const pct = job.vision_progress !== undefined ? `(${job.vision_progress}%)` : '';
    label.textContent = `⏳ 지판 비전 분석 중 ${pct}`.trim();
    ind.title = job.message || '백그라운드에서 전체 영상 지판·손 비전 추적 중입니다.';
  } else if (vStatus === 'user_calibrated_active' || (result && result.vision_connected)) {
    ind.className = 'vision-indicator-pill state-active';
    label.textContent = '✓ 지판 비전 활성';
    ind.title = '사용자 지정 지판 및 손가락 골격 추적이 적용되어 영상에 표시 중입니다. (클릭하여 재지정 가능)';
  } else if (vStatus === 'calibration_saved_audio_preserved') {
    ind.className = 'vision-indicator-pill state-saved';
    label.textContent = 'ℹ 지판 좌표 저장됨';
    ind.title = '지판 4점 좌표가 저장되었습니다. (클릭하여 재지정 가능)';
  } else {
    ind.className = 'vision-indicator-pill state-idle';
    label.textContent = '⌖ 지판 비전: 대기';
    ind.title = '클릭하거나 우측 [지판 직접 지정] 버튼을 눌러 영상 위 지판을 지정하면 비전 분석이 시작됩니다.';
  }
}

if ($('#vision-indicator')) {
  $('#vision-indicator').onclick = () => {
    if (!currentJob || currentJob.media_url?.endsWith('.wav')) return;
    if (currentJob.vision_status === 'calibrating') {
      notice(currentJob.message || '현재 백그라운드에서 지판 비전 추적이 진행 중입니다.');
      return;
    }
    if ($('#start-calibrate')) $('#start-calibrate').click();
  };
}

async function watchCalibration(jobId){
  try{
    const job=await api(`/api/jobs/${jobId}`);
    if(!currentJob||currentJob.id!==jobId)return;
    currentJob=job;
    updateVisionIndicator(job);
    if(job.vision_status==='calibrating'){
      notice(job.message || '백그라운드에서 전체 영상 프레임(손·지판) 비전 추적 중입니다... (재생·코드 편집 계속 가능)');
      setTimeout(()=>watchCalibration(jobId),1500);
      return;
    }
    if(job.vision_status==='user_calibrated_active'&&job.vision_url){
      currentJob=job;
      result=await api(job.result_url);
      visionOverlay=await api(job.vision_url);
      $('#vision').disabled=!result.vision_connected;
      $('#mode-pill').textContent='오디오 + 사용자 지판 비전 연결됨';
      updateVisionIndicator(job);
      notice('✓ 사용자 지정 지판 비전 추적이 완료되어 전체 영상에 반영되었습니다.');
      rebuild();
      return;
    }
    if(job.vision_status==='calibration_saved_audio_preserved'){
      updateVisionIndicator(job);
      notice(job.message||'지판 좌표 저장 완료');
    }
  }catch(e){}
}

if($('#apply-calibrate'))$('#apply-calibrate').onclick=async()=>{
  if(!currentJob||calibPoints.length!==4)return;
  userCalibratedCorners=calibPoints.map(p=>[...p]);
  const refTime=player.currentTime;
  setCalibrating(false);
  currentJob.vision_status='calibrating';
  currentJob.vision_progress=0;
  updateVisionIndicator(currentJob);
  notice('지판 4점 좌표 및 프렛 간격을 저장하고 비전 추적을 요청했습니다...');
  try{
    const capVal=Number($('#capo').value);
    const totalFrets=Number($('#total-frets')?.value)||20;
    await api(`/api/jobs/${currentJob.id}/calibrate`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        time_s:refTime,
        corners:userCalibratedCorners,
        capo:Number.isFinite(capVal)?capVal:0,
        total_frets:totalFrets,
        perspective_k:perspectiveK
      })
    });
    notice('지판 4점 격자가 적용되었습니다. 백그라운드에서 전체 프레임 비전 추적을 시작합니다.');
    drawVision(player.currentTime);
    setTimeout(()=>watchCalibration(currentJob.id),1500);
  }catch(e){
    notice(e.message);
  }
};

if($('#apply-edit-btn'))$('#apply-edit-btn').onclick=()=>{
  const isShape=$('#notation').value==='shape';
  const offset=isShape?Number($('#capo').value):0;
  const dispRoot=Number($('#edit-root').value);
  const concertRoot=(dispRoot+offset+12)%12;
  const quality=$('#edit-quality').value;
  const rawBass=$('#edit-bass').value;
  const concertBass=rawBass!==''?(Number(rawBass)+offset+12)%12:null;
  applyChordEditToCurrentSegment(concertRoot,quality,concertBass);
};

if($('#audio-source-btn'))$('#audio-source-btn').onclick=()=>{
  if(!currentJob?.guitar_audio_url)return;
  const curTime=player.currentTime,wasPlaying=!player.paused;
  usingGuitarStem=!usingGuitarStem;
  player.src=usingGuitarStem?currentJob.guitar_audio_url:currentJob.media_url;
  $('.stage')?.classList.toggle('audio',player.src.endsWith('.wav'));
  $('#audio-source-btn').textContent=usingGuitarStem?'원곡 전체 듣기 🎬':'기타 분리 트랙 듣기 ♬';
  player.currentTime=curTime;
  if(wasPlaying)player.play();
};

async function openJob(job){
  const data=await api(job.result_url);currentJob=job;result=data;
  usingGuitarStem=false;calibratingMode=false;userCalibratedCorners=null;perspectiveK=0.0;
  if(job.user_calibration?.corners){
    userCalibratedCorners=job.user_calibration.corners.map(p=>[...p]);
    if(job.user_calibration.perspective_k!==undefined){
      perspectiveK=Number(job.user_calibration.perspective_k)||0;
      if($('#fret-perspective'))$('#fret-perspective').value=Math.round(perspectiveK*100);
      if($('#fret-persp-val'))$('#fret-persp-val').textContent=(perspectiveK>0?'+':'')+Math.round(perspectiveK*100)+'%';
    }
    if(job.user_calibration.total_frets&&$('#total-frets')){
      $('#total-frets').value=String(job.user_calibration.total_frets);
    }
  }
  if($('#calibrate-bar'))$('#calibrate-bar').hidden=true;
  player.pause();player.src=job.media_url;
  if($('#audio-source-btn')){
    $('#audio-source-btn').hidden=!job.guitar_audio_url||job.media_url===job.guitar_audio_url;
    $('#audio-source-btn').textContent='기타 분리 트랙 듣기 ♬';
  }
  const autoBpm=data.tempo?.auto_bpm??data.tempo?.bpm??120;
  const autoOffset=Number(data.tempo?.offset_s??0);
  if($('#bpm'))$('#bpm').value=autoBpm;
  if($('#bpm-auto'))$('#bpm-auto').textContent=`자동 ${autoBpm}`;
  if($('#beat-offset'))$('#beat-offset').value=autoOffset.toFixed(2);
  if($('#offset-auto'))$('#offset-auto').textContent=`자동 ${autoOffset.toFixed(2)}s`;
  visionOverlay=[];$('#vision').disabled=!data.vision_connected;
  $('#mode-pill').textContent=job.separation_status==='separated_htdemucs_6s'?'기타 트랙 분리 완료':data.vision_connected?'오디오 + 비전 지판 연결됨':'오디오 16박자 격자 + 편집 모드';
  if(job.vision_url){try{visionOverlay=await api(job.vision_url);}catch(e){notice('비전 오버레이 로드 생략');}}
  $('.stage')?.classList.toggle('audio',job.media_url.endsWith('.wav'));$('#track-name').textContent=job.name;
  if($('#download'))$('#download').href=job.result_url;$('#end-time').textContent=clock(data.duration_s);
  updateVisionIndicator(job);
  $('#workspace').hidden=false;
  $('#intro').hidden=true;
  if($('#drop'))$('#drop').hidden=true;
  notice('');
  rebuild();
}

async function watch(id){
  try{
    const job=await api(`/api/jobs/${id}`);$('#bar').value=job.progress;$('#percent').textContent=job.progress+'%';$('#progress-message').textContent=job.message;
    if(job.status==='error')throw Error(job.message);
    if(job.status==='complete'){$('#progress').hidden=true;await openJob(job);busy(false);await loadHistory();return;}
    setTimeout(()=>watch(id),1000);
  }catch(e){notice(e.message);$('#progress').hidden=true;busy(false);loadHistory();}
}
async function start(file){
  if(loading)return;
  if(file&&file.size>2048*1024*1024){notice('2GB 이하의 파일을 선택해 주세요.');return;}
  busy(true);notice();$('#progress').hidden=false;$('#bar').value=0;$('#percent').textContent='0%';
  if($('#intro'))$('#intro').hidden=true;if($('#drop'))$('#drop').hidden=true;
  const sep=$('#separate-toggle')?.checked!==false?'1':'0';
  $('#progress-message').textContent=file?'파일 업로드 및 전체 음원 분리 준비 중':'샘플 결과 준비 중';
  if(file)$('#file-name').textContent=file.name;
  try{
    const url=file?`/api/jobs?name=${encodeURIComponent(file.name)}&separate=${sep}`:'/api/demo';
    const job=await api(url,{method:'POST',body:file||null});
    watch(job.id);
  }catch(e){notice(e.message);$('#progress').hidden=true;busy(false);}
}
function formatJobTitle(rawName){
  if(!rawName) return '제목 없음';
  let clean = rawName;
  clean = clean.replace(/^YTDown(?:\.com)?_YouTube_Media_[^_]+_/i, '');
  clean = clean.replace(/_\d+_\d+p\.[a-z0-9]+$/i, '');
  clean = clean.replace(/\.(mp4|wav|mp3|mkv|mov|flac|m4a)$/i, '');
  return clean.trim() || rawName;
}

function formatTimeAgo(timestamp){
  if(!timestamp) return '';
  const now = Date.now(), diff = (now - timestamp * 1000) / 1000;
  if(diff < 60) return '방금 전';
  if(diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if(diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  const d = new Date(timestamp * 1000);
  return `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}

async function loadHistory(){
  try{
    const jobs=await api('/api/jobs');
    const container=$('#history');
    if(!container) return;
    container.replaceChildren();
    const countBadge=$('#history-count');
    if(countBadge) countBadge.textContent=`총 ${jobs.length}건`;
    if(!jobs.length){
      container.innerHTML='<div class="history-empty"><span class="empty-icon">📭</span><p>아직 분석한 파일이 없습니다.<br>위에서 오디오나 영상을 업로드해 보세요!</p></div>';
      return;
    }
    jobs.sort((a,b)=>b.created_at-a.created_at).slice(0,16).forEach(job=>{
      const isVideo=!job.media_url?.endsWith('.wav')&&!job.name?.endsWith('.wav');
      const extMatch=job.name?.match(/\.([a-z0-9]+)$/i);
      const ext=extMatch?extMatch[1].toUpperCase():isVideo?'MP4':'WAV';
      const cleanTitle=formatJobTitle(job.name);
      const timeStr=formatTimeAgo(job.created_at);

      const card=document.createElement('div');
      card.className=`history-card ${job.status}`;

      const iconWrap=document.createElement('div');
      iconWrap.className=`history-media-icon ${isVideo?'video':'audio'}`;
      iconWrap.innerHTML=`<span>${isVideo?'🎬':'♬'}</span>`;

      const content=document.createElement('div');
      content.className='history-content';

      const titleRow=document.createElement('div');
      titleRow.className='history-title-row';
      const title=document.createElement('strong');
      title.className='history-title';
      title.textContent=cleanTitle;
      title.title=job.name;

      const audioPill=document.createElement('span');
      audioPill.className=`status-pill status-${job.status}`;
      audioPill.textContent=job.status==='complete'?'✓ 음성 완료':job.status==='error'?'⚠ 음성 실패':'⏳ 음성 분석 중';

      const visionPill=document.createElement('span');
      if(!isVideo){
        visionPill.className='status-pill status-vision-audio-only';
        visionPill.textContent='오디오 전용';
        visionPill.title='오디오 전용 파일 (비전 미지원)';
      }else if(job.vision_status==='user_calibrated_active'||job.vision_url){
        visionPill.className='status-pill status-vision-active';
        visionPill.textContent='✓ 비전 완료';
        visionPill.title='사용자 지판 및 손 비전 추적 완료';
      }else if(job.vision_status==='calibrating'){
        visionPill.className='status-pill status-vision-calibrating';
        visionPill.textContent='⏳ 비전 분석 중';
        visionPill.title='백그라운드에서 지판 및 손 비전 추적 중';
      }else if(job.vision_status==='calibration_saved_audio_preserved'){
        visionPill.className='status-pill status-vision-saved';
        visionPill.textContent='ℹ 비전 좌표 저장됨';
        visionPill.title='지판 4점 좌표 저장됨';
      }else{
        visionPill.className='status-pill status-vision-idle';
        visionPill.textContent='⌖ 비전 대기';
        visionPill.title='지판 미지정 (스튜디오에서 4점 지정 시 비전 분석 시작)';
      }

      titleRow.append(title,audioPill,visionPill);

      const metaRow=document.createElement('div');
      metaRow.className='history-meta-row';

      const fmtTag=document.createElement('span');
      fmtTag.className='history-tag tag-format';
      fmtTag.textContent=ext;
      metaRow.append(fmtTag);

      if(job.separation_status==='separated_htdemucs_6s'){
        const sepTag=document.createElement('span');
        sepTag.className='history-tag tag-sep';
        sepTag.textContent='♬ 기타 트랙 분리';
        metaRow.append(sepTag);
      }
      if(job.vision_connected){
        const visTag=document.createElement('span');
        visTag.className='history-tag tag-vision';
        visTag.textContent='👁 비전 지판';
        metaRow.append(visTag);
      }
      if(timeStr){
        const timeTag=document.createElement('span');
        timeTag.className='history-meta-time';
        timeTag.textContent=timeStr;
        metaRow.append(timeTag);
      }

      const rawTag=document.createElement('span');
      rawTag.className='history-raw-name';
      rawTag.textContent=job.name;
      rawTag.title=job.name;
      metaRow.append(rawTag);

      content.append(titleRow,metaRow);

      const actionWrap=document.createElement('div');
      actionWrap.className='history-action-side';
      const button=document.createElement('button');
      button.type='button';
      button.className=`history-btn-open ${job.status}`;
      button.innerHTML=job.status==='complete'?'스튜디오 열기 ▶':job.status==='error'?'실패 사유 ℹ':'진행 확인 ↻';
      button.onclick=async()=>{
        if(loading)return;
        try{
          if(job.status==='complete')await openJob(job);
          else if(job.status==='error')notice(job.message);
          else{busy(true);$('#progress').hidden=false;watch(job.id);}
        }catch(e){notice(e.message);}
      };
      actionWrap.append(button);

      card.append(iconWrap,content,actionWrap);
      container.append(card);
    });
  }catch(e){notice(e.message);}
}
function returnToHome(){
  player.pause();
  if($('#workspace'))$('#workspace').hidden=true;
  if($('#progress'))$('#progress').hidden=true;
  if($('#intro'))$('#intro').hidden=false;
  if($('#drop'))$('#drop').hidden=false;
  if($('#calibrate-bar'))$('#calibrate-bar').hidden=true;
  notice('');
  loadHistory();
}

$('#file').onchange=event=>{if(event.target.files[0])start(event.target.files[0]);event.target.value='';};
if($('#demo'))$('#demo').onclick=()=>start(null);$('#refresh').onclick=loadHistory;
if($('#back-home-btn'))$('#back-home-btn').onclick=returnToHome;
if($('#bpm-auto'))$('#bpm-auto').onclick=()=>{if(!result)return;const autoBpm=result.tempo?.auto_bpm??result.tempo?.bpm??120;$('#bpm').value=autoBpm;rebuild();};
if($('#offset-auto'))$('#offset-auto').onclick=()=>{if(!result)return;const autoOffset=Number(result.tempo?.offset_s??0);$('#beat-offset').value=autoOffset.toFixed(2);rebuild();};
if($('#offset-minus'))$('#offset-minus').onclick=()=>{if(!result)return;const {bpm,offsetS}=activeTempo();const step=60/bpm/4;$('#beat-offset').value=(offsetS-step).toFixed(2);rebuild();};
if($('#offset-plus'))$('#offset-plus').onclick=()=>{if(!result)return;const {bpm,offsetS}=activeTempo();const step=60/bpm/4;$('#beat-offset').value=(offsetS+step).toFixed(2);rebuild();};
for(const type of ['dragenter','dragover'])$('#drop').addEventListener(type,e=>{e.preventDefault();$('#drop').classList.add('drag');});
$('#drop').ondragleave=()=>$('#drop').classList.remove('drag');$('#drop').ondrop=e=>{e.preventDefault();$('#drop').classList.remove('drag');if(e.dataTransfer.files[0])start(e.dataTransfer.files[0]);};
for(const selector of ['#window','#notation','#capo','#bpm','#beat-offset','#beat-grid','#context','#onset','#vision','#skeleton']){const el=$(selector);if(el)el.onchange=()=>{let capo=Number($('#capo').value);$('#capo').value=Number.isFinite(capo)?Math.min(12,Math.max(0,Math.round(capo))):0;if(result)rebuild();};}
player.addEventListener('timeupdate',update);player.addEventListener('seeked',update);
player.addEventListener('play',()=>{function tick(){update();if(!player.paused&&!player.ended)requestAnimationFrame(tick);}requestAnimationFrame(tick);});

function initSidebar(){
  const toggle=$('#sidebar-toggle');
  if(!toggle)return;
  const label=$('.toggle-label');
  const hasStorage=typeof localStorage!=='undefined';
  const isCollapsed=hasStorage&&localStorage.getItem('chord_studio_sidebar_collapsed')==='1';
  if(isCollapsed){
    document.body.classList.add('sidebar-collapsed');
    toggle.title='사이드바 펼치기';
    if(label)label.textContent='사이드바 펼치기';
  }
  toggle.onclick=()=>{
    const collapsed=document.body.classList.toggle('sidebar-collapsed');
    toggle.title=collapsed?'사이드바 펼치기':'사이드바 접기';
    if(label)label.textContent=collapsed?'사이드바 펼치기':'사이드바 접기';
    if(hasStorage)localStorage.setItem('chord_studio_sidebar_collapsed',collapsed?'1':'0');
  };
  const nav=$('.nav');
  if(nav){
    nav.onclick=()=>{
      if($('#workspace')&&!$('#workspace').hidden){
        returnToHome();
      }
    };
  }
  const brand=$('.brand');
  if(brand){
    brand.onclick=e=>{
      if(document.body.classList.contains('sidebar-collapsed')){
        e.preventDefault();
        document.body.classList.remove('sidebar-collapsed');
        toggle.title='사이드바 접기';
        if(label)label.textContent='사이드바 접기';
        if(hasStorage)localStorage.setItem('chord_studio_sidebar_collapsed','0');
      }
      if($('#workspace')&&!$('#workspace').hidden){
        e.preventDefault();
        returnToHome();
      }
    };
  }
}
initSidebar();
initDualViewSwitcher();
loadHistory();
