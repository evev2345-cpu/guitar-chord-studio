"""Raw-image and sequence diagnostics of full-frame VIDEO hand tracking."""
import json
from pathlib import Path
import subprocess
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image,ImageDraw,ImageFont
from improve_hand_skeleton import CHAINS,COLORS

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dataset/hand_analysis/runs/low_string_stability_20261105_v1'
METHODS=['baseline','multi_crop','video_tracking']

def summarize(rows):
    result={}
    for segment in ['middle_200','root_214','new_257']:
        group=[r for r in rows if r['segment']==segment];result[segment]={}
        for method in METHODS:
            points=[];times=[]
            for r in group:
                h=r['branches'][method]['hand']
                if h:points.append(np.array(h['pixel_landmarks']));times.append(r['pts'])
            p=np.array(points);delta=np.linalg.norm(np.diff(p[:,12]-p[:,0],axis=0),axis=1)
            contiguous=np.isclose(np.diff(times),1/24,atol=1e-5);delta=delta[contiguous]
            result[segment][method]=dict(total=len(group),detected=len(points),middle_wrist_relative_step_median_px=float(np.median(delta)),middle_wrist_relative_step_p90_px=float(np.percentile(delta,90)))
    stable=[r for r in rows if r['segment']=='root_214' and 213.75<=r['pts']<=214.083334]
    root={}
    for method in METHODS:
        values=[]
        for r in stable:
            s=r['branches'][method]['root_diagnostic']['support'];values.append(dict(pts=r['pts'],Am7_support=s['root_support'][9],C6_support=s['root_support'][0],low65_A=s['low65_support'][9]))
        root[method]=dict(frames=len(values),Am7_higher=sum(v['Am7_support']>v['C6_support'] for v in values),low65_A_at_least_0_05=sum(v['low65_A']>=.05 for v in values),values=values)
    return dict(segments=result,root_probe=root,limitations='Step size measures temporal variation, not ground-truth position error; wrist-relative removes translation only; original finger identity and contact remain unverified')

