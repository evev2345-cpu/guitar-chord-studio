"""Show unresolved equal-PC roots together rather than silently picking one."""
import json
import subprocess
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from visual_root_tiebreak import resolve

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dataset/integration_review/runs/visual_root_tie_20261105_v1'

def main():
    output=OUT/'root_ambiguity_208_218.mp4'
    if output.exists():raise FileExistsError(output)
    base=ROOT/'dataset/integration_review/runs/stable_video_review_20261105_v2';source=base/'first_watch_208_218.mp4';timeline=json.loads((base/'barre_194_226_timeline.json').read_text());rows=[r for r in timeline if 208<=r['video_pts_s']<218]
    cap=cv2.VideoCapture(str(source));font='C:/Windows/Fonts/malgun.ttf';big=ImageFont.truetype(font,29);small=ImageFont.truetype(font,19)
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pixel_format','bgr24','-video_size','1280x940','-framerate','24','-i','pipe:0','-i',str(source),'-map','0:v','-map','1:a','-c:v','libx264','-crf','20','-preset','fast','-pix_fmt','yuv420p','-c:a','copy','-shortest','-movflags','+faststart',str(output)];changed=[]
    with (OUT/'video.ffmpeg.log').open('wb') as log:
        process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
        for r in rows:
            ok,im=cap.read()
            if not ok:raise RuntimeError('Clip decode failed')
            decision=resolve(r['predictions']['0.2']['top3'],visual_status='unknown');group=decision['tie_group']
            if len(group)>1:
                panel=Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB));draw=ImageDraw.Draw(panel);draw.rectangle((645,754,1279,898),fill=(19,25,34))
                draw.text((658,758),'동일 구성음 동점 · 근음 미확정',font=small,fill=(245,193,102))
                draw.text((658,791),'운지표기 '+' · '.join(c['capo1_shape'] for c in group),font=big,fill=(244,247,250))
                draw.text((658,829),'실음 '+' · '.join(c['symbol'] for c in group),font=big,fill=(244,247,250))
                draw.text((658,871),'비전 근거가 미확정이므로 두 후보 유지',font=small,fill=(194,205,222));im=cv2.cvtColor(np.array(panel),cv2.COLOR_RGB2BGR);changed.append(r['video_pts_s'])
            process.stdin.write(im.tobytes())
            if abs(r['video_pts_s']-214)<.001:cv2.imwrite(str(OUT/'root_ambiguity_preview.png'),im)
        process.stdin.close();code=process.wait();cap.release()
    if code:raise RuntimeError('Video encoding failed')
    (OUT/'video_audit.json').write_text(json.dumps(dict(frames=len(rows),modified_display_pts=changed,ranking_changed=False,source_video_start_s=208,
         scope='Display equal-score identical-PC candidates together; no confirmed root inferred from unreliable vision'),indent=2),encoding='utf-8');print('Rendered ambiguity review',len(rows),'frames')

if __name__=='__main__':main()
