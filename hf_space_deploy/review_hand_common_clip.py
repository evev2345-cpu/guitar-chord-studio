"""Hand-owned report, minimum model-blind review queue, and gate diagnostics."""
import argparse
import base64
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

import numpy as np

from hand_frame_contract import file_sha256,frame_identity
from run_hand_common_clip import DEFAULT_OUT,write_json


def prepare_review(out,source_id):
    if (out/'review_queue.json').exists() and (out/'minimum_independent_review.html').exists():
        return
    video=next(Path('sample video').glob('*.mp4'))
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-read_intervals','0%219',
        '-show_frames','-show_entries','frame=pts,best_effort_timestamp','-of','json',str(video)],
        check=True,capture_output=True,encoding='utf-8').stdout)['frames']
    cases=[]
    for label,path,index in [('open',Path('dataset/chord_video_review/case_0005.00_tracking.json'),120),
                             ('barre',Path('dataset/chord_video_review/case_0194.86_tracking.json'),4677),
                             ('error',Path('dataset/chord_video_review/case_0217.20_tracking.json'),5213)]:
        track=json.loads(path.read_text());image=Path(track['image'])
        import cv2
        raw=cv2.imread(str(image))
        identity=frame_identity(source_id,index,probe[index],'1/12288',raw,image)
        identity['case_id']=track.get('case_id',path.stem)
        cases.append(dict(role=label,**identity,
            image='data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode(),
            image_sha256=file_sha256(image),wrists=[dict(hand_index=h['hand_index'],pixel=h['landmarks'][0]['pixel']) for h in track['hands']]))
    # Reuse the original model-blind HTML; restrict the requested points to 9 per photo.
    html=Path('dataset/chord_sequence_review/independent_review.html').read_text(encoding='utf-8')
    html=re.sub(r'const cases=.*?; const names=',lambda _: 'const cases='+json.dumps(cases)+'; const names=',html,count=1)
    html=html.replace('for(let i=0;i<21;i++){','for(const i of [0,4,5,6,7,8,12,16,20]){')
    html=html.replace("pi=Math.min(20,pi+1)","pi=([0,4,5,6,7,8,12,16,20].find(i=>i>pi)??20)")
    html=html.replace("ci=(ci+5)%6","ci=(ci+cases.length-1)%cases.length").replace("ci=(ci+1)%6","ci=(ci+1)%cases.length")
    html=html.replace("+' ('+(ci+1)+'/6)'","+' ('+(ci+1)+'/'+cases.length+')'")
    html=html.replace("image_sha256:c.image_sha256,fretting_hand_index", "source_id:c.source_id,frame_index:c.frame_index,frame_pts_s:c.frame_pts_s,frame_pixel_sha256:c.frame_pixel_sha256,image_file_sha256:c.image_file_sha256,image_sha256:c.image_sha256,fretting_hand_index")
    html=html.replace('원본 기반 독립 손 검수 — 예측 골격은 표시하지 않습니다', '최소 독립 검수: 오픈·바레·오류 3장 × 최대 9점')
    html=html.replace('운지 손만 라벨링합니다.', '운지 손의 손목(0), 엄지끝(4), 검지 관절(5·6·7)과 끝(8), 중지끝(12), 약지끝(16), 소지끝(20)만 검수합니다. 가린 점은 가림으로 두세요. 바레·오류 장면은 3~12초 밖의 회귀 참조입니다.')
    (out/'minimum_independent_review.html').write_text(html,encoding='utf-8')
    for case in cases:case.pop('image');case.pop('wrists')
    write_json(out/'review_queue.json',dict(cases=cases,required_landmark_indices=[0,4,5,6,7,8,12,16,20],
        maximum_points=27,independent_human_points=0,agent_visual_reference_only=True,
        status='awaiting_human_input',scope='one common-clip open frame; outside-clip barre and frozen error references'))
    write_json(out/'legacy_time_mapping.json',cases)


