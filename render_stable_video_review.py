"""Render before/after conservative display cleanup on the same original footage."""
import json
import subprocess
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from evaluate_chord_display import ROOT,BASE
from chord_display_stabilizer import identity

OUT=ROOT/'dataset/integration_review/runs/stable_video_review_20261105_v2'
STATUS={'provisional':'현재 음 근거의 잠정 후보','retained_top_score_tie':'동점 중 직전 후보 유지',
        'removed_isolated_spike':'앞뒤가 같은 짧은 튐 정리','removed_isolated_extension':'짧게 튄 확장 코드 정리',
        'bridged_short_dropout':'짧은 음 부족 연결 · 현재 근거는 부족','insufficient_note_evidence':'음 근거 부족 · 보류','audio_edge_no_full_window':'분석 구간 가장자리'}

def label(c):return f"운지표기 {c['capo1_shape']}  /  실음 {c['symbol']}" if c else '음 근거 부족 · 보류'

def main():
    if (OUT/'video_manifest.json').exists():raise FileExistsError(OUT)
    manifest=json.loads((BASE/'manifest.json').read_text());source=Path(manifest['source_video']);fonts={k:ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',s) for k,s in [('big',31),('small',21),('tiny',17)]};videos=[]
    for case in manifest['cases']:
        rows=json.loads((OUT/(case['id']+'_timeline.json')).read_text());cap=cv2.VideoCapture(str(source));cap.set(cv2.CAP_PROP_POS_FRAMES,rows[0]['source_frame_index'])
        for key in ['0.2','0.4']:
            cap.set(cv2.CAP_PROP_POS_FRAMES,rows[0]['source_frame_index']);tag=case['id']+'_w'+key.replace('.','');target=OUT/(tag+'_original.mp4')
            # Original review audio is copied, so before/after share the same sound.
            cmd=['ffmpeg','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pixel_format','bgr24','-video_size','1280x940','-framerate','24','-i','pipe:0','-i',str(BASE/case['original_video']),'-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','copy','-shortest','-movflags','+faststart',str(target)]
            with (OUT/(tag+'.ffmpeg.log')).open('wb') as log:
                process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
                for i,r in enumerate(rows):
                    ok,frame=cap.read()
                    if not ok:raise ValueError('Source decode failed')
                    raw=r['predictions'][key];display=r['stable_predictions'][key];before=raw['top3'][0] if raw['top3'] else None;after=display['display_candidate'];t=r['video_pts_s']
                    panel=Image.new('RGB',(1280,220),(19,25,34));draw=ImageDraw.Draw(panel);draw.text((18,5),f"실제 영상 · {int(t//60):02d}:{t%60:05.2f}  |  같은 {key}초 오디오 후보의 표시 전후",font=fonts['small'],fill=(225,232,241));draw.line([(640,37),(640,178)],fill=(65,76,90))
                    for col,(title,c,color) in enumerate([('수정 전',before,(160,183,209)),('수정 후 · 보수적 정리',after,(94,218,194))]):
                        x=18+col*640;draw.text((x,39),title,font=fonts['small'],fill=color);draw.text((x,72),label(c),font=fonts['big'],fill=(245,247,250) if c else (172,185,202))
                    draw.text((18,119),'현재 오디오 후보: '+' · '.join(c['capo1_shape'] for c in raw['top3']),font=fonts['tiny'],fill=(174,187,204))
                    draw.text((658,119),STATUS.get(display['status'],display['status']),font=fonts['tiny'],fill=(245,195,110) if display['status']!='provisional' else (174,187,204))
                    if identity(before)!=identity(after):draw.text((658,145),'표시 정리 적용 · 원래 후보는 왼쪽에 보존',font=fonts['tiny'],fill=(245,195,110))
                    else:draw.text((658,145),'오디오 모델·코드 채점은 동일',font=fonts['tiny'],fill=(140,157,179))
                    draw.line([(0,181),(1280,181)],fill=(65,76,90));ref=r['review_reference']
                    if ref:
                        target_id=(ref['concert_root_pc'],ref['quality']);tail=f"검수 참조: {ref['shape']} → {ref['concert_symbol']}  |  수정 전 {'일치' if identity(before)==target_id else '불일치/보류'} · 수정 후 {'일치' if identity(after)==target_id else '불일치/보류'}"
                    else:tail='운지표기는 카포 1 환산값 · 이 시점은 별도 정답 미검수 · 잠정 후보'
                    draw.text((18,186),tail,font=fonts['tiny'],fill=(198,208,221));combined=np.vstack([frame,cv2.cvtColor(np.asarray(panel),cv2.COLOR_RGB2BGR)]);process.stdin.write(combined.tobytes())
                    if key=='0.2' and abs(t-(215.416667 if case['start_s']==194 else 259.041667))<.001:cv2.imwrite(str(OUT/(case['id']+'_preview.png')),combined)
                process.stdin.close();code=process.wait()
                if code:raise RuntimeError('Video encoding failed')
            guitar_target=OUT/(tag+'_guitar.mp4');subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-i',str(target),'-i',str(BASE/case['guitar_video']),'-map','0:v:0','-map','1:a:0','-c','copy','-shortest','-movflags','+faststart',str(guitar_target)],check=True)
            videos.append(dict(case=case['id'],window=key,original=target.name,guitar=guitar_target.name,frames=len(rows)))
            print('Rendered',tag,flush=True)
        cap.release()
    # A short before/after excerpt includes the real isolated glitch near215.42s.
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-ss','14','-i',str(OUT/'barre_194_226_w02_original.mp4'),'-t','10','-c:v','libx264','-preset','fast','-crf','20','-c:a','aac','-movflags','+faststart',str(OUT/'first_watch_208_218.mp4')],check=True)
    (OUT/'video_manifest.json').write_text(json.dumps(dict(videos=videos,mode='Before/after display only; same audio and model; original top720pixels preserved',offline_lookahead=True),indent=2),encoding='utf-8')
    html='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>코드 표시 수정 전후</title><style>body{font:16px system-ui;background:#111923;color:#edf1f7;max-width:1280px;margin:24px auto;padding:0 16px}video{width:100%;max-height:78vh}select,button{font:inherit;padding:8px;margin:6px 8px 8px 0;background:#26364a;color:inherit;border:1px solid #526078;border-radius:6px}p{color:#c8d2df;line-height:1.7}a{color:#8bd8d3}</style><h1>코드 표시 수정 전후</h1><p>왼쪽은 기존 표시, 오른쪽은 짧은 튐·잠깐의 보류·동점을 보수적으로 정리한 표시입니다. 실제 코드 전환에 일괄 대기시간을 붙이지 않았습니다.</p><a href="first_watch_208_218.mp4">먼저 10초 보기 · 3:28~3:38</a><br><select id="segment"><option value="barre_194_226">기존 3:14~3:46</option><option value="new_250_266">새 구간 4:10~4:26</option></select><select id="width"><option value="02">0.2초</option><option value="04">0.4초</option></select><select id="audio"><option value="original">원본 소리</option><option value="guitar">기타 추정음</option></select><video id="v" controls preload="metadata"></video><div id="jump"></div><p>짧은 보류를 연결한 순간에는 ‘현재 근거는 부족’이라고 표시합니다. 긴 보류나 근거가 다른 코드까지 임의로 채우지 않습니다. 두 패널은 같은 소리를 사용합니다.</p><script>const v=document.querySelector('#v'),s=document.querySelector('#segment'),w=document.querySelector('#width'),a=document.querySelector('#audio'),j=document.querySelector('#jump');function load(keep){const t=keep?v.currentTime:0,play=!v.paused;v.src=s.value+'_w'+w.value+'_'+a.value+'.mp4';v.onloadedmetadata=()=>{v.currentTime=t;if(play)v.play().catch(()=>{});};j.replaceChildren();let start=s.value.startsWith('barre')?194:250,marks=start===194?[197.75,207.29,215.42,220.88]:[253.88,254.54,257.13,259.04];marks.forEach(p=>{let b=document.createElement('button');b.textContent=Math.floor(p/60)+':'+(p%60).toFixed(2);b.onclick=()=>{v.currentTime=Math.max(0,p-start-.8);v.play().catch(()=>{});};j.append(b);});}s.onchange=()=>load(false);w.onchange=a.onchange=()=>load(true);load(false);</script></html>'''
    (OUT/'review.html').write_text(html,encoding='utf-8')

if __name__=='__main__':main()
