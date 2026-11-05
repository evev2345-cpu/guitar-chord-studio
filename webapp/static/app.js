'use strict';
const $=s=>document.querySelector(s), player=$('#player');
const names=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
let result=null,currentJob=null,rows=[],segments=[],loading=false,selection=0,lastRendered=-1;
const clock=t=>`${String(Math.floor(t/60)).padStart(2,'0')}:${String(Math.floor(t%60)).padStart(2,'0')}`;
function label(c,shape=$('#notation').value==='shape'){
  if(!c)return '—';
  return shape?names[(c.root_pc-Number($('#capo').value)+12)%12]+c.symbol.slice(names[c.root_pc].length):c.symbol;
}
async function api(url,options){const response=await fetch(url,options);const data=await response.json();if(!response.ok)throw Error(data.error||'요청에 실패했습니다.');return data;}
function notice(text=''){$('#notice').textContent=text;}
function busy(value){loading=value;$('#demo').disabled=value;$('#file').disabled=value;}
function identity(c){return c?`${c.root_pc}:${c.quality}`:'none';}
function display(row){
  if(!row)return [];
  const top=row.top3, chosen=row.display.display_candidate;
  if(top.length>1 && row.tied_top1_count>1){
    const tied=top.filter(c=>Math.abs(c.score-top[0].score)<=1e-10);
    if(tied.length>1)return tied;
  }
  return chosen?[chosen]:[];
}
function signature(row){return display(row).map(identity).join('|')||'none';}
function rebuild(){
  lastRendered=-1;
  rows=result.branches[$('#window').value];segments=[];
  rows.forEach((row,i)=>{const prev=segments.at(-1),key=signature(row);if(prev&&prev.key===key)prev.end=row.time_s+1/24;else segments.push({key,start:row.time_s,end:row.time_s+1/24,row,index:i});});
  const container=$('#timeline');container.replaceChildren();
  segments.forEach((segment,i)=>{const button=document.createElement('button');const text=display(segment.row).map(c=>label(c)).join(' / ')||'보류';button.textContent=text;button.title=`${clock(segment.start)} · ${text}`;button.style.width=`${Math.max(56,(segment.end-segment.start)/result.duration_s*1000)}px`;button.classList.toggle('unknown',segment.key==='none');button.onclick=()=>{player.currentTime=segment.start;update();};segment.button=button;container.append(button);});
  update();
}
function update(){
  if(!rows.length)return;
  const time=Math.min(player.currentTime,Math.max(0,result.duration_s-1e-6));
  $('#clock').textContent=`${clock(player.currentTime)} / ${clock(result.duration_s)}`;
  let low=0,high=rows.length-1;
  while(low<high){const mid=Math.ceil((low+high)/2);if(rows[mid].time_s<=time)low=mid;else high=mid-1;}
  if(low===lastRendered)return;
  lastRendered=low;
  const row=rows[low],choices=display(row),text=choices.map(c=>label(c)).join(' / ')||'보류';
  $('#chord').textContent=$('#overlay-chord').textContent=text;
  const tied=choices.length>1;
  $('#state').textContent=$('#overlay-caption').textContent=tied?`동점 ${row.tied_top1_count}개 · 근음 확정 보류`:'현재 코드 후보';
  $('#other-name').textContent=choices.length?(`${$('#notation').value==='shape'?'실음':'운지'}: `+choices.map(c=>label(c,$('#notation').value!=='shape')).join(' / ')):'현재 음 근거가 부족합니다.';
  const status=row.display.status;
  const message=status==='bridged_short_dropout'?'짧은 보류 연결 · 현재 근거 부족':status.startsWith('removed_')?'앞뒤 근거로 짧은 표시 튐 정리':row.status==='audio_edge_no_full_window'?'분석 구간 가장자리':tied?'오디오만으로 순위를 정할 수 없는 후보':'잠정 후보 · 오디오 기반';
  $('#overlay-sub').textContent=message;
  const container=$('#candidates');container.replaceChildren();
  row.top3.forEach(c=>{const div=document.createElement('div');div.className='candidate';const title=document.createElement('strong'),score=document.createElement('span');title.textContent=label(c);score.textContent=c.score.toFixed(3);div.append(title,score);container.append(div);});
  const index=segments.findIndex(s=>s.start<=time&&s.end>time);
  if(index!==selection){segments[selection]?.button.classList.remove('active');selection=index;}
  segments[index]?.button.classList.add('active');
  $('#next').textContent=segments[index+1]?display(segments[index+1].row).map(c=>label(c)).join(' / ')||'보류':'—';
}
async function openJob(job){
  const data=await api(job.result_url);currentJob=job;result=data;player.pause();player.src=job.media_url;
  $('.stage').classList.toggle('audio',job.media_url.endsWith('.wav'));$('#track-name').textContent=job.name;
  $('#download').href=job.result_url;$('#end-time').textContent=clock(data.duration_s);$('#workspace').hidden=false;
  $('#intro').hidden=true;rebuild();
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
  if(file && file.size>150*1024*1024){notice('150MB 이하의 파일을 선택해 주세요.');return;}
  busy(true);notice();$('#progress').hidden=false;$('#bar').value=0;$('#percent').textContent='0%';$('#progress-message').textContent=file?'파일을 업로드하는 중':'샘플 결과 준비 중';
  if(file)$('#file-name').textContent=file.name;
  try{const job=await api(file?`/api/jobs?name=${encodeURIComponent(file.name)}`:'/api/demo',{method:'POST',body:file||null});watch(job.id);}catch(e){notice(e.message);$('#progress').hidden=true;busy(false);}
}
async function loadHistory(){
  try{const jobs=await api('/api/jobs');const container=$('#history');container.replaceChildren();if(!jobs.length){container.textContent='아직 분석한 파일이 없습니다.';return;}
    jobs.sort((a,b)=>b.created_at-a.created_at).slice(0,12).forEach(job=>{const div=document.createElement('div');div.className='history-row';const title=document.createElement('span'),button=document.createElement('button');title.textContent=job.name;button.textContent=job.status==='complete'?'결과 열기':job.status==='error'?'실패 사유':'진행 확인';button.onclick=async()=>{if(loading)return;try{if(job.status==='complete')await openJob(job);else if(job.status==='error')notice(job.message);else{busy(true);$('#progress').hidden=false;watch(job.id);}}catch(e){notice(e.message);}};div.append(title,button);container.append(div);});
  }catch(e){notice(e.message);}
}
$('#file').onchange=event=>{if(event.target.files[0])start(event.target.files[0]);event.target.value='';};
$('#demo').onclick=()=>start(null);$('#refresh').onclick=loadHistory;
for(const type of ['dragenter','dragover'])$('#drop').addEventListener(type,e=>{e.preventDefault();$('#drop').classList.add('drag');});
$('#drop').ondragleave=()=>$('#drop').classList.remove('drag');$('#drop').ondrop=e=>{e.preventDefault();$('#drop').classList.remove('drag');if(e.dataTransfer.files[0])start(e.dataTransfer.files[0]);};
for(const selector of ['#window','#notation','#capo'])$(selector).onchange=()=>{let capo=Number($('#capo').value);$('#capo').value=Number.isFinite(capo)?Math.min(12,Math.max(0,Math.round(capo))):0;if(result)rebuild();};
player.addEventListener('timeupdate',update);player.addEventListener('seeked',update);player.addEventListener('error',()=>notice('미디어를 재생하지 못했습니다. 분석 결과는 타임라인과 JSON에서 확인할 수 있습니다.'));
player.addEventListener('play',()=>{function tick(){update();if(!player.paused&&!player.ended)requestAnimationFrame(tick);}requestAnimationFrame(tick);});
loadHistory();
