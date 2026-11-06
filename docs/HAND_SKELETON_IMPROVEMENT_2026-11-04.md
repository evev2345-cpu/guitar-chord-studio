# 손가락 스켈레톤 인식 개선 — 2026-11-04

## 결과

사용자가 대응 오류를 지적한 frame210(PTS8.791667초)에서 **중지·약지·소지가 서로 다른 손가락을 따라가는 새 검출 후보**를 얻었다. 기존 좌표의 이름을 바꾸거나 검수점에 맞춰 이동하지 않았다. 같은 모델을 사용하되 입력 손 영역을 좁히고, 회전별로 검출한 **단일 손 전체21점** 중 하나를 선택했다.

![원본·기존 ROI·개선된 전체 손 스켈레톤](../dataset/hand_analysis/runs/skeleton_improvement_20261104_focused_v1/frame210_before_after.png)

왼쪽은 원본, 가운데는 오류가 검수된 기존 ROI, 오른쪽은 새 검출 결과다. **중지=초록, 약지=주황, 소지=분홍**, 검지=하늘색, 엄지=흰색이다. 점·가상현·격자·확률분포는 그리지 않았다. 실제 원본 픽셀에 검출 연결선만 겹친 과학적 시각화이며 생성형 편집 이미지가 아니다.

새 결과는 중지를 위쪽 긴 손가락, 약지를 그 아래 프렛 근처 손가락, 소지를 아래로 굽은 손가락으로 나눠 표현한다. 모델의 가려진 관절과 손바닥 내부는 여전히 추정이다. 실제 접촉·정확한21점 정답·새 후보의 독립 사용자 검수는 완료되지 않았다.

## 변경한 방법

1. baseline의넓은 ROI `[740,155,1135,420]`와 달리 `[850,150,1110,420]`의 손 중심 영역을 사용한다. 배경·지판이 차지하는 비율을 줄이고 원본 손을 더 크게 입력한다. 이 좌표는 현재 고정카메라 튜토리얼 전용 preset이다.
2. 동일 손영역을0/90/180/270도 방향으로 각각 추론하고, 변환을 역으로 적용해 원본 좌표로 복원한다. 영상의 손가락 이름이나 연결 순서를 수동 변경하지 않는다.
3. 전체21점의 쌍별 관절거리 중앙값으로 가장 일관적인 실제관측 하나를 고른다. 손가락별로 좋은 점을 뽑아 새 손을 합성하지 않는다. 회전 후보끼리의 일치도는 정확도·접촉 확률이 아니다.
4. 유효한 단일손 후보가3개 미만이면 관측부족 상태를 남긴다. 손이 없거나 다중손이면 억지 선택하지 않는다. 다른 hand-pipeline의 원시 관측·사람 검수·기존 무효 sidecar는 수정하지 않았다.

미리 손가락 구분을 알아야만 사용할 수 있는 후처리로 이름을 바꾸지 않았으며, 단순히 중지 체인을 둘로 나누거나 누락 소지 좌표를 만들어 넣지도 않았다.

## 개발 비교와 검수

먼저frame120/210에서4가지crop×4회전×반전유무=32가지씩, 총64번의 IMAGE 추론을 비교했다. 그 과정에서 좁은손 crop의 방향변환 없는/회전된 여러 결과에서 중지·약지·소지 분리가 개선되는 것을 확인했다. 탐색자료는 `skeleton_improvement_20261104_image_v1`에 보존했다.

그 뒤 거울반전은 기본경로에서 제외하고, 고정crop+4회전의 전체손 선택 경로로11프레임(120/124/190/209~216)을44회 추론했다. 모든프레임에서 회전별 단일손4개를 얻었다. 검출빈도 증가는 해부학적 정확도 향상과 다르다.

### frame120의 기존 Kim 검수8점

![Kim 검수 사진의 원본·기존·새 검출 비교](../dataset/hand_analysis/runs/skeleton_improvement_20261104_focused_v1/frame120_before_after.png)

