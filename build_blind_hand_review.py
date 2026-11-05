"""Generate a model-blind, local-only manual landmark review artifact."""
import base64
import json
from pathlib import Path


def main():
    cases=[]
    for path in sorted(Path('dataset/chord_video_review').glob('*_tracking.json')):
        track=json.loads(path.read_text())
        cases.append(dict(case_id=path.stem,image='data:image/png;base64,'+base64.b64encode(Path(track['image']).read_bytes()).decode(),
                          image_sha256=__import__('hashlib').sha256(Path(track['image']).read_bytes()).hexdigest(),
                          wrists=[dict(hand_index=h['hand_index'],pixel=h['landmarks'][0]['pixel']) for h in track['hands']]))
    html='''<!doctype html><meta charset="utf-8"><title>독립 손 검수</title>
<style>body{background:#182028;color:#eee;font:16px sans-serif;margin:20px}button,input{padding:8px;margin:4px}canvas{max-width:100%;cursor:crosshair;border:1px solid #667}p{max-width:1000px}</style>
<h2>원본 기반 독립 손 검수 — 예측 골격은 표시하지 않습니다</h2>
<p>운지 손만 라벨링합니다. 먼저 손목(0)을 찍고, 각 관절을 선택해 클릭하세요. 좌표는 원본 픽셀로 저장됩니다. 보이지 않는 점은 가림/미확정으로 두세요. 손끝은 보이는 말단 패드 중심으로 일관되게 표시합니다. TAB나 예상 코드를 근거로 가려진 좌표를 추측하지 마세요.</p>
<label>검수자 <input id="reviewer" placeholder="이름/식별자"></label><button id="prev">이전 사진</button><button id="next">다음 사진</button><button id="save">검수 JSON 내려받기</button>
<div id="case"></div><div id="points"></div><button id="hidden">가림</button><button id="unknown">미확정</button><div id="current"></div><canvas id="canvas" width="1280" height="720"></canvas>
<script>
const cases=DATA; const names=['손목','엄지 CMC','엄지 MCP','엄지 IP','엄지 끝','검지 MCP','검지 PIP','검지 DIP','검지 끝','중지 MCP','중지 PIP','중지 DIP','중지 끝','약지 MCP','약지 PIP','약지 DIP','약지 끝','소지 MCP','소지 PIP','소지 DIP','소지 끝'];
let ci=0,pi=0; const rows=cases.map(c=>({case_id:c.case_id,review_status:'pending',reviewer:'',model_blind:true,image_sha256:c.image_sha256,fretting_hand_index:null,landmarks:names.map((n,i)=>({index:i,pixel:null,visibility:'unreviewed'}))}));
const canvas=document.getElementById('canvas'),ctx=canvas.getContext('2d'),image=new Image(); image.onload=draw;
function draw(){ctx.drawImage(image,0,0); for(const l of rows[ci].landmarks){if(!l.pixel)continue;ctx.fillStyle='#00ffcc';ctx.beginPath();ctx.arc(...l.pixel,4,0,7);ctx.fill();ctx.font='16px sans-serif';ctx.fillText(l.index,l.pixel[0]+7,l.pixel[1]);}document.getElementById('case').textContent=cases[ci].case_id+' ('+(ci+1)+'/6)';document.getElementById('current').textContent=pi+': '+names[pi]+' / '+rows[ci].landmarks[pi].visibility;}
for(let i=0;i<21;i++){const b=document.createElement('button');b.textContent=i+' '+names[i];b.onclick=()=>{pi=i;draw()};document.getElementById('points').append(b)}
function show(){image.src=cases[ci].image}document.getElementById('prev').onclick=()=>{ci=(ci+5)%6;show()};document.getElementById('next').onclick=()=>{ci=(ci+1)%6;show()};
canvas.onclick=e=>{const r=canvas.getBoundingClientRect();rows[ci].landmarks[pi]={index:pi,pixel:[(e.clientX-r.left)*1280/r.width,(e.clientY-r.top)*720/r.height],visibility:'visible'};pi=Math.min(20,pi+1);draw()};
for(const state of ['hidden','unknown'])document.getElementById(state).onclick=()=>{rows[ci].landmarks[pi]={index:pi,pixel:null,visibility:state};pi=Math.min(20,pi+1);draw()};
document.getElementById('save').onclick=()=>{const reviewer=document.getElementById('reviewer').value.trim();if(!reviewer){alert('검수자 식별자를 입력하세요');return;}const output=rows.map((r,i)=>{const wrist=r.landmarks[0].pixel;let hand=null;if(wrist&&cases[i].wrists.length){const ranked=cases[i].wrists.map(h=>({...h,d:Math.hypot(h.pixel[0]-wrist[0],h.pixel[1]-wrist[1])})).sort((a,b)=>a.d-b.d);if(ranked[0].d<50)hand=ranked[0].hand_index;}return {...r,reviewer,review_status:r.landmarks.some(l=>l.visibility!=='unreviewed')?'reviewed':'pending',fretting_hand_index:hand,hand_assignment_basis:'nearest independently labeled wrist within 50px; null if none',point_definition:'visible distal pad center / visible joint center'};});const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(output,null,2)],{type:'application/json'}));a.download='independent_hand_review.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};show();
</script>'''.replace('DATA',json.dumps(cases,ensure_ascii=True))
    out=Path('dataset/chord_sequence_review');out.mkdir(parents=True,exist_ok=True)
    (out/'independent_review.html').write_text(html,encoding='utf-8')
    (out/'independent_review_status.json').write_text(json.dumps(dict(planned_points=126,images=6,
        independent_reviewed_points=0,status='awaiting_human_model_blind_annotation',
        existing_agent_provisional_points=4),indent=2),encoding='utf-8')


if __name__=='__main__':main()
