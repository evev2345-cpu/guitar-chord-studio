"""Generate hand-owned Kim review report and source-preserving geometry link."""
import argparse
import json
from pathlib import Path

from evaluate_kim_hand_review import OUT
from hand_frame_contract import adapt_geometry,apply_geometry_gate,file_sha256


def link_geometry(out,evaluation):
    upstream=Path('dataset/fretboard_review/runs/clip_003_012_20261103_v2_semantic')
    # Only use an actual same-frame board deliverable; images or semantic labels aren't geometry.
    matches=[]
    if upstream.exists():
        for path in upstream.rglob('*board.json'):
            data=json.loads(path.read_text())
            if data.get('frame_index')==120:matches.append((path,data))
    if not matches:
        link=dict(status='awaiting_upstream_frame120_semantic_numbering_fixture',
                  inspected_directory=str(upstream),semantic_confirmation_is_not_exact_geometry=True,
                  contact='unknown',precise_fret_decision=None)
    elif len(matches)>1:
        link=dict(status='ambiguous_multiple_upstream_fixtures',paths=[str(p)for p,d in matches],
                  contact='unknown',precise_fret_decision=None)
    else:
        path,data=matches[0]
        obs=next(json.loads(line) for line in Path(evaluation['observation_source_path']).read_text().splitlines()
                 if json.loads(line)['frame_index']==120)
        geometry=adapt_geometry(obs,data)
        link=dict(status='same_frame_upstream_linked',path=str(path),sha256=file_sha256(path),
                  geometry=geometry,raw_gate_after_upstream={name:apply_geometry_gate(q,geometry)for name,q in obs['raw_location_quality'].items()},
                  contact='unknown',precise_fret_decision=None,
                  model_observations_shifted=False,human_positions_used_as_prediction=False)
    (out/'frame120_geometry_link.json').write_text(json.dumps(link,indent=2),encoding='utf-8')
    return link


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,default=OUT);args=parser.parse_args()
    out=args.run;d=json.loads((out/'evaluation.json').read_text())
    link=link_geometry(out,d)
    lines=['# Kim 가시8점 평가 — 2026-11-03 (Asia/Seoul)', '',
        '상태: 주어진 사람 검수8점으로 평가 완료. 1장 개발 평가이며 전역 threshold 보정이나 접촉 정답을 주장하지 않는다. 외부 API/업로드/추가 MediaPipe 추론0회. 최초 raw 관측과 검수 파일은 읽기만 했다.', '',
        '## 검수 범위와 손 대응', '',
        '- 입력: reviewer Kim, model_blind 선언, frame120 실제 PTS5.041666667초, 가시8점+손목unknown1. 원본 영상/픽셀/PNG 해시와 PTS를 다시 검증했다. 입력 fretting_hand_index=null과 손목null은 그대로 보존했다.',
        f'- 평가용 다중 가시점 대응: full hand {d["association"]["derived_hand_index"]}; 같은 랜드마크 번호8점의 중앙 원본 오차 {d["association"]["candidates"][0]["median_error_px"]:.3f}px, 반대 손 {d["association"]["candidates"][1]["median_error_px"]:.3f}px. 30px 이내8/8 대0/8, 중앙값 차 {d["association"]["runner_up_median_margin_px"]:.3f}px.',
        '- 좌표 이동/정합 없이 동일 랜드마크 번호를 직접 대조했다. 최소4가시점, 중앙값≤50px, 30px 이내≥4점, runner-up 차≥50px라는 평가용 대응 규칙을 기록했다. 동률/증거 부족이면 미대응으로 남기며 원본 검수의 hand index를 덮어쓰지 않는다.',
        '- ROI의 별도 hand0은 가시점 중앙오차17.526px, 30px 이내6/8로 공간상 같은 손 후보지만 한 후보뿐이고 손가락 위치는 틀릴 수 있다. 전체 화면 hand0과 ROI hand0이 숫자가 같다는 이유로 대응한 것은 아니다.', '',
        '## 원본 위치 오차', '',
        '| 점 | Full 오차 px | ROI 오차 px | 현재 끝점 gate |', '|---|---:|---:|---|']
    for point in d['point_errors']:
        gate=point['production_raw_gate'];state=gate['decision'] if gate else '적용 대상 아님(관절)'
        lines.append(f'| {point["index"]} {point["name"]} | {point["full_error_px"]:.3f} | {point["roi_error_px"]:.3f} | {state} |')
    lines += ['',f'- Full 평균 {d["full_error"]["mean_px"]:.3f}px / 중앙 {d["full_error"]["median_px"]:.3f}px / 최대 {d["full_error"]["max_px"]:.3f}px. ROI 평균 {d["roi_error"]["mean_px"]:.3f}px / 중앙 {d["roi_error"]["median_px"]:.3f}px / 최대 {d["roi_error"]["max_px"]:.3f}px.',
        '- 검지 관절+끝4점의 개별 오차도 위 표에 포함했다. 오차는 Kim이 표시한 관절/말단 패드 중심과 모델 점 사이 거리다. 표시점의 반복 검수 오차는 아직 측정하지 않았으며 출력 소수점이 그만큼의 라벨 정밀도를 뜻하지 않는다.', '',
        '## gate 과도 보류와 개발 비교', '',
        '- 현재 끝점 gate5개는 통과0/보류5. 중지2.985px·약지4.103px는 현재6px 위치 기준 안이지만 각각 ROI 차20.10px·25.98px로 보류됐다. 위치 기준상 명확한 과도 보류2개: 허용오차 안 끝점2/2를 모두 잃었다. 접촉/프렛의 과도 보류 판정은 아니다.',
        '- 엄지9.085px·검지끝7.799px·소지24.033px는6px 위치 기준 밖이었다. 현 gate가 이3점을 보류하는 것과 정확한 중심을 찾아내는 것은 별개다. 특히 ROI가 full보다 이 사진의5끝점에서 더 나쁘므로 ROI를 항상 확인 정답으로 쓰면 안 된다.',
        '- frame120에 이전 선택 관측이 없어 속도 값은null이었다. 180px/s gate의 옳고 그름은 단일 검수 사진으로 평가할 수 없다. 원래3~12초 gate 측정은 보존하며 모델/threshold를 변경하지 않았다.',
        '- 반경3/6/9/12px 내 실제 검수점 수는1/2/5/7 (각8점 중)이다. 6px의95% 포함 가정이 이 한 사진에서25%였다는 개발 결과이며, 이를 전체 검출기 calibration 정확도나 전역95% 반경으로 일반화하지 않는다.', '',
        '| 개발 비교(배포 안 함) | 통과/5 | 보류/5 | 6px내 과도보류 | 통과했지만 오차>6px |', '|---|---:|---:|---:|---:|']
    for a in d['development_gate_ablations']:
        lines.append(f'| {a["mode"]} | {a["passed"]} | {a["withheld"]} | {a["excessive_withholding_within_6px"]} | {a["passed_but_error_over_6px"]} |')
    lines += ['', '- ROI gate 제거는 모든5점을 통과시켜 과도보류2개를 없애지만 오차>6px의3점도 통과시킨다. 단순 gate 완화나 ROI 제거를 개선 완료로 채택하지 않았다. 현재 운영 gate는 그대로다.', '',
        '## 지판 의미 검수와 새 fixture', '',
        '- 너트/카포/첫금속프렛=물리1 의미 확인은 별도 사람 참조로 보존했다. 생성형 표시 이미지의 의미 확인이며 원본 픽셀 끝점·나머지 프렛·현 정체성·접촉·독립 블라인드 좌표 검수로 승격하지 않았다.',
        f'- 새 지판 fixture 연결 상태: {link["status"]}. frame120_geometry_link.json에 입력 경로/해시·기하 상태를 기록한다. 원래 full/ROI 중심을 사람 점에 맞춰 옮기지 않았다. 정확한 프렛/접촉은 계속null/unknown.', '',
        '## 인계와 남은 작업', '',
        '- evaluation.json: 원본8점 오차, 평가용 손 대응/모호성, gate/개발 ablation, 입력 해시. frame120_comparison_original.png·full_error_crop.png·roi_error_crop.png: 사람 초록십자, full 주황, ROI 자홍.',
        '- 기존 검수 G 사진은 재요청하지 않는다. 이번8점의 평가에 추가 사람 입력은 필요하지 않았다. 바레/217초 오류2장은 여전히 미완료이며, 그 조건의 위치오차·ROI gate 성능까지 평가하려면 기존 검수 도구에서 보이는 검지끝8과 관절5/6/7부터만 추가하면 된다. 가린 점/손목은unknown 유지 가능하다. 이번 자동 작업을 그 입력 때문에 중단하지 않았다.',
        '- 단1장8점, 가림/접촉 정답 없음. 전역 반경·속도/ROI threshold 보정 완료가 아니며 독립적인 다른 조건에서 재검증해야 한다. 기존 C#m7 회귀 fixture는 변경하지 않았다.', '',
        '## 실행', '', '```powershell','python evaluate_kim_hand_review.py','python report_kim_hand_review.py','python -m unittest test_kim_hand_review test_hand_frame_contract test_hand_quality -v','```']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(link['status'])


if __name__=='__main__':main()
