"""Overlay frozen audio chord candidates below the original video, preserving TAB.

No hand inference, smoothing, hidden corrections, or reference-fed predictions.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from temporal_audio_pool import pooled_chroma
from guitarset_benchmark import rank_saliences,TEMPLATES
from harmony_engine import SUFFIX

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dataset/integration_review/runs/actual_video_review_20261105_v1'
SHARP=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

def shape(c,capo=1):return SHARP[(c['root_pc']-capo)%12]+SUFFIX.get(c['quality'],c['quality'])

def predictions(grid,frames,queries,width):
    valid=(queries-width/2>=grid[0])&(queries+width/2<=grid[-1]);sal=np.zeros((len(queries),12))
    sal[valid]=pooled_chroma(grid,frames,queries[valid],width)
    scores,order,usable=rank_saliences(sal);rows=[]
    for i in range(len(queries)):
        top=[dict(TEMPLATES[j],score=float(scores[i,j]),capo1_shape=shape(TEMPLATES[j])) for j in order[i,:3]] if usable[i] else []
        ties=int(np.isclose(scores[i],scores[i,order[i,0]],atol=1e-10,rtol=0).sum()) if usable[i] else 0
        rows.append(dict(top3=top,tied_top1_count=ties,status='audio_edge_no_full_window' if not valid[i] else 'provisional' if usable[i] else 'insufficient_note_evidence'))
    return rows

def render_case(video,all_pts,case,fonts):
    start,end=case['start'],case['end'];selected=np.flatnonzero((all_pts>=start-1e-8)&(all_pts<end-1e-8));pts=all_pts[selected]
    if not len(selected) or np.any(np.diff(selected)!=1):raise ValueError('Non-contiguous video interval')
    meta=json.loads(case['prediction'].with_suffix('.json').read_text());assert hashlib.sha256(case['guitar'].read_bytes()).hexdigest()==meta['source_sha256']
    with np.load(case['prediction']) as d:rows={str(w):predictions(d['times'],d['note'],pts-start,w) for w in [.2,.4]}
    refs=json.loads(case['references'].read_text())['references'];cap=cv2.VideoCapture(str(video));cap.set(cv2.CAP_PROP_POS_FRAMES,int(selected[0]));width,height=1280,940
    target=OUT/(case['id']+'_original.mp4');logpath=target.with_suffix('.ffmpeg.log')
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pixel_format','bgr24','-video_size',f'{width}x{height}','-framerate','24','-i','pipe:0','-i',str(case['mixture']),'-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',str(target)]
    timeline=[]
    with logpath.open('wb') as log:
        process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
        for k,t in enumerate(pts):
            ok,original=cap.read()
            if not ok or original.shape[:2]!=(720,1280):raise ValueError('Unexpected source frame')
            panel=Image.new('RGB',(1280,220),(19,25,34));draw=ImageDraw.Draw(panel)
            draw.text((18,5),f'실제 영상 적용  |  원본 {int(t//60):02d}:{t%60:05.2f}  |  오디오 후보 · 카포 1 환산',font=fonts['small'],fill=(225,232,241))
            draw.line([(640,38),(640,173)],fill=(60,70,82),width=1)
            for col,key in enumerate(['0.2','0.4']):
                x=18+col*640;r=rows[key][k];top=r['top3'];color=(92,210,211) if col==0 else (246,184,99)
                title=f'{key}초 고정창'+(f" · 1위 동점 {r['tied_top1_count']}개" if r['tied_top1_count']>1 else '')
                draw.text((x,39),title,font=fonts['small'],fill=color)
                if top:
                    draw.text((x,70),f"운지표기 {top[0]['capo1_shape']}  /  실음 {top[0]['symbol']}",font=fonts['big'],fill=(245,247,250))
                    draw.text((x,116),'다음 후보: '+' · '.join(f"{c['capo1_shape']} / {c['symbol']}" for c in top[1:]),font=fonts['tiny'],fill=(181,190,204))
                    draw.text((x,143),'잠정 후보 · 점수는 확률이 아님',font=fonts['tiny'],fill=(139,153,172))
                else:
                    message='분석 구간 가장자리' if r['status']=='audio_edge_no_full_window' else '음 근거 부족 · 보류'
                    draw.text((x,76),message,font=fonts['big'],fill=(184,192,204))
            draw.line([(0,180),(1280,180)],fill=(65,75,88),width=1)
            ref=next((r for r in refs if r.get('stable_interval',[r['pts']-.2,r['pts']+.2])[0]<=t<=r.get('stable_interval',[r['pts']-.2,r['pts']+.2])[1]),None)
            if ref:
                matches=[]
                for key in ['0.2','0.4']:
                    top=rows[key][k]['top3'];matches.append(key+'초 '+('참조 일치' if top and top[0]['root_pc']==ref['concert_root_pc'] and top[0]['quality']==ref['quality'] else '불일치/보류'))
                text=f"검수 참조 ({ref['pts']:.0f}초 주변): {ref['shape']} → {ref['concert_symbol']}  |  "+' · '.join(matches)
            else:text='이 시점은 별도 정답 미검수 · 원본 화면의 코드/TAB과 비교하세요.'
            draw.text((18,186),text,font=fonts['tiny'],fill=(198,207,219))
            combined=np.vstack([original,cv2.cvtColor(np.asarray(panel),cv2.COLOR_RGB2BGR)])
            process.stdin.write(combined.tobytes())
            timeline.append(dict(video_pts_s=float(t),source_frame_index=int(selected[k]),predictions={key:rows[key][k] for key in rows},review_reference=ref))
            if abs(t-211)<.001 or abs(t-257)<.001:cv2.imwrite(str(OUT/(case['id']+'_preview.png')),combined)
        process.stdin.close();code=process.wait();cap.release()
    if code:raise RuntimeError(logpath.read_text(errors='replace'))
    guitar_target=OUT/(case['id']+'_guitar.mp4')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-i',str(target),'-i',str(case['guitar']),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',str(guitar_target)],check=True)
    (OUT/(case['id']+'_timeline.json')).write_text(json.dumps(timeline,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Rendered',case['id'],len(timeline),'frames',flush=True)
    return dict(id=case['id'],start_s=start,end_s=end,frame_count=len(timeline),source_first_frame=int(selected[0]),source_last_frame=int(selected[-1]),
        original_video=target.name,guitar_video=guitar_target.name,original_audio_sha256=hashlib.sha256(case['mixture'].read_bytes()).hexdigest(),guitar_audio_sha256=meta['source_sha256'],
        audio_prediction_sha256=hashlib.sha256(case['prediction'].read_bytes()).hexdigest())

def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True);read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    manifest=read(ROOT/'dataset/audio_analysis/runs/barre_194_226_mix_20261104_v1/manifest.json');video=Path(manifest['source_path'])
    if hashlib.sha256(video.read_bytes()).hexdigest()!=manifest['source_id']:raise ValueError('Source video changed')
    data=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(video)],text=True,encoding='utf-8'));pts=np.array([float(f['best_effort_timestamp_time']) for f in data['frames']])
    font='C:/Windows/Fonts/malgun.ttf';fonts={k:ImageFont.truetype(font,size) for k,size in [('big',31),('small',21),('tiny',17)]}
    cases=[dict(id='barre_194_226',start=194.,end=226.,prediction=ROOT/'dataset/integration_review/runs/basic_pitch_20261105_v2/predictions/tutorial_raw.npz',
        mixture=ROOT/'dataset/audio_analysis/runs/barre_194_226_mix_20261104_v1/original.wav',guitar=ROOT/'dataset/audio_analysis/runs/barre_194_226_guitar_6s_20261105_v1/htdemucs_6s/original/guitar.wav',references=ROOT/'dataset/integration_review/runs/tutorial_accuracy_20261105_v1/references.json'),
        dict(id='new_250_266',start=250.,end=266.,prediction=ROOT/'dataset/integration_review/runs/change_aware_audio_20261105_v2/new_predictions/new_tutorial_raw.npz',
        mixture=ROOT/'dataset/audio_analysis/runs/new_250_266_mix_20261105_v1/original.wav',guitar=ROOT/'dataset/audio_analysis/runs/new_250_266_guitar_20261105_v1/htdemucs_6s/original/guitar.wav',references=ROOT/'dataset/integration_review/runs/change_aware_audio_20261105_v2/new_references.json')]
    results=[render_case(video,pts,c,fonts) for c in cases]
    metadata=dict(source_video=str(video),source_sha256=manifest['source_id'],engine='Frozen BasicPitch raw input; output D2-E6; max0.2/0.4s; unchanged coverage scorer',
        video='Original1280x720 unchanged,220px analysis panel appended below;24fps',reference_policy='Only reviewed time windows shown; reference never enters prediction',
        limitations=['Offline centered pooling and underlying2scontext','No hand/board fusion or contact conclusions','Decoded source PTS and sample mapped audio; no fitted offset','No prediction smoothing or correct-answer substitution'],cases=results,
        source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (OUT/'manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    html='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>실제 영상 코드 검수</title><style>body{font:16px system-ui;background:#111923;color:#edf1f7;max-width:1280px;margin:24px auto;padding:0 16px}video{width:100%;max-height:78vh;background:#000}button,select{font:inherit;padding:8px;margin:6px 8px 8px 0;background:#243244;color:inherit;border:1px solid #506079;border-radius:6px}p{color:#c8d2df;line-height:1.7}</style><h1>실제 영상에서 코드 후보 확인</h1><p>원본 화면 아래에 0.2초·0.4초 판별을 나란히 표시했습니다. ‘운지표기’는 카포 1을 반영한 환산값이며 손 검출 결과가 아닙니다.</p><select id="segment"><option value="barre_194_226">기존 구간 3:14~3:46</option><option value="new_250_266">새 구간 4:10~4:26</option></select><select id="audio"><option value="original">원본 소리</option><option value="guitar">기타 추정음</option></select><video id="player" controls preload="metadata" src="barre_194_226_original.mp4" poster="barre_194_226_preview.png"></video><div id="jumps"></div><p>흰색 큰 글씨는 모델의 잠정 후보입니다. 영상에 원래 표시된 코드와 비교하세요. 검수 참조는 미리 확인한 시점 주변에서만 표시됩니다. 두 입력 소리는 비교 재생용이며, 판별은 모두 기타 추정음을 사용합니다.</p><script>const v=document.querySelector('#player'),s=document.querySelector('#segment'),a=document.querySelector('#audio'),j=document.querySelector('#jumps');function load(keep){let t=keep?v.currentTime:0,play=!v.paused;v.src=s.value+'_'+a.value+'.mp4';v.onloadedmetadata=()=>{v.currentTime=t;if(play)v.play().catch(()=>{});};let start=s.value.startsWith('barre')?194:250,marks=start===194?[195,199,207,209,211,221,223,225]:[253,257,259,261];j.replaceChildren();marks.forEach(p=>{let b=document.createElement('button');b.textContent=Math.floor(p/60)+':'+String(p%60).padStart(2,'0');b.onclick=()=>{v.currentTime=Math.max(0,p-start-.5);v.play().catch(()=>{});};j.append(b);});}s.onchange=()=>load(false);a.onchange=()=>load(true);load(false);</script></html>'''
    (OUT/'review.html').write_text(html,encoding='utf-8')

if __name__=='__main__':main()