|항목|기존 baseline ROI 오차px|새 전체손 후보 오차px|
|---|---:|---:|
|가시8점 평균|22.84|9.40|
|중지 끝12|17.83|7.66|
|약지 끝16|28.30|4.83|
|소지 끝20|46.05|8.96|
|엄지 끝4|51.03|22.41|
|검지 끝8|9.49|10.22|

검지 오차는 조금 늘었고 엄지도 여전히 크다. 참고로 기존 **전체화면** 검출의8점 평균은9.33px여서 새방식9.40px가 기존 모든방식보다 우수한 것은 아니다. 이번 핵심은 실패한baseline ROI의 손가락 체인을 개선한 것이다.

frame120은 설정 탐색에 사용한 개발사진 한 장이며 독립 테스트가 아니다. frame210에는 가시8점 같은 정밀라벨이 없어 수치오차나 ‘손가락 식별 정확도’를 계산하지 않았다. 화면의G코드/운지표는 모델 입력·후보선택 점수로 사용하지 않았다. 손가락 접촉이나 코드 인식 성공률도 평가하지 않았다.

### 다른 자세와 인접 프레임

![frame190의 다른 자세 비교](../dataset/hand_analysis/runs/skeleton_improvement_20261104_focused_v1/frame190_before_after.png)

![이전 ROI 미검출 frame212의 새 후보](../dataset/hand_analysis/runs/skeleton_improvement_20261104_focused_v1/frame212_before_after.png)

![frame215의 원본·기존·새 후보](../dataset/hand_analysis/runs/skeleton_improvement_20261104_focused_v1/frame215_before_after.png)

인접frame209~216의 새 후보에서도 중지끝은원본y≈222~225, 약지끝y≈270~274, 소지끝y≈331~344로 분리됐다. 이 수치는 이 자세의 모델관측 비교일 뿐 일반적인 손가락 순서 규칙이나 실제 위치정답이 아니다. 가림이 다른 바레·빠른전환·다른촬영으로 일반화됐다고 주장하지 않는다.

## 소스와 실행

- `improve_hand_skeleton.py`: 역변환 가능한 crop/회전/반전 탐색, 전체21점 기록과 그림.
- `fretting_hand_skeleton.py`: 재사용 가능한 `FrettingHandSkeletonDetector`, 하나의실제손을 선택하는 `select_whole_hand`.
- `review_fretting_hand_skeleton.py`: 프레임해시 검증·새검출·원본/이전/개선 사진과 개발오차 평가.
- `test_fretting_hand_skeleton.py`: 변환역산·전체손보존·누락/다중관측·고정자세 회귀.

```powershell
python improve_hand_skeleton.py --output dataset/hand_analysis/runs/skeleton_improvement_20261104_image_v1
python review_fretting_hand_skeleton.py --output dataset/hand_analysis/runs/skeleton_improvement_20261104_focused_v1
python -m unittest test_fretting_hand_skeleton test_hand_anatomical_validity test_hand_fret_tracker test_hand_cell_distribution test_hand_frame_contract test_kim_hand_review test_cell_audio_fusion -q
```

실행완료: 관련7모듈 **55개 통과/실패0**. 출력디렉터리가 이미있으면 덮어쓰지 않으므로 재실행은 새경로를 지정한다. 새검사는8가지정수변환의원본좌표 복원, 원시21점 비혼합·원시관측불변, 누락·다중관측 선택거부, frame210의이자세에서 세끝점분리 및 validity미승격을 검증한다.

공식 API참고: [MediaPipe Hand Landmarker Python](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python). 이번결과는IMAGE모드의별도추론이며 VIDEO추적이나 시간보간을 사용하지 않았다.

## 하류 적용 경계와 다음 작업

새 결과는 새로운 branch와 skeleton hash를 갖는다. 기존baseline ROI의 invalid를 지우지 않았고, 새branch를자동valid로도올리지않았다. 기존production 기본검출과운지·화성run은그대로보존했다. 확인되지 않은 새로운손결과를확정운지에즉시사용하지않는다.

다음은새사진으로중지/약지/소지대응의정성검수를받고, 이설정이현재자세외에도유지되는지확인하는일이다. 손정체성이허용된후에만가상칸·오디오를새branch로재생한다. 이름만바꾸는수정이나소지를오디오로맞추는일은하지않는다.