def main():
    data=json.loads((OUT/'result.json').read_text());rows=data['frames'];summary=summarize(rows);(OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    fig,axes=plt.subplots(3,3,figsize=(16,12))
    for i,t in enumerate([200.,214.,257.]):
        r=min(rows,key=lambda r:abs(r['pts']-t));im=cv2.cvtColor(cv2.imread(r['image']),cv2.COLOR_BGR2RGB)
        allp=[np.array(r['branches'][m]['hand']['pixel_landmarks']) for m in METHODS if r['branches'][m]['hand']];p=np.concatenate(allp);lo=p.min(axis=0)-25;hi=p.max(axis=0)+25
        axes[i,0].imshow(im);axes[i,0].set_title(f"Original PTS{r['pts']:.6f} / f{r['frame_index']}");axes[i,0].axis('off')
        for ax,method,title in zip(axes[i,1:],['baseline','video_tracking'],['Before: independent IMAGE','After: full-frame VIDEO tracking']):
            ax.imshow(im);h=r['branches'][method]['hand']
            if h:
                q=np.array(h['pixel_landmarks'])
                for name,chain in CHAINS.items():ax.plot(q[chain,0],q[chain,1],color=COLORS[name],lw=2)
                for tip in [8,12,16,20]:ax.scatter(q[tip,0],q[tip,1],s=20,color=COLORS[{8:'index',12:'middle',16:'ring',20:'pinky'}[tip]])
            ax.set_xlim(lo[0],hi[0]);ax.set_ylim(hi[1],lo[1]);ax.set_title(title);ax.axis('off')
    fig.suptitle('Raw observed skeletons only: index cyan / middle green / ring orange / pinky magenta; anatomy/contact UNVERIFIED');fig.tight_layout();fig.savefig(OUT/'before_after_original.png',dpi=145);plt.close(fig)
    group=[r for r in rows if r['segment']=='root_214'];fig,axes=plt.subplots(1,2,figsize=(12,4))
    for method in METHODS:
        found=[r for r in group if r['branches'][method]['hand']];t=[r['pts'] for r in found];p=np.array([r['branches'][method]['hand']['pixel_landmarks'] for r in found]);axes[0].plot(t,p[:,12,1]-p[:,0,1],label=method,marker='.',ms=3)
        values=[r['branches'][method]['root_diagnostic']['support'] for r in found];axes[1].plot(t,[v['root_support'][9]-v['root_support'][0] for v in values],label=method,marker='.',ms=3)
    axes[0].set_ylabel('Middle-tip y minus wrist y (px)');axes[1].set_ylabel('Am7 minus C6 weighted location support');axes[1].axhline(0,color='black',lw=.7)
    for ax in axes:ax.axvspan(213.75,214.083334,color='green',alpha=.08);ax.set_xlabel('Source time (s)');ax.legend(fontsize=8)
    axes[0].set_title('Motion/variation diagnostic, not position accuracy');axes[1].set_title('Root preference; middle remains weighted0.25');fig.tight_layout();fig.savefig(OUT/'temporal_metrics.png',dpi=145);plt.close(fig)
    # Real-time-speed source excerpt, no fitted audio offset; whole source remains above.
    clip=OUT/'root_213_214_5_before_after.mp4'
    if not clip.exists():
        rate=24;audio=ROOT/'dataset/audio_analysis/runs/barre_194_226_guitar_6s_20261105_v1/htdemucs_6s/original/guitar.wav'
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pixel_format','bgr24','-video_size','1280x1080','-framerate','24','-i','pipe:0','-ss','19','-i',str(audio),'-map','0:v','-map','1:a','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-t',str(len(group)/24),'-movflags','+faststart',str(clip)]
        font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',21)
        with (OUT/'render.log').open('wb') as log:
            process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
            for r in group:
                source=cv2.imread(r['image']);panels=[]
                for method,title in [('baseline','수정 전 · 독립 프레임 검출'),('video_tracking','수정 후 · VIDEO 추적')]:
                    im=source.copy();hand=r['branches'][method]['hand']
                    if hand:
                        p=np.array(hand['pixel_landmarks'])
                        colors={'thumb':(255,255,255),'index':(255,255,0),'middle':(0,255,0),'ring':(0,165,255),'pinky':(255,0,255)}
                        for name,chain in CHAINS.items():cv2.polylines(im,[p[chain].astype(np.int32)],False,colors[name],2)
                    crop=cv2.resize(im[155:420,800:1080],(640,360));pil=Image.fromarray(cv2.cvtColor(crop,cv2.COLOR_BGR2RGB));draw=ImageDraw.Draw(pil);draw.rectangle((0,0,640,35),fill=(15,20,27));draw.text((10,3),title,font=font,fill='white');panels.append(cv2.cvtColor(np.array(pil),cv2.COLOR_RGB2BGR))
                canvas=np.vstack([source,np.hstack(panels)]);process.stdin.write(canvas.tobytes())
            process.stdin.close()
            if process.wait():raise RuntimeError('Render failed')
    table=[]
    for seg,methods in summary['segments'].items():
        table.append('|'+seg+'|'+'|'.join(f"{methods[m]['middle_wrist_relative_step_p90_px']:.2f}px" for m in METHODS)+'|')
    root=summary['root_probe'];text=f'''# 6·5번 현 주변 손 위치 안정화 — 2026-11-05

**새 모델을 학습하지 않고, 기존 MediaPipe의 VIDEO 추적 경로를 비교해 개선을 확인했다.** 현재화면만독립처리하는방식보다중지의프레임간튐이줄고214초근음가점도일관됐다. 손끝을수동으로이동하거나손가락이름을바꾸지않았다.

## 비교한 세 경로

1. 기존전역손선택+원본우선독립IMAGE검출.
2. 같은프레임에서찾은전체손범위로3종padding×2종확대크기(480/720)를만든후, 실제21점전체스켈레톤중하나를합의/제한적시간일관성으로선택. 손이많이이동하면이전위치가점을끈다.
3. **원본전체화면VIDEO모드**,2손탐색후현재지판근접성과방향으로운지손선택. 좌표의외부평균/보간을하지않고VIDEO모델의실제출력을사용한다.

200초전후1초,214초전후1.5초,257초전후1초를실행해총87프레임을비교했다. 모든경로가87/87곳에서손후보를반환했다. 확대실험과VIDEO추적의선택에오디오·화면코드·사용자정답을넣지않았다. 전체손을하나의검출결과로선택하며손가락별점을섞지않았다. 회전은기존원본우선fallback정책을유지했고추가확대뷰는0도만사용했다.

## 원본과 실제 스켈레톤 대조

![원본·기존 검출·VIDEO 추적 비교](../{(OUT/'before_after_original.png').relative_to(ROOT).as_posix()})

왼쪽은 원본, 가운데는 기존 독립 검출, 오른쪽은 VIDEO 추적이다. 검지는 청록, 중지는 초록, 약지는 주황, 새끼는 자홍이다. 200초와 257초에서는 중지 끝이 손가락 밖으로 튀는 모습이 줄었다. 다만 214초의 손목과 손가락 뿌리를 잇는 연결은 여전히 어색해 보인다. 끝점의 안정성과 전체 관절의 해부학적 정확성은 별개이며, 사람 정답 좌표로 전수 검증하지 않았다.

## 시간 안정성

중지끝의손목상대위치가프레임사이얼마나바뀌는지90백분위수로비교했다. 실제움직임도포함하므로 **이값은좌표오차나오차율이아니다.** 단순히안정적인오검출일가능성도있어원본사진과함께해석한다.

|구간|기존 IMAGE|확대 합의|VIDEO 추적|
|---|---:|---:|---:|
'''+ '\n'.join(table)+f'''

![214초 주변 중지 움직임과 근음 가점](../{(OUT/'temporal_metrics.png').relative_to(ROOT).as_posix()})

214초에서기존중지끝은(888.37,227.06),VIDEO는(883.87,215.10)으로검출됐다. 모두각모델의실제추론좌표이며근음칸에맞추려고좌표를보정한것이아니다. 확대합의는214초에서기존검출과같은관측을선택해이장면의문제를크게해결하지못했다.

## 근음 가점 일관성

이전에원본을확인한213.75~214.083초9프레임에서기존저음현가중치를그대로적용했다. 중지는이전과같이0.25로낮게반영했다. 같은PC의C6/Am7(화면B6/G#m7)쌍은근음가점진단에만썼고스켈레톤선택에는사용하지않았다.

- 기존 IMAGE: G#m7쪽가점이높은{root['baseline']['Am7_higher']}/9프레임,6·5번현A근음지지가0.05이상인{root['baseline']['low65_A_at_least_0_05']}/9프레임.
- 확대 합의: G#m7쪽가점이높은{root['multi_crop']['Am7_higher']}/9프레임,저음현지지{root['multi_crop']['low65_A_at_least_0_05']}/9프레임.
- VIDEO 추적: **G#m7쪽가점이높은{root['video_tracking']['Am7_higher']}/9프레임,저음현지지{root['video_tracking']['low65_A_at_least_0_05']}/9프레임.**

214초단일프레임의VIDEO가점은Am7약0.206,C6약0.005로기존보다분명해졌다. 그러나가점은확률이나실제누름확정이아니다. 정확한가상현경계·해부학적의미·접촉검증은아직미완료이므로근음자동재정렬의기존검증차단규칙은풀지않았다. 214.2초이후의손이동을이전코드의근거로빌려쓰지도않았다.

## 실제 영상

[원본213~214.5초: 기존/VIDEO 손 추적 비교](../{clip.relative_to(ROOT).as_posix()})

위쪽원본은그대로이고아래왼쪽은기존,아래오른쪽은VIDEO추적이다.24fps원속도이며기타추정음을같은원본시각에서맞췄다. 짧은영상은일시정지해원본사진과함께확인하는것이좋다. 리사이즈된확대보기는시각검수용이지좌표평가원본이아니다.

## 적용·검증

`whole_hand_consensus.py`에원본21점보존선택을추가했고`review_low_string_hand_stability.py`에현재원본화면VIDEO추적비교경로를추가했다. 기존모델·음원·기존오디오코드경로는변경하지않았다. 평가범위밖의전체영상자동추적성공을주장하지않는다.

178개테스트통과. 현재프레임의실제관측중선택, 손미검출시이전좌표복사금지, 손이동시시간가점해제와기존손/오디오/화성회귀를확인했다. 모든선택에원본모델출처·영상프레임·PTS·확대변환을보관했다.

```powershell
python review_low_string_hand_stability.py
python report_low_string_hand_stability.py
python -m unittest test_whole_hand_consensus test_low_string_root_prior test_visual_root_tiebreak test_chord_display_cleanup test_chord_display_stabilizer test_audio_change_pool test_temporal_audio_pool test_oracle_chord_audit test_audio_note_calibrator test_basic_pitch_clock test_basic_pitch_adapter test_cut_audio_features test_harmonic_chord_features test_harmonic_chord_benchmark test_idmt_chords_benchmark test_chord_score_variants test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q
```

완료원본결과는덮어쓰지않는다. 모든원본사진·실제관측·경로별결과는result.json/frames, 수치집계는summary.json에있다. 다음확인대상은VIDEO중지/검지의의미가원본손가락과맞는지와6·5번가상현경계다. 안정성개선과해부학적정확성완료를동일시하지않는다.
'''
    (ROOT/'docs/LOW_STRING_HAND_STABILITY_2026-11-05.md').write_text(text,encoding='utf-8');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
