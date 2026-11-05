# 제출물

- `report.md`: 영상 3프레임의 해상도 비교·수작업 기준 대비 오차·한계.
- `resolution_comparison.jpg`: 800×150 / 원본 직접 고해상도 검출 비교.
- `case_0005.00_high_raw.png`: 가림이 상대적으로 적은 구간의 실제 원본 오버레이.
- `case_0194.86_high_raw.png`, `case_0206.03_high_raw.png`: 가림·전환 프레임 오버레이.
- `case_*_high.json`: 원본 식별자/프레임/해시, 이미지 크기, 검출·공통 캔버스 크기, M/M_inv/M_detection, 프렛 번호·출처, 현 후보 모델/관측 구간/물리 번호 출처/미해결 항목.
- `manual_string_references.json`: 오버레이 없는 원본 확대본에서 직접 선택한 수작업 기준점. 코딩 에이전트의 근사 참조이며 사용자 검수 전이다. 프레임당 선명한 4개 선만 평가하며 물리적 현 번호는 미확정이다.
- `evaluation.json`: 기준선과 검출선의 1:1 대응 및 점별 원본/공통 좌표 오차.
- `failure_photo_raw.png`, `failure_photo.json`: 실제 저해상도·손 가림 사진의 검출 실패/물리적 번호 미확정 사례.
- `../label_audit/numbering_report.md`: 프렛 라벨 삭제 후 번호 유지 수정과 기존 예시 부분 검수.

전체 과정 API 호출 0회. 이 모듈은 코드명 판정을 구현하지 않는다.