def evaluate(out):
    records=[json.loads(line) for line in (out/'observations.jsonl').read_text().splitlines()]
    gates=[];normal=[]
    for record in records:
        for name,q in record['raw_location_quality'].items():
            if name=='thumb':continue
            item=dict(q,frame_index=record['frame_index'],frame_pts_s=record['frame_pts_s'],finger=name)
            gates.append(item)
            if 4.5<=record['frame_pts_s']<=5.5:normal.append(item)
    counts=Counter(reason for q in gates for reason in q['reasons'])
    sensitivity=[]
    for radius in [3,6,9,12]:
        for speed in [90,180,360]:
            n=sum((q['secondary_pixel'] is None or q['cross_view_distance_px']>radius or
                   (q['speed_px_per_second'] is not None and q['speed_px_per_second']>speed)) for q in gates)
            sensitivity.append(dict(radius_px=radius,speed_px_s=speed,abstain_count=n,
                                    eligible_fingertip_observations=len(gates),abstain_rate=n/len(gates) if gates else None))
    default=sum(q['decision']=='abstain' for q in gates)
    stablehold=sum(q['decision']=='abstain' for q in normal)
    result=dict(frame_count=len(records),eligible_fingertips=len(gates),default_abstain_count=default,
        default_abstain_rate=default/len(gates),reason_counts=dict(counts),sensitivity=sensitivity,
        agent_visual_clear_window=dict(start_s=4.5,end_s=5.5,eligible=len(normal),abstain_count=stablehold,
            abstain_rate=stablehold/len(normal) if normal else None,
            label_status='agent_visual_reference_not_independent_gt',confirmed_false_abstain_rate=None),
        geometry_gated_frames=sum(r['geometry']['status']!='valid' for r in records),
        calibration_status='heuristics_not_validated',independent_reviewed_points=0)
    write_json(out/'gate_evaluation.json',result)
    return records,result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,default=DEFAULT_OUT);args=parser.parse_args()
    out=args.run
    records,metrics=evaluate(out);source=records[0]['source_id']
    prepare_review(out,source)
    source_audio=json.loads(Path('dataset/audio_analysis/runs/clip_003_012_v2/manifest.json').read_text())
    if source_audio['source_id']!=source:raise ValueError('Audio and hand source mismatch')
    statuses=Counter(r['status'] for r in records)
    join_path=out/'upstream_join/manifest.json'
    joined=json.loads(join_path.read_text()) if join_path.exists() else dict(matched_frames=0,frames=[])
    lines=['# 손 담당 3~12초 공통 구간 보고 — 2026-11-03', '',
        '지시서 P1 손 담당 1~6 실행. 기존 결과/회귀 fixture 보존, 새 run 저장, 외부 API 호출 0회. 공용 README와 다른 담당 소유 파일은 수정하지 않았다.', '',
        '## 식별·실제 PTS', '',
        f'- source_id={source}. 오디오 clip_003_012_v2의 MP4 SHA-256과 일치.',
        f'- 실제 원본 frame PTS 기준 [3,12)초: {len(records)}프레임, index {records[0]["frame_index"]}~{records[-1]["frame_index"]}, PTS {records[0]["frame_pts_s"]:.6f}~{records[-1]["frame_pts_s"]:.6f}초.',
        '- ffprobe 정수 PTS × stream time_base=1/12288을 사용한다. OpenCV 디코딩 순서를 ffprobe 표시 순서에 매핑했다. frame_index/fps를 시간 정답으로 사용하지 않는다. 시작 PTS 차를 실제 A/V 지연으로 해석하지 않는다.',
        '- frame_contract.json에 영상 해시·frame_index·정수 PTS·PTS초·decoded BGR 해시·저장 PNG 파일 해시를 분리했다. 저장하지 않은 프레임의 image_file_sha256은 null이며 픽셀 해시는 보존된다.',
        '- 과거 G index120의 실제 PTS는 5.041667초다. 기존 case_0005.00의 5초 표기를 덮어쓰지 않고 legacy_time_mapping.json에 정정 정보를 기록했다. 194/217초 회귀도 같은 방식으로 매핑했다.', '',
        '## 지판 계약과 원시 증거', '',
        f'- 최신 지판 담당 결과 {joined["matched_frames"]}개 동일 프레임을 연결했다. 상태 {dict(Counter(r["geometry_status"] for r in joined["frames"]))}. 최신 결과는 upstream_join/manifest.json과 joined_observations.jsonl이다. ROI alignment valid와 contact_fret_decision_allowed=false는 별도이며 후자를 보류에 반영했다.',
        '- hand_frame_contract.adapt_geometry는 동일 source_id/frame_index/PTS/pixel hash의 상류 geometry_validity(valid/suspect/unknown/invalid)를 사용한다. 누락은 unknown, 프레임 불일치는 거부한다. geometry_request.json은 상류 제출용 최소 계약이다.',
        f'- 현재 결합된 유효 상류 기하가 없어 {metrics["geometry_gated_frames"]}/{len(records)}프레임의 정확한 프렛·접촉은 보류다. 기존 5초 수동 fixture는 손 근접 선택의 참조로만 사용하며 source_kind=manual_approximation/validity=unknown으로 분리했다.',
        '- 관측21점, ROI 원시 검출, 선택 상태, gate 전후 상태를 observations.jsonl에 저장했다. 이전 좌표는 속도 진단에만 사용하며 선택 실패 후 초기화한다. 영구ID/평활화/새 관측으로 좌표 재사용 없음. 비접촉 손가락을 코드 음으로 변환하지 않는다.',
        f'- 선택 상태: {dict(statuses)}. selected는 정확도나 접촉 성공률이 아니다.', '',
        '## 보류율·과도한 보류', '',
        f'- 엄지 제외 선택된 손 끝점 {metrics["eligible_fingertips"]}관측 중 기본 gate 보류 {metrics["default_abstain_count"]} ({metrics["default_abstain_rate"]:.1%}). 기하 보류와 구분한 수치다.',
        f'- 중복 가능한 원인: {metrics["reason_counts"]}. ROI 재검출 실패는 실제 가림 정답이 아니라 검출 경로 불일치다.',
        f'- 시각적으로 명확한 G 장면 4.5~5.5초(agent 참조)에서 보류 {metrics["agent_visual_clear_window"]["abstain_count"]}/{metrics["agent_visual_clear_window"]["eligible"]} ({metrics["agent_visual_clear_window"]["abstain_rate"]:.1%}). 과도한 보류 후보이며 실제 오보류율은 독립 정답 부재로 null이다.',
        '- 특히 기존 G index120 검지는 전체/ROI 차 약13.79px여서 6px gate가 보류한다. 전체 화면 위치가 타당해 보이더라도 어느 관측이 옳은지는 사람 점 검수가 필요하다. 모든 보류가 개선이라는 주장을 하지 않는다.',
        '- gate_evaluation.json에 radius 3/6/9/12px × speed 90/180/360px/s의 전체 보류율을 제공한다. 기존 6px/180px/s 기준을 측정 없이 완화하지 않았다.', '',
        '## 최소 독립 검수·217초 회귀', '',
        '- 예측을 숨긴 기존 HTML을 재사용해 minimum_independent_review.html을 만들었다. 126점 대신 오픈·바레·오류 3장 각 최대9점(손목0, 엄지끝4, 검지5·6·7·8, 중지12, 약지16, 소지20)만 요청한다. hidden/unknown은 좌표를 비운다.',
        '- 오픈은 공통 구간의 기존 G, 바레와 오류는 각각 과거 F#/C#m7 회귀 장면이다. 3~12초에 확실한 전체 바레가 있다는 정답을 만들어내지 않았다. 화면 코드 참조는 검수 레이어이며 접촉 정답이 아니다.',
        '- 사람이 작성한 독립 점은 현재0개다. 기존 에이전트4점은 그대로 에이전트 참조이며 독립 정확도/보정 완료에 사용하지 않는다. 사람은 HTML에서 위 가시 점을 찍거나 가림을 표시하고 식별자를 입력해 JSON을 내려받으면 된다.',
        '- dataset/regression/csharp_m7_wrong_center.json과 기존 회귀 검사를 유지했다. 새 run은 과거 회귀 fixture의 파일 해시도 manifest에 보존한다.', '',
        '## 상류/하류 제출', '',
        '- 상류: frame_contract.json, geometry_request.json. 동일 프레임 기하 유효성/현 결과를 이 계약으로 연결 가능.',
        '- 하류: observations.jsonl, summary.json, gate_evaluation.json, review_queue.json, legacy_time_mapping.json, 대표 frame_*_overlay.png. 모든 미확인 접촉/정확한 프렛은 null/unknown.', '',
        '## 실행', '', '```powershell', 'python run_hand_common_clip.py', 'python review_hand_common_clip.py', 'python -m unittest test_hand_frame_contract test_hand_quality -v', '```']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write_json(out/'run_manifest.json',dict(source_id=source,source_audio_match=True,
        immutable_regression_path='dataset/regression/csharp_m7_wrong_center.json',
        immutable_regression_sha256=file_sha256('dataset/regression/csharp_m7_wrong_center.json'),
        api_calls=0,independent_human_points=0))


if __name__=='__main__':main()
