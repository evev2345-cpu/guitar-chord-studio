"""Build a review report from offline tutorial candidate artifacts."""
import csv
import json
from pathlib import Path
import cv2
import numpy as np

OUT = Path('dataset/chord_photo_validation')


def main():
    cases = json.loads(Path('dataset/chord_video_review/cases.json').read_text(encoding='utf-8'))
    summary = json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    lines = ['# 코드 분석기 첫 정지 이미지 검수', '',
             '사용자가 제공한 sample video의 266.875초, 24fps, 1280×720 튜토리얼에서 6장을 추출했다. 유료/검출 API 호출 0회. 영상 추적은 실행하지 않았다.',
             '기존 사진 캐시는 보존했다. 이 영상에 대응하는 지판 캐시가 없으므로 서로 다른 사진의 캐시를 적용하지 않았다. 대신 프레임별 수동 시각 근사 코너·와이어를 별도 fixture로 저장하고 손 분석에서 재사용했다. 자동 지판 검출의 품질을 평가한 결과가 아니다.',
             '영상의 코드·TAB와 실제 손 모양을 같이 보았다. 화면에는 현재/후속 코드가 함께 나와 있어 코드명은 검수 참조값이며 프레임 동기화된 접촉 정답이 아니다. Capo.1: 물리 프렛=너트 기준, TAB 프렛=카포 기준이다. 후보 JSON에 둘을 분리했다.', '',
             '## 사례', '', '| 시간 | 화면 참조 | 손 검출 | 검수 | 원본+평탄 |', '|---|---|---|---|---|']
    notes = {
        'G': '운지 손 선택 타당. 검지/중지/약지의 주 후보는 물리 3/4/4(카포 상대 2/3/3). 사용하지 않는 소지는 지판 밖 유지.',
        'A': '운지 손 선택 타당. 일부 손끝이 다른 칸에 있으나 손끝 위치와 접촉은 별개. 화면 A 표기만으로 모든 손가락 접촉을 라벨링하지 않음.',
        'F#': '운지 손 선택 타당. 검지 끝은 지판 밖이지만 검지 마디는 지판 위를 가로지름. 바레 접촉을 끝점만으로 판정하면 누락.',
        'C#m7': '운지 손 선택 타당. 검지 끝의 시각 라벨과 모델 위치가 약 23.4px 불일치. r=6에서 물리 6 후보 약 100% → 과신 오류 사례.',
        'E': '운지 손 선택 타당. 검지/중지/약지 주 후보 물리 2/3/3(카포 상대 1/2/2). 소지는 떠 있는 후보이며 접촉 확정 금지.',
        None: '전환/잔상 사례. 손 1개 검출, 지판 쪽 손 선택 타당. 코드명과 프렛 접촉 정답은 보류.'}
    csv_rows=[]
    for case in cases:
        name=case['case_id']+'_tracking'
        result=json.loads((OUT/f'{name}_candidates.json').read_text(encoding='utf-8'))
        original=cv2.imread(str(OUT/f'{name}_r6_original.png'))
        flat=cv2.imread(str(OUT/f'{name}_r6_flat.png'))
        tile=np.full((640,800,3),240,np.uint8)
        thumb=cv2.resize(original,(800,450)); tile[30:480]=thumb; tile[485:635]=flat
        cv2.putText(tile,f'{case["timestamp_seconds"]:.2f}s / {case["chord_shape"]} / {case["chord_type"]}',(5,20),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,0,0),1)
        cv2.imwrite(str(OUT/f'{name}_review.png'),tile)
        lines.append(f'| {case["timestamp_seconds"]:.2f}s | {case["chord_shape"] or "전환"} ({case["chord_type"]}) | {case["hands"]} | {notes[case["chord_shape"]]} | [보기]({name}_review.png) |')
        for finger in result['fingers']:
            for entry in finger['sensitivity']:
                top=entry['candidates'][0] if entry['candidates'] else {}
                csv_rows.append(dict(case=name,finger=finger['finger'],radius_px=entry['radius_px'],
                                     top_physical_fret=top.get('fret_num'),top_probability=top.get('probability'),
                                     unassigned_probability=entry['unassigned_probability']))
    with (OUT/'sensitivity.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(csv_rows[0]));writer.writeheader();writer.writerows(csv_rows)
    cal=summary['calibration']
    lines += ['', '## 위치 분포와 반경 검증', '',
              '- 반경 3/6/9/12px 및 라벨 기반 시험 반경을 비교했다. 각 손가락은 모든 프렛의 질량과 outside_board / unresolved_geometry / unassigned 확률을 보존한다. 지판 내부로 재정규화하거나 최고 후보 하나를 확정하지 않는다.',
              '- 위치 Gaussian을 65,536개 고정 시드 표본으로 적분해 좁은 분포의 1px 격자 합 오차를 줄였다. 표본 표준오차를 저장하며 매우 작은 꼬리는 0이 될 수 있다. 보드 기하 오차는 아직 포함하지 않는다.',
              f'- 임시 시각 라벨 4점/2프레임의 원본 오차: {cal["errors_px"]}. 95백분위 시험 반경 {cal["calibrated_radius_px"]:.2f}px도 계산/오버레이했다. 독립 사람 정답이나 잠금 검증이 아니며, 기본 6px를 전역 교체하지 않았다. 현재 숫자를 검출 신뢰도 보정 완료라고 해석하면 안 된다.',
              '- G 중지 물리4 질량: r3 약94.5%, r6 79.0%, r9 70.4%, r12 65.6%; 경계 밖 질량이 증가한다. F# 검지는 r6에서 미배정 약98.7%로 유지되며, 마디 구간은 따로 출력된다.',
              '- C#m7 검지는 r6에서 물리6 약100%, r20.07에서도 약96.1%로 남는다. 분포를 넓히는 것만으로 중심 위치 오류가 해결되지 않는다. 다른 손가락과 가림·관절 구조를 이용한 검수가 필요하다.', '',
              '## 바레·엄지·외부 현 인터페이스', '',
              '- 모든 손의 원본 21개 랜드마크 보존. 선택 손의 엄지 끝도 다른 손가락과 같은 민감도/복수 후보를 출력하되 contact=unknown.',
              '- 검지 5→6(MCP→PIP), 6→7(PIP→DIP), 7→8(DIP→TIP) 구간의 원본/평탄 끝점과 9개 위치 표본별 후보를 출력한다. 이 구간의 반경은 명시적으로 6px이며 구간 표본을 접촉이나 독립 사건으로 곱하지 않는다.',
              '- 새 현 검출기 없음. --strings-json으로 기존 detect_strings_offline 결과를 받는다. 동일 input_geometry와 canvas를 검사하고 observed/estimated 출처를 보존한다. 영상 신규 프레임에는 현 검출 결과가 아직 없으므로 not_provided. 균등 6분할은 사용하지 않는다.', '',
              '## 검수 범위와 남은 작업', '',
              '- 6프레임 모두 운지 손 선택이 시각적으로 타당했다. 이는 에이전트 시각 점검이며 독립 라벨 기반 선택 정확도 수치가 아니다.',
              '- 오픈 코드의 비접촉 손가락, 지판 밖 바레 끝점, C#m7 랜드마크 이동, 프렛 경계 분산을 오류/미확정 사례로 보존했다. 소지나 엄지의 후보가 존재한다고 코드를 구성하는 음으로 넣지 않는다.',
              '- 단일 영상에서 뽑은 유사 프레임들이므로 학습·검증·테스트 독립성이 없다. 독립 촬영, 사람 21점 라벨과 가림 표시, 실제 접촉·현/프렛 정답이 추가되어야 첫 마일스톤 품질을 확정할 수 있다.',
              '- review_template.json은 수동 검수용 빈 형식이다. landmarks 항목은 {index:8,pixel:[x,y],visibility:"visible"}, fret_labels는 접촉이 아니라 검수한 위치 프렛 후보를 기록한다. review_status와 reviewer를 명시하고 가린 점은 좌표를 추측하지 않는다.', '',
              '## 재실행', '', '```powershell',
              'python prepare_chord_video_cases.py',
              '$tracks = (Get-ChildItem dataset/chord_video_review -Filter "*_tracking.json").FullName',
              'python chord_photo_validation.py --tracking-json $tracks --labels dataset/chord_video_review/visual_point_review.json --output dataset/chord_photo_validation',
              'python summarize_chord_photo_validation.py', '```', '',
              '기존 지판 캐시/손 결과를 덮어쓰지 않는다. API 키를 읽거나 원격 호출하는 코드가 없다.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__ == '__main__':main()
