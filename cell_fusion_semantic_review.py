"""Render synthetic semantic-gate regression and snapshot real review scope."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from cell_audio_fusion import fusion, require
from harmony_input_adapter import apply_fusion_semantic_policy


def write(path,data):path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')


def synthetic_fixture():
    # Standalone hypothetical cells, not a frame210 measurement.
    data=json.loads(Path('dataset/cell_audio_fusion/fixtures/synthetic_contract.json').read_text(encoding='utf-8'))
    data['data_kind']='synthetic_semantic_gate_stress_not_real_frame'
    base=data['video']['fingers'][0];data['video']['fingers']=[]
    identity=data['grid']
    lineage={k:identity[k] for k in ('source_id','frame_index','frame_pts_s','frame_pixel_sha256')}
    lineage.update(observation_id='synthetic_hand',branch='synthetic',raw_hand_sha256='synthetic_21_point_hand')
    base['observation_lineage']=lineage
    base['semantic_validity']=dict(status='valid',finger_id='index',lineage=copy.deepcopy(lineage),reasons=['synthetic_identity_permission_not_human_review'])
    for name,cid,midi in zip(('middle','ring','pinky'),('s6f1','s5f2','s4f3'),(60,64,67)):
        finger=copy.deepcopy(base);finger.update(finger_id=name,cell_masses={cid:.99},outside_mass=.01,unassigned_mass=0.)
        finger['semantic_validity']['finger_id']=name
        data['video']['fingers'].append(finger)
        cell=next(c for c in data['grid']['cells'] if c['cell_id']==cid)
        cell['possible_midi']=midi
        data['audio']['cells'][cid].update(score=1.,evidence_ids=[cid+':synthetic_peak'])
    return data


def replay(output):
    output=Path(output);require(not output.exists(),'choose new output directory');output.mkdir(parents=True)
    fixture=synthetic_fixture()
    policy=dict(schema_version='fusion_semantic_policy.v1',policy_id='synthetic_review_not_real_frame210',
        lineage=copy.deepcopy(fixture['video']['fingers'][0]['observation_lineage']),
        fingers={name:dict(status='invalid',reasons=['synthetic_chain_identity_failure']) for name in ('middle','ring','pinky')})
    after=apply_fusion_semantic_policy(fixture,policy)
    unknown=copy.deepcopy(fixture)
    for f in unknown['video']['fingers']:f['semantic_validity']['status']='unknown'
    rows=[]
    for name,data in (('valid_assumption_control',fixture),('invalid',after),('unknown',unknown)):
        result=fusion(data)
        write(output/f'{name}_input.json',data);write(output/f'{name}_result.json',result)
        rows.append(dict(case=name,experiments={k:dict(combinations=len(e['combinations']),
            assigned_fingers=sorted({a['finger_id'] for c in e['combinations'] for a in c['assignments']}),
            rankable_cells=sum(r['score'] is not None for f in e['finger_rankings'] for r in f['candidates']),
            chord_hypotheses=sum(len(c['fingering_chord_hypotheses']) for c in e['combinations'])) for k,e in result['experiments'].items()}))
    write(output/'summary.json',rows)
    review_path=Path('dataset/hand_analysis/human_review_20261103/frame210_finger_identity_review.json')
    review=json.loads(review_path.read_text(encoding='utf-8'))
    image=Path(review['reviewed_image'])
    require(hashlib.sha256(image.read_bytes()).hexdigest()==review['reviewed_image_sha256'],'reviewed skeleton image hash changed')
    write(output/'actual_review_scope.json',dict(review=review,review_path=str(review_path.resolve()),
        review_file_sha256=hashlib.sha256(review_path.read_bytes()).hexdigest(),
        actual_raw_hand_sidecar_status='not_applied_in_synthetic_run_use_separate_actual_replay',
        actual_review_not_applied_to_synthetic=True))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    names=list(rows[0]['experiments']);fig,axes=plt.subplots(1,2,figsize=(12,4),constrained_layout=True)
    for i,row in enumerate(rows):
        axes[0].plot(names,[row['experiments'][k]['rankable_cells'] for k in names],marker='o',label=row['case'])
        axes[1].plot(names,[row['experiments'][k]['combinations'] for k in names],marker='o',label=row['case'])
    axes[0].set(title='Synthetic eligible finger-cell rows',ylabel='count')
    axes[1].set(title='Synthetic fingering combinations',ylabel='count')
    for ax in axes:ax.legend(fontsize=8);ax.tick_params(axis='x',rotation=20)
    fig.suptitle('Semantic gate: raw V=.99, A=1 remain diagnostic; invalid/unknown cannot assign')
    fig.savefig(output/'semantic_gate_comparison.png',dpi=140);plt.close(fig)
    return rows


def replay_actual(hand_root, output):
    from audio_cell_compatibility import compare
    from harmony_input_adapter import fusion_from_owner_records
    root=Path(hand_root);output=Path(output)
    require(not output.exists(),'choose new actual output directory');output.mkdir(parents=True)
    audio_path=Path('dataset/audio_analysis/runs/clip_003_012_demucs_evidence_v5/accompaniment/fixtures/audio_8.75_9.05.json')
    audio=json.loads(audio_path.read_bytes());summaries=[];single_summaries=[]
    index_path=root/'downstream_fixtures.json'
    index=json.loads(index_path.read_bytes())
    require(len(index['fixtures'])==30,'expected thirty single distributions')
    for hp in sorted(root.glob('clip003012_f000210_*_hand_cells.json')):
        hand=json.loads(hp.read_bytes());gp=Path(hand['grid_path']);grid=json.loads(gp.read_bytes())
        record=dict(grid,start_s=audio['start_s'],end_s=audio['end_s'],timebase=audio['timebase'],
                    canvas=grid['canvas_size'],data_origin='actual_semantic_sidecar_replay')
        compat=compare(record,audio,tuning={'midi_6_to_1':[40,45,50,55,59,64],'status':'assumed',
            'source':'explicit_replay_hypothesis_not_verified'},capo=None)
        data=fusion_from_owner_records(gp,hp,compat,observation_branch='crop_medoid_actual_observation')
        data['provenance']['audio_fixture_path']=str(audio_path.resolve())
        data['provenance']['audio_fixture_sha256']=hashlib.sha256(audio_path.read_bytes()).hexdigest()
        result=fusion(data);folder=output/hp.stem;folder.mkdir()
        write(folder/'input.json',data);write(folder/'result.json',result)
        experiment=result['experiments']['60_40']
        summary=dict(grid_id=grid['grid_id'],model=hp.stem,
            previous_hand_record_path=hand['upstream_result_path'],
            previous_hand_record_sha256=hand['upstream_result_sha256'],
            raw_observations_and_masses_unchanged=True,
            finger_states={f['finger_id']:f['semantic_status'] for f in experiment['finger_rankings']},
            raw_position_mass_max={f['finger_id']:max(f['cell_masses'].values(),default=None) for f in data['video']['fingers']},
            combinations={k:len(e['combinations']) for k,e in result['experiments'].items()},
            invalid_rankable_cells=sum(r['score'] is not None for f in experiment['finger_rankings']
                if f['semantic_status']=='invalid' for r in f['candidates']))
        summaries.append(summary)
        entries=[entry for entry in index['fixtures'] if entry['grid_id']==grid['grid_id']]
        require(len(entries)==5,'five standalone observations required per grid')
        for entry in entries:
            source_path=Path(entry['path']);source=json.loads(source_path.read_bytes())
            original=next(o for o in hand['observations'] if o['observation']['observation_id']==entry['observation_id'])
            require(all(source.get(k)==v for k,v in original.items()) and
                    set(source)-set(original)<= {'review_binding_path','upstream_result_path'},
                    'standalone distribution differs from frame record beyond wrapper provenance')
            finger=next(f for f in data['video']['fingers'] if f['raw_observation_id']==entry['observation_id'])
            require(finger['semantic_validity']['status']==entry['anatomical_validity_status'],'index semantic status mismatch')
            single=copy.deepcopy(data);single['video']['fingers']=[copy.deepcopy(finger)]
            single['provenance']['single_fixture_path']=str(source_path.resolve())
            single['provenance']['single_fixture_sha256']=hashlib.sha256(source_path.read_bytes()).hexdigest()
            single_result=fusion(single)
            target=folder/(entry['observation_id']+'_result.json');write(target,single_result)
            single_summaries.append(dict(input=str(source_path.resolve()),output=str(target.resolve()),
                grid_id=grid['grid_id'],finger_id=finger['finger_id'],semantic_status=finger['semantic_validity']['status'],
                rankable_cells=sum(r['score'] is not None for e in single_result['experiments'].values()
                    for f in e['finger_rankings'] for r in f['candidates']),
                combinations=sum(len(e['combinations']) for e in single_result['experiments'].values())))
    require(len(summaries)==6,'expected six actual grid variants')
    require(sum(s['semantic_status']=='invalid' for s in single_summaries)==18,'expected eighteen scoped invalid observations')
    require(sum(s['semantic_status']=='unknown' for s in single_summaries)==12,'expected twelve unknown observations')
    require(all(s['rankable_cells']==0 and s['combinations']==0 for s in single_summaries),'semantic gate resurrected a reviewed or unknown chain')
    write(output/'summary.json',summaries)
    write(output/'single_fixture_replay.json',single_summaries)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4),constrained_layout=True)
    first=summaries[0];names=list(first['finger_states'])
    axes[0].bar(names,[first['raw_position_mass_max'][k] for k in names],color=['gray' if first['finger_states'][k]=='unknown' else 'crimson' for k in names])
    axes[0].set(title='Actual raw max cell mass (one grid variant)',ylim=(0,1),ylabel='location mass, not pressure')
    axes[1].bar(names,[0]*len(names),color='crimson');axes[1].set(title='Eligible finger-cell scores after semantic gate',ylim=(0,1),ylabel='eligible count (all zero)')
    for i,name in enumerate(names):axes[1].text(i,.15,first['finger_states'][name],ha='center')
    fig.suptitle('Actual frame210 PTS8.791667: reviewed lineage only; no anatomical recovery claimed')
    fig.savefig(output/'actual_semantic_gate.png',dpi=140);plt.close(fig)
    return summaries


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--hand-root',help='Actual owner sidecar root; otherwise synthetic regression')
    a=p.parse_args()
    replay_actual(a.hand_root,a.output) if a.hand_root else replay(a.output)
