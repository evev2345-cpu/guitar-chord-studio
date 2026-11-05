"""Experimental virtual-cell ranking, never contact/sounding probabilities.

Independent fusion_cell.v1 boundary; upstream owner adapters remain explicit.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from harmony_engine import rank_chords

WEIGHTS = {'60_40': (.6,.4), '80_20': (.8,.2), '40_60': (.4,.6),
           'video_only': (1.,0.), 'audio_only': (0.,1.)}
IDENTITY = ('source_id','grid_id','grid_version','frame_index','frame_pts_s',
            'frame_pixel_sha256','canvas_size','M','M_inv','start_s','end_s','timebase')
SEMANTIC_LINEAGE = ('source_id','frame_index','frame_pts_s','frame_pixel_sha256',
                    'observation_id','branch','raw_hand_sha256')


def semantic_state(finger, grid):
    """Identity/chain permission is independent of coordinate quality and scores."""
    validity=finger.get('semantic_validity')
    if validity is None:
        return 'unknown', ['semantic_validity_not_provided']
    require(validity.get('status') in ('valid','invalid','unknown'),'invalid semantic status')
    lineage=finger.get('observation_lineage',{})
    target=validity.get('lineage',{})
    if any(k not in lineage or k not in target or lineage[k]!=target[k] for k in SEMANTIC_LINEAGE):
        return 'unknown',['semantic_observation_lineage_mismatch_or_missing']
    if any(lineage[k]!=grid[k] for k in ('source_id','frame_index','frame_pixel_sha256')):
        return 'unknown',['semantic_frame_identity_mismatch']
    # Grid PTS is rounded upstream to six decimals; raw observation PTS is retained.
    pts=lineage['frame_pts_s']
    if type(pts) not in (int,float) or not math.isfinite(pts) or abs(pts-grid['frame_pts_s'])>1e-6:
        return 'unknown',['semantic_frame_pts_mismatch']
    if not lineage['raw_hand_sha256'] or validity.get('finger_id')!=finger['finger_id']:
        return 'unknown',['semantic_finger_or_raw_hand_mismatch']
    if validity['status']=='valid' and finger.get('anatomical_fingering_evidence_allowed') is False:
        return 'unknown',['owner_anatomical_fingering_permission_denied']
    return validity['status'],list(validity.get('reasons',[]))


def require(value, message):
    if not value:
        raise ValueError(message)


def unit(value, name):
    require(type(value) in (float,int) and math.isfinite(value) and 0<=value<=1,
            f'{name} must be finite in [0,1]')
    return float(value)


def validate(data):
    require(data.get('schema_version')=='fusion_cell.v1','unsupported fusion schema')
    grid, video, audio = (data[k] for k in ('grid','video','audio'))
    for field in IDENTITY:
        require(field in grid, f'missing grid {field}')
        for branch in (video,audio):
            require(branch.get(field)==grid[field], f'identity mismatch: {field}')
    require(grid['start_s']<=grid['frame_pts_s']<grid['end_s'],'frame outside window')
    require(grid['timebase']=='source_video_seconds','unsupported timebase')
    require(all(type(grid[k]) in (int,float) and math.isfinite(grid[k]) for k in ('start_s','end_s','frame_pts_s')),'invalid times')
    require(grid['end_s']>grid['start_s'],'invalid interval')
    for key in ('M','M_inv'):
        matrix=grid[key]
        require(len(matrix)==3 and all(len(row)==3 for row in matrix),'invalid matrix shape')
        require(all(type(v) in (int,float) and math.isfinite(v) for row in matrix for v in row),'invalid matrix values')
    product=[[sum(grid['M'][i][k]*grid['M_inv'][k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    scale=product[2][2]
    require(abs(scale)>1e-12 and all(abs(product[i][j]/scale-int(i==j))<1e-5 for i in range(3) for j in range(3)),'homography inverse mismatch')
    require(bool(grid['source_id']) and bool(grid['frame_pixel_sha256']),'missing source identity')
    cells={c['cell_id']:c for c in grid['cells']}
    require(len(cells)==len(grid['cells']),'duplicate grid cell')
    for c in cells.values():
        require(c.get('estimated') is True and c.get('is_virtual') is True,'cells must be virtual estimates')
        require(type(c['virtual_string_num']) is int and 1<=c['virtual_string_num']<=6,'invalid virtual string')
    require(video.get('score_type')=='unconditional_location_mass','unsupported video score scale')
    require(audio.get('score_type')=='normalized_compatibility_0_1','unsupported audio scale')
    fingers=set()
    for finger in video['fingers']:
        require(finger['finger_id'] not in fingers,'duplicate finger')
        fingers.add(finger['finger_id'])
        mass=sum(unit(v,'location mass') for v in finger['cell_masses'].values())
        rest=sum(unit(finger.get(k,0),k) for k in ('outside_mass','unresolved_mass','unassigned_mass'))
        require(mass+rest<=1+1e-6,'mass exceeds one')
        require(set(finger['cell_masses'])<=cells.keys(),'unknown video cell')
    require(set(audio['cells'])<=cells.keys(),'unknown audio cell')
    for record in audio['cells'].values():
        if record.get('score') is not None:
            unit(record['score'],'audio compatibility')
            require(bool(record.get('evidence_ids')) or (record['score']==0 and record.get('evaluation_status') in
                ('no_matching_candidate_evidence','pitch_class_only_support')),'audio score requires evidence IDs or explicit evaluated-zero status')
    return cells


def fusion(data, *, beam_width=128, top_k=3):
    cells=validate(data)
    out=copy.deepcopy(data)
    grid,video,audio=(data[k] for k in ('grid','video','audio'))
    geometry_ok=grid.get('geometry_status')=='usable_for_hypotheses'
    audio_ok=audio.get('quality_status')=='usable'
    experiments={}
    for name,(wv,wa) in WEIGHTS.items():
        finger_rows=[]
        for finger in video['fingers']:
            semantic,semantic_reasons=semantic_state(finger,grid)
            semantic_ok=semantic=='valid'
            video_ok=finger.get('quality_status')=='usable' and geometry_ok
            rows=[]
            for cid,cell in cells.items():
                cell_denied=finger.get('cell_semantic_permissions',{}).get(cid) is False
                row_semantic='unknown' if cell_denied and semantic=='valid' else semantic
                row_semantic_ok=semantic_ok and not cell_denied
                raw_v=finger['cell_masses'].get(cid)
                v=raw_v if video_ok and row_semantic_ok else None
                ar=audio['cells'].get(cid,{})
                raw_a=ar.get('score')
                a=raw_a if audio_ok and geometry_ok and row_semantic_ok else None
                # Missing is never silently filled or renormalized for a fused row.
                score=wv*(v or 0)+wa*(a or 0) if ((wv==0 or v is not None) and
                        (wa==0 or a is not None)) else None
                used='both' if wv and wa else 'video_only' if wv else 'audio_only'
                rows.append(dict(cell_id=cid,video_score=v,audio_score=a,score=score,
                    raw_video_score=raw_v,raw_audio_score=raw_a,semantic_status=row_semantic,
                    anatomical_fingering_evidence_allowed=row_semantic_ok,
                    confirmed_cell=None,
                    semantic_reasons=semantic_reasons+(['owner_cell_anatomical_permission_denied'] if cell_denied else []),
                    status='rankable_hypothesis' if score is not None else
                        'semantic_invalid' if row_semantic=='invalid' else
                        'semantic_unknown' if row_semantic=='unknown' else
                        'geometry_withheld' if not geometry_ok else 'missing_or_withheld_modality',
                    used_modalities=used, audio_evidence_ids=ar.get('evidence_ids',[]),
                    virtual_string_num=cell['virtual_string_num'],
                    physical_fret_candidate=cell.get('physical_fret_candidate'),
                    contact='unknown',sounding='unknown'))
            rows.sort(key=lambda r: (r['score'] is None,-(r['score'] or 0),r['cell_id']))
            finger_rows.append(dict(finger_id=finger['finger_id'],candidates=rows,
                retained_cell_mass=sum(finger['cell_masses'].values()),
                outside_mass=finger.get('outside_mass'),unresolved_mass=finger.get('unresolved_mass'),
                unassigned_mass=finger.get('unassigned_mass'),quality_status=finger.get('quality_status'),
                semantic_status=semantic,semantic_reasons=semantic_reasons,
                anatomical_fingering_evidence_allowed=semantic_ok,
                observation_lineage=copy.deepcopy(finger.get('observation_lineage'))))
        # Audio-only ranking cannot assign fingers. Geometry/withheld hands never restored.
        combinations=[]
        beam=[dict(assignments=[],vsum=0.,asum=0.,audio_ids=set(),strings={},score=0.)]
        search_allowed=geometry_ok and wv>0
        if search_allowed:
            for fr in finger_rows:
                choices=[r for r in fr['candidates'] if r['score'] is not None and fr['semantic_status']=='valid']
                choices=choices[:12]+[None]
                expanded=[]
                for state in beam:
                    for row in choices:
                        new=copy.deepcopy(state)
                        if row is not None:
                            s=row['virtual_string_num']; fret=row['physical_fret_candidate']
                            # Conservative policy: at most one assigned finger per string, no barre inference.
                            if s in new['strings']: continue
                            new['strings'][s]=fret
                            new['assignments'].append(dict(finger_id=fr['finger_id'],cell_id=row['cell_id']))
                            new['vsum']+=row['video_score'] or 0
                            ids=set(row['audio_evidence_ids'])
                            # Entire overlapping support group counted once; no partial independence assumption.
                            if not ids & new['audio_ids']:
                                new['asum']+=row['audio_score'] or 0
                            new['audio_ids'] |= ids
                        n=max(1,len(finger_rows))
                        new['score']=(wv*new['vsum']+wa*new['asum'])/n
                        expanded.append(new)
                beam=sorted(expanded,key=lambda s:-s['score'])[:beam_width]
            for state in beam:
                if not state['assignments']: continue
                notes=[]
                for assignment in state['assignments']:
                    cell=cells[assignment['cell_id']]
                    midi=cell.get('possible_midi')
                    if type(midi) is int and cell.get('pitch_basis') in ('explicit_assumption','verified_tuning_physical_fret'):
                        notes.append(dict(midi=midi,id=cell['cell_id']))
                chords,reason=rank_chords(notes)
                combinations.append(dict(assignments=state['assignments'],score=state['score'],
                    video_component=wv*state['vsum']/max(1,len(finger_rows)),
                    audio_component=wa*state['asum']/max(1,len(finger_rows)),
                    audio_evidence_ids=sorted(state['audio_ids']),
                    fingering_chord_hypotheses=chords,unknown_reason=reason,
                    contact='unknown',sounding='unknown'))
                if len(combinations)>=top_k: break
        experiments[name]=dict(weights={'video':wv,'audio':wa},finger_rankings=finger_rows,
            combinations=combinations, status='geometry_withheld' if not geometry_ok else
            'hypotheses_only' if combinations else 'no_joint_assignment',
            assignment_ambiguity=(len(combinations)>1 and combinations[0]['score']-combinations[1]['score']<.05))
    out.update(experiments=experiments,confirmed_guitar_chords=[],
        accompaniment_harmony=copy.deepcopy(data.get('accompaniment_harmony')),
        score_type='experimental_weighted_rank_not_probability',
        confidence_calibrated=False,contact='unknown',sounding='unknown',confirmed_cell=None,
        anatomical_recovery='not_completed',
        search=dict(beam_width=beam_width,per_finger_limit=12,top_k=top_k,
            constraint='one finger per string, no barre inference, optional unassigned',
            audio_dedup='overlapping evidence-ID support group counted at most once',
            audio_only='cell ranking only; no finger assignment'),
        limitations=['60:40 is an experimental default, not an optimum.',
            'Raw unconditional visual mass is not renormalized; audio compatibility is not a probability.',
            'Missing/withheld input has no fused score; explicit single-modal experiments remain separate.',
            'No audio chord rescoring; accompaniment harmony does not enter fusion.',
            'Possible MIDI requires explicit upstream tuning/capo assumptions; no notes inferred from pixels.'])
    return out


def render(result, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    fig,axes=plt.subplots(1,5,figsize=(16,4),constrained_layout=True)
    cells=result['grid']['cells']; frets=sorted({c['physical_fret_candidate'] for c in cells})
    for ax,(name,experiment) in zip(axes,result['experiments'].items()):
        arr=np.full((6,len(frets)),np.nan)
        # Heatmap is max rank score over fingers, not sum or contact probability.
        for cell in cells:
            vals=[r['score'] for f in experiment['finger_rankings'] for r in f['candidates']
                  if r['cell_id']==cell['cell_id'] and r['score'] is not None]
            if vals: arr[6-cell['virtual_string_num'],frets.index(cell['physical_fret_candidate'])]=max(vals)
        im=ax.imshow(arr,vmin=0,vmax=1,cmap='magma',aspect='auto')
        ax.set(title=name,xlabel='physical fret candidate',xticks=range(len(frets)),xticklabels=frets,
               yticks=range(6),yticklabels=range(6,0,-1))
    fig.colorbar(im,ax=axes,label='max rank score (not probability)',shrink=.8)
    fig.suptitle(f"{result.get('data_kind','unspecified')} | virtual cells, geometry={result['grid'].get('geometry_status')}")
    fig.savefig(output/'heatmap.png',dpi=150); plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    require(not args.output.exists(),'choose a new output directory')
    data=json.loads(args.input.read_text(encoding='utf-8-sig')); result=fusion(data)
    args.output.mkdir(parents=True)
    result['input_sha256']=hashlib.sha256(args.input.read_bytes()).hexdigest()
    (args.output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    render(result,args.output)


if __name__=='__main__': main()
