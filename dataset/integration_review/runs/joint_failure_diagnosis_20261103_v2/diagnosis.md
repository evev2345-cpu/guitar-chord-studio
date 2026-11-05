# 현 대응·손 선택 실패 진단

원시 관측을 보존하고 동일 프레임 ROI의 별도 후보를 비교했다. 확정 접촉·확정 기타 음은0개다.

ROI candidate recovery: 7/8; production selection remains unchanged.

|frame|PTS|full status|ROI candidate|
|---|---|---|---|
|209|8.750000|no_hand_near_board|same_frame_roi_candidate_near_board|
|210|8.791667|no_hands|same_frame_roi_candidate_near_board|
|211|8.833333|no_hand_near_board|same_frame_roi_candidate_near_board|
|212|8.875000|no_hand_near_board|roi_missing|
|213|8.916667|no_hand_near_board|same_frame_roi_candidate_near_board|
|214|8.958333|no_hand_near_board|same_frame_roi_candidate_near_board|
|215|9.000000|no_hand_near_board|same_frame_roi_candidate_near_board|
|216|9.041667|no_hand_near_board|same_frame_roi_candidate_near_board|

## 해석

- 전체 화면은 지판 쪽 손을 놓치고 반대편 피킹 손만 검출했으며, 210번은 손 자체가 미검출됐다.
- 같은 프레임 ROI는7개에서 지판 근처 손 후보를 제공했다. 212번은 ROI도 없어 복구하지 않았다.
- ROI 후보의 좌표·출처를 별도 보존하고 기존 production 실패 상태는 변경하지 않았다.
- ROI는 기존 Kim 검수에서 오차가 더 컸다. 후보 증가를 정확도 향상이나 접촉 복구로 보고하지 않는다.
- 현 padding에 따라 가장자리 추가 선이 나타나거나 사라진다. 6개가 나왔다는 이유만으로6현 정답으로 승격하지 않는다.
- 3번째 창도 같은 프레임 손·지판·현·음향 후보를 이제 진단 비교할 수 있다. 실제 현 번호와 접촉은 계속 unknown이다.
- 창 중앙값에 대한 좌표 변동은 실제 움직임을 포함하므로 순수 지터/위치오차로 부르지 않는다.
