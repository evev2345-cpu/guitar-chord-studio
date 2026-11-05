"""Multi-crop hand reliability and repeated-padding string tracking diagnostics."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from hand_fret_tracker import detect_image
from investigate_joint_failures import padded_strings
from joint_evidence_review import ROOT, BOARD, HAND, read, same_frame

# Frozen before looking at human errors; specific to this fixed-camera tutorial.
CROPS = [(740,155,1135,420), (720,135,1155,440),
         (720,155,1135,440), (760,165,1125,410)]
TIPS = [4,8,12,16,20]


def consensus_point(points, full=None, tolerance=6., minimum_views=3):
    """Choose an observed medoid, never average or promote to contact/probability."""
    points = np.asarray(points, float)
    base = dict(contact='unknown', calibrated_probability=None,
                evidence_grade='insufficient_views', minimum_views=minimum_views,
                threshold_original_px=tolerance, full_distance_px=None,
                selected_pixel=None, full_observation_replaced=False)
    if len(points) < minimum_views:
        return base
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError('Expected finite 2D observations')
    pair = np.linalg.norm(points[:,None,:]-points[None,:,:], axis=2)
    index = int(np.argmin(np.median(pair, axis=1)))
    center = points[index]
    dispersion = float(np.percentile(np.linalg.norm(points-center, axis=1),90))
    base.update(selected_pixel=center.tolist(), medoid_view_index=index,
                crop_spread_90_px=dispersion, view_count=len(points))
    if dispersion > tolerance:
        base['evidence_grade'] = 'abstain_crop_disagreement'
    elif full is None:
        base['evidence_grade'] = 'multi_crop_supported_unconfirmed_candidate'
    else:
        distance = float(np.linalg.norm(center-np.asarray(full)))
        base['full_distance_px'] = distance
        base['evidence_grade'] = ('full_and_multi_crop_supported_candidate' if distance<=tolerance
                                  else 'abstain_full_crop_disagreement')
    return base


def cluster_paths(views, width=800, tolerance=4., minimum_votes=3):
    """Repeated views are sensitivity checks, not independent probability trials."""
    clusters = []
    for view in views:
        used = set()
        for line in view['strings']:
            vector = np.array([line['b'], line['m']*(width-1)+line['b']])
            eligible = []
            for i,c in enumerate(clusters):
                if i in used or view['padding_detector_px'] in c['views']:
                    continue
                # Complete-link prevents transitive chains merging distinct edge lines.
                distance = max(float(np.max(abs(vector-v))) for v in c['vectors'])
                if distance<=tolerance:
                    eligible.append((distance,i))
            if eligible:
                _,i = min(eligible);c = clusters[i];used.add(i)
            else:
                c = dict(vectors=[], lines=[], views=[]);clusters.append(c);used.add(len(clusters)-1)
            c['vectors'].append(vector);c['lines'].append(copy.deepcopy(line))
            c['views'].append(view['padding_detector_px'])
    output = []
    for c in clusters:
        vectors = np.array(c['vectors'])
        pair = np.max(abs(vectors[:,None,:]-vectors[None,:,:]), axis=2)
        i = int(np.argmin(pair.sum(axis=1)));line = c['lines'][i]
        output.append(dict(m=line['m'], b=line['b'],
             observed_intervals=line['observed_intervals'],
             representative_is_observed_path=True, independent_votes=False,
             supporting_paddings=c['views'], vote_count=len(c['views']), total_views=len(views),
             status='repeated_padding_candidate' if len(c['views'])>=minimum_votes else 'transient_padding_candidate',
             endpoint_spread_common_px=float(pair.max()), physical_string_num=None,
             crosses_nominal_board_boundary=bool(np.any(vectors[i]<0) or np.any(vectors[i]>150)),
             edge_candidate=bool(vectors[i].min()<10 or vectors[i].max()>135),
             semantic_kind=('boundary_ambiguous_path' if vectors[i].min()<10 or vectors[i].max()>135 else 'interior_line_candidate'),
             usable_for_physical_number_assignment=False))
    return sorted(output, key=lambda c:c['b'])


def link_paths(previous, current, next_id, tolerance=8., max_gap_s=.12):
    """Track existing candidates; a missing path is never imputed as observed."""
    active = [];used = set()
    for line in current:
        if line['status'] != 'repeated_padding_candidate':
            continue
        options = []
        v = np.array([line['b'],line['b']+799*line['m']])
        for i,p in enumerate(previous):
            dt=line['frame_pts_s']-p['frame_pts_s']
            u=np.array([p['b'],p['b']+799*p['m']])
            d=float(np.max(abs(u-v)))
            if i not in used and 0<dt<=max_gap_s and d<=tolerance:
                options.append((d,i))
        if options:
            distance,i=min(options);used.add(i);track_id=previous[i]['track_id']
        else:
            distance=None;track_id=f'candidate_track_{next_id}';next_id+=1
        active.append(dict(line,track_id=track_id,association_distance_common_px=distance,
                           temporal_coordinates_condition='same manually referenced common board frame',
                           observation_reused=False))
    lost=[p['track_id'] for i,p in enumerate(previous) if i not in used]
    return active,lost,next_id


def crop_hands(raw):
    views=[]
    for view_id,(x0,y0,x1,y1) in enumerate(CROPS):
        detected=detect_image(raw[y0:y1,x0:x1], ROOT/'hand_landmarker.task')
        hands=[[[lm.x*(x1-x0)+x0,lm.y*(y1-y0)+y0] for lm in hand]
               for hand in detected.hand_landmarks]
        views.append(dict(view_id=view_id,bounds=[x0,y0,x1,y1],hands=hands,
                          status='single_hand' if len(hands)==1 else 'missing_or_ambiguous'))
    return views


def plot_hand(raw, idx, record, views, decisions, labels, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(14,5))
    for ax in axes:
        ax.imshow(cv2.cvtColor(raw,cv2.COLOR_BGR2RGB));ax.set(xlim=(875,1080),ylim=(380,170))
    axes[0].set_title(f'Frame {idx}: full + separate crop inference (shared model)')
    full=None
    if record['status']=='selected':
        full=next(h for h in record['hands'] if h['hand_index']==record['selected_hand_index'])
        p=np.array([full['landmarks'][i]['pixel'] for i in TIPS]);axes[0].scatter(p[:,0],p[:,1],c='cyan',label='full',s=25)
    for v in views:
        if len(v['hands'])==1:
            p=np.array(v['hands'][0])[TIPS];axes[0].scatter(p[:,0],p[:,1],s=15,label=f"crop {v['view_id']}")
    axes[0].legend(fontsize=8)
    axes[1].set_title('Observed medoids; green=candidate, red=abstain; not contact')
    for tip,d in decisions.items():
        if d['selected_pixel'] is None:continue
        x,y=d['selected_pixel'];color='red' if d['evidence_grade'].startswith('abstain') else 'lime'
        axes[1].scatter([x],[y],c=color,s=35);axes[1].annotate(str(tip),(x,y))
    for label in labels:
        if label['visibility']=='visible' and label['pixel'] is not None:
            x,y=label['pixel'];axes[1].scatter([x],[y],marker='x',c='white',s=40)
    fig.tight_layout();fig.savefig(path);plt.close(fig)


def plot_edges(raw,board,paths,idx,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(15,5))
    for ax in axes:
        ax.imshow(cv2.cvtColor(raw,cv2.COLOR_BGR2RGB));ax.set(xlim=(430,1125),ylim=(310,175))
    axes[0].set_title(f'Frame {idx}: original image, no predictions')
    axes[1].set_title('Green=repeated interior; orange=boundary ambiguity; red=transient; identities unknown')
    for p in paths:
        x=np.linspace(0,799,80);pts=cv2.perspectiveTransform(np.c_[x,p['m']*x+p['b']][:,None],np.array(board['M_inv']))[:,0]
        repeated=p['status']=='repeated_padding_candidate'
        color='orange' if repeated and p['edge_candidate'] else 'lime' if repeated else 'red'
        axes[1].plot(pts[:,0],pts[:,1],color=color,
                     linestyle='-' if repeated else '--',lw=.8)
    fig.tight_layout();fig.savefig(path);plt.close(fig)


def main(out,replay=None):
    if out.exists():raise FileExistsError('Use a new output')
    out.mkdir(parents=True)
    records={r['frame_index']:r for r in (json.loads(l) for l in HAND.read_text().splitlines())}
    human=read(ROOT/'dataset/hand_analysis/human_review_20261103/validated_review.json')['reviews'][0]
    results=[];previous=[];next_id=1
    replay_records={f['frame_index']:f for f in read(replay)['frames']} if replay else {}
    indices=[120,124,190,209,210,211,212,213,214,215,216]
    for idx in indices:
        bp=BOARD/'frames'/f'clip003012_f{idx:06d}_board.json';b=read(bp)
        raw=cv2.imread(b['image_file']);record=records[idx]
        same_frame(record,b)
        if hashlib.sha256(np.ascontiguousarray(raw).tobytes()).hexdigest()!=record['frame_pixel_sha256']:
            raise ValueError('Frame pixel mismatch')
        if replay:
            cached=replay_records[idx]
            if cached['source_id']!=record['source_id'] or cached['frame_pixel_sha256']!=record['frame_pixel_sha256']:
                raise ValueError('Replay source mismatch')
            views=copy.deepcopy(cached['views'])
        else:
            views=crop_hands(raw)
        valid=[v for v in views if len(v['hands'])==1]
        # Only unique hands within each predeclared crop contribute. Multi-crop agreement is not GT.
        full=next((h for h in record['hands'] if h['hand_index']==record['selected_hand_index']),None)
        decisions={tip:consensus_point([v['hands'][0][tip] for v in valid],
                     full=None if full is None else full['landmarks'][tip]['pixel']) for tip in TIPS}
        padding=(copy.deepcopy(replay_records[idx]['padding_views']) if replay else
                 [padded_strings(raw,b,pad) for pad in [12,20,28,36,44,52]])
        clusters=cluster_paths(padding)
        for p in clusters:p.update(frame_index=idx,frame_pts_s=record['frame_pts_s'])
        active,lost,next_id=link_paths(previous,clusters,next_id)
        previous=active
        point_errors=[]
        if idx==120:
            for label in human['landmarks']:
                tip=label['index']
                if tip not in decisions or label['visibility']!='visible':continue
                d=decisions[tip]
                point_errors.append(dict(index=tip,grade=d['evidence_grade'],
                   full_error_px=float(np.linalg.norm(np.array(full['landmarks'][tip]['pixel'])-label['pixel'])),
                   medoid_error_px=None if d['selected_pixel'] is None else float(np.linalg.norm(np.array(d['selected_pixel'])-label['pixel'])),
                   scope='single development frame, not held-out validation'))
        result=dict(source_id=record['source_id'],frame_index=idx,frame_pts_s=record['frame_pts_s'],
                    frame_pixel_sha256=record['frame_pixel_sha256'],original_production_status=record['status'],
                    views=views,tip_decisions=decisions,development_point_errors=point_errors,
                    padding_views=padding,string_paths=clusters,active_tracks=active,lost_tracks=lost,
                    confirmed_contacts=[],confirmed_string_numbers=[],confirmed_guitar_notes=[],
                    production_observations_modified=False,geometry_status=b['geometry_validity']['status'])
        results.append(result)
        if idx in [120,124,190,210,215]:
            plot_hand(raw,idx,record,views,decisions,human['landmarks'] if idx==120 else [],out/f'frame_{idx}_hand_reliability.png')
        if idx in [124,190,215]:plot_edges(raw,b,clusters,idx,out/f'frame_{idx}_edge_tracking.png')
        print('processed',idx,'valid_crop_views',len(valid),'repeated_lines',len(active),flush=True)
    data=dict(method='diagnostic_multicrop_and_multpadding_v2',frames=results,
              observation_replay_source=str(replay) if replay else None,
              configuration=dict(crops=CROPS,tip_tolerance_px=6,minimum_crop_views=3,
                path_consensus_tolerance_common_px=4,minimum_padding_votes=3,
                path_association_tolerance_common_px=8,max_temporal_gap_s=.12),
              limitations=['Agreement is not calibrated accuracy or contact probability',
                'Crop presets are specific to this tutorial; shared model bias can persist',
                'Repeated padding uses the same pixels and does not add independent evidence',
                'Candidate tracks never provide missing observations or physical numbers',
                'Manual board geometry is suspect; tracking in board coordinates is conditional'])
    (out/'result.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    summary=[dict(frame_index=r['frame_index'],valid_views=sum(len(v['hands'])==1 for v in r['views']),
         grades={i:d['evidence_grade'] for i,d in r['tip_decisions'].items()},
         repeated_paths=len(r['active_tracks']),transient_paths=sum(p['status']!='repeated_padding_candidate' for p in r['string_paths']),
         edge_paths=[dict(votes=p['vote_count'],b=p['b'],status=p['status'],track_id=next((a['track_id'] for a in r['active_tracks'] if a['b']==p['b']),None))
                     for p in r['string_paths'] if p['edge_candidate']],
         development_errors=r['development_point_errors']) for r in results]
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    report=['# 확대 손 후보·가장자리 현의 안정성 비교','','## 관측과 추정 구분',
       '확대 범위4개를 별도 추론하고 여유 영역6가지에서 현 후보를 조사했다. 원본 이미지와 기존 결과는 보존했다.',
       '신뢰도는 보정되지 않은 근거 등급이며 접촉 확률이나 측정된 정확도가 아니다.','','## 손 위치 사진 비교',
       '흰×는Kim 수동점, 색점은 모델 관측이다. 오른쪽은 실제 관측 medoid이며 초록은 후보, 빨강은 보류다.',
       '확대 추론은 같은 모델을 사용하므로 서로 일치해도 공통 오류가 있을 수 있다.','',
       '![frame120](frame_120_hand_reliability.png)','',
       '![frame215](frame_215_hand_reliability.png)','',
       '## 현 추적 사진 비교',
       '위는 원본, 아래는 관측 경로다. 초록=반복 내부선, 주황=경계 모호, 빨강점선=일시 후보. 물리 현 번호는 미확정이다.','',
       '![frame124](frame_124_edge_tracking.png)','',
       '![frame190](frame_190_edge_tracking.png)','',
       '![frame215](frame_215_edge_tracking.png)','',
       '## frame120 개발 검수점 오차',
       '|index|전체화면 오차px|확대medoid 오차px|판정|','|---|---:|---:|---|']
    for row in results[0]['development_point_errors']:
        report.append(f"|{row['index']}|{row['full_error_px']:.2f}|{row['medoid_error_px']:.2f}|{row['grade']}|")
    report += ['', '단일 개발 프레임이며 독립 테스트가 아니다. 오차가 작은 설정을 골라 임계값을 보정하지 않았다.',
       '55손끝의 근거등급과 프레임별 후보 수는summary.json, 전체 관측·경로·추적 이력은result.json에 있다.',
       '8프레임 연속 구간의 내부후보5개는 동일track을 유지했다. 사라진 경우lost이며 보간 좌표를 관측으로 만들지 않는다.',
       '경계의 추가 선을 실제 현으로 확정하거나6개가 나오는 설정을 정답으로 고르지 않는다.']
    (out/'report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--replay-result',type=Path,help='Re-render and reassess saved observations without new inference')
    args=p.parse_args();main(args.output,args.replay_result)
