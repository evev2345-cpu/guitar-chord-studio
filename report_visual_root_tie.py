"""Real214s visual audit: no manual truth or screen text fed into tie selection."""
import json
from pathlib import Path
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from visual_root_tiebreak import resolve
from improve_hand_skeleton import CHAINS,COLORS

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dataset/integration_review/runs/visual_root_tie_20261105_v1'

def main():
    records=json.loads((OUT/'observations.json').read_text());results=[];fig,axes=plt.subplots(3,2,figsize=(12,10))
    for row,r in enumerate(records):
        mass=np.array(r['visual_pc_mass']);audio=r['audio']['0.2']['top3'];decision=resolve(audio,{c['root_pc']:float(mass[c['root_pc']]) for c in audio},visual_status='unknown')
        record=dict(pts=r['pts'],audio=audio,decision=decision,alignment=r['alignment']['status'],hand_selection=r['hand']['selection']['status'],
            root_location_mass_proxy={c['symbol']:float(mass[c['root_pc']]) for c in audio},
            generic_pc_compatibility={c['symbol']:float(mass[c['pcs']].sum()) for c in audio},
            visual_status='unverified_anatomy_grid_and_contact; tip mass is not validated root evidence')
        results.append(record);im=cv2.cvtColor(cv2.imread(r['image']),cv2.COLOR_BGR2RGB);axes[row,0].imshow(im);axes[row,0].set_title(f"Original PTS{r['pts']:.6f}; no manual points");axes[row,0].axis('off')
        axes[row,1].imshow(im);selected=r['hand']['selection']['selected']
        if selected:
            points=np.array(selected['hands'][0]['pixel_landmarks'])
            for name,chain in CHAINS.items():
                p=points[chain];axes[row,1].plot(p[:,0],p[:,1],color=COLORS[name],lw=2)
        axes[row,1].set_xlim(840,1040);axes[row,1].set_ylim(390,175);axes[row,1].set_title('Detected skeleton / anatomy and contact UNKNOWN');axes[row,1].axis('off')
    fig.tight_layout();fig.savefig(OUT/'original_skeleton.png',dpi=145);plt.close(fig)
    target=next(r for r in results if abs(r['pts']-214)<1e-6);fig,ax=plt.subplots(figsize=(9,4));names=['C6 (shape B6)','Am7 (shape G#m7)'];pc=[target['generic_pc_compatibility'][c] for c in ['C6','Am7']];root=[target['root_location_mass_proxy'][c] for c in ['C6','Am7']];x=np.arange(2);ax.bar(x-.17,pc,.34,label='Existing PC compatibility: identical');ax.bar(x+.17,root,.34,label='Unverified fingertip root-PC mass proxy');ax.set_xticks(x,names);ax.set_ylim(0,1);ax.legend(fontsize=8);ax.set_title('214s / location mass is not root confidence');fig.tight_layout();fig.savefig(OUT/'tie_scores.png',dpi=140);plt.close(fig)
    (OUT/'result.json').write_text(json.dumps(dict(frames=results,user_reference=dict(source_time_s=214,shape='G#m7',concert='Am7',usage='Review only, never selection input'),
        production_reranking_applied=False,reason='Same-PC compatibility cannot choose roots; current visual root evidence unverified and inconsistent across neighboring frames'),indent=2),encoding='utf-8')
    text='''# B6/G#m7 동점에 비전 근거 대조 — 2026-11-05

10초비교영상의6초는원본214초다. 실제오디오후보는화면환산B6/G#m7,실음C6/Am7이며두점수가정확히동점인것을확인했다. 사용자가확인한화면G#m7은검수참조로만저장했다.

중요한수정사항: **기존 비전의 구성음 일치 가점만으로는 이 둘을 구분할 수 없다.** 두후보의음집합은C·E·G·A로같아서어떤위치PC분포를넣어도구성음일치점수가같다. 근음·베이스위치·운지유형을따로검증한근거가필요하다. 같은운지를C6/A로해석하는경우도있으므로최저음이A라는것만으로Am7이유일한정답이라고확정할수없다.

## 실제 영상·손 모델 확인

원본213.791667·214.000000·214.208333초의프레임에서기존지판정합·손선택·스켈레톤·가상현분포를실행했다. 원본영상영역만입력했고화면코드나TAB를OCR하거나가점입력에넣지않았다. 알려진중지끝오류를고려해기존정책대로검지/약지/새끼위치만진단에사용했다. 검출점을수동으로옮기지않았다.

![실제 원본과 검출 스켈레톤 — 해부학적 의미·현 접촉 미확정](original_skeleton_placeholder)

지판ROI정합은valid였지만정밀프렛번호·가상현·손가락의미·접촉은여전히미확정이다. 손선택도insufficient_views_candidate였다. 근음PC의손끝위치가점은213.792초에는C쪽,214초에는A쪽이높아일관되지않았다. 이는확률이나실제베이스검출이아니라‘손끝이그PC의가상칸에가까운가’라는미검증지표다.

![214초 기존 구성음 가점과 미검증 근음 위치지표](tie_scores_placeholder)

**214초한프레임만골라G#m7로바꾸면사용자정답에맞춘수정이될위험이있다.** 따라서이번실험에서는자동순위변경을하지않았다. 비전이약하면둘다남기자는사용자합의를따른다. 앞서‘비전으로동점을해결할수있다’고말한것은가능한방향이며현재손모델이이미그근거를제공한다는뜻은아니다.

## 구현한 경계

`visual_root_tiebreak.py`는동일PC집합·동일오디오점수의후보에한해서만순위를바꿀수있게했다. 별도로검증된근음/운지근거와충분한차이가없으면원래후보와동점을유지한다. 일반코드후보나구성음은바꾸지않는다. 현재실제프레임에는그검증상태가없어서withhold했다.

현재음원·화성엔진·가중치·다른영상구간은변경하지않았다. 실제로G#m7을자동선택했다고보고하지않는다. 다음에는6번/5번현의근음자리와검지바레유형을근거로하는별도특징을검증하거나저음오디오와앞뒤진행을함께검토해야한다.

새4개테스트로동점한정,실제다른구성음후보보호,검증되지않은비전의강제선택금지,약한차이보류를확인했다. 수치와원본손좌표는observations.json/result.json에있다.
'''
    for placeholder,file in [('original_skeleton_placeholder','original_skeleton.png'),('tie_scores_placeholder','tie_scores.png')]:text=text.replace(placeholder,'../'+str((OUT/file).relative_to(ROOT)).replace('\\','/'))
    text+='\n\n## 실제 영상 표시 수정\n\n[수정한10초영상:6초지점확인](../dataset/integration_review/runs/visual_root_tie_20261105_v1/root_ambiguity_208_218.mp4)\n\n![214초동일구성음후보를함께표시](../dataset/integration_review/runs/visual_root_tie_20261105_v1/root_ambiguity_preview.png)\n\n비전으로정답을확정한척하지않고같은PC·같은최고점의후보를함께보여주도록별도영상에적용했다. 음추출·음집합·오디오점수·다른후보순위는변경하지않았다. 전체170개회귀/신규테스트와MP4전체디코딩검사를통과했다.\n'
    (ROOT/'docs/VISUAL_ROOT_TIE_REVIEW_2026-11-05.md').write_text(text,encoding='utf-8');print('Visual root tie remains ambiguous; no forced selection')

if __name__=='__main__':main()
