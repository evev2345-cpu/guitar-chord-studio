"""Same-time audio harmony vs explicitly unvalidated visual-compatibility reranking.

Does not bypass production semantic/geometry gates or assert finger contact.
"""
import hashlib
import json
import cv2
import numpy as np
from scipy.io import wavfile
from joint_evidence_review import ROOT,read,same_frame
from harmony_engine import provisional_audio_harmony,QUALITIES
from fretboard_frame_identity import make_frame_identity,sha256_file
from review_fretboard_clip import track,make_board
from virtual_string_grid import build_grid
from hand_cell_distribution import sample_projected,integrate_points

SCENARIOS=[('baseline',12.,1.,'top'),('radius24',24.,1.,'top'),
           ('spacing_minus10',12.,.9,'top'),('spacing_plus10',12.,1.1,'top'),
           ('reverse_string_order',12.,1.,'bottom')]


def rerank(candidates,pc_mass,video_weight=.2):
    """Mass is unconditioned location support under a hypothetical contact interpretation."""
    result=[]
    for c in candidates:
        target={(c['root_pc']+i)%12 for i in QUALITIES[c['quality']]}
        v=float(sum(pc_mass[i] for i in target))
        result.append(dict(c, audio_score=c['score'],visual_compatibility=v,
                           score=(1-video_weight)*c['score']+video_weight*v))
    return sorted(result,key=lambda c:(-c['score'],c['root_pc'],c['quality']))


def visual_mass(grid,selected,radius):
    totals=np.zeros(12);fingers=[]
    if selected is None:return totals,fingers
    # Known middle-tip errors are excluded rather than silently treated as reliable.
    for tip,name in [(8,'index'),(16,'ring'),(20,'pinky')]:
        p=selected['hands'][0]['pixel_landmarks'][tip]
        points,valid=sample_projected(grid,p,radius,samples=4096)
        distribution=integrate_points(grid,points,valid)
        pcs=np.zeros(12)
        for cell in distribution['cells']:
            midi=[64,59,55,50,45,40][cell['virtual_string_num']-1]+cell['physical_fret_candidate']
            pcs[midi%12]+=cell['position_mass']
        totals+=pcs/3
        fingers.append(dict(finger=name,tip_index=tip,pixel=p,anatomical_validity='unknown',
                            assumed_radius_px=radius,pc_mass=pcs.tolist(),**distribution))
    return totals,fingers


def main():
    out=ROOT/'dataset/integration_review/runs/new_hand_harmony_20261105_v3'
    if (out/'result.json').exists():raise FileExistsError(out)
    out.mkdir(parents=True,exist_ok=True)
    hand_paths=[ROOT/'dataset/hand_analysis/runs/global_fretting_20261104_v4_native_first/result.json',
                ROOT/'dataset/hand_analysis/runs/neighbors_4823_20261104_v1/result.json',
                ROOT/'dataset/hand_analysis/runs/middle_temporal_200s_20261104_v4_native_first/result.json']
    pairs=[(r,path) for path in hand_paths for r in read(path)['frames'] if path!=hand_paths[2] or r['frame_index']==4812]
    hands=sorted([r for r,path in pairs],key=lambda r:r['frame_pts_s'])
    hand_sources={r['frame_index']:str(path) for r,path in pairs}
    audio_dir=ROOT/'dataset/audio_analysis/runs/barre_194_226_accompaniment_20261104_v1'
    manifest=read(audio_dir/'manifest.json');audio=read(audio_dir/'evidence.json')
    sep=read(ROOT/'dataset/audio_analysis/runs/barre_194_226_separation_20261104_v1/separation_manifest.json')
    if sep['status']!='completed':raise ValueError('Separation incomplete')
    if sha256_file(sep['input'])!=sep['input_sha256']:raise ValueError('Separation input changed')
    rate,pcm=wavfile.read(manifest['analysis_parent_audio'])
    if rate!=manifest['sample_rate'] or len(pcm)!=manifest['clip_end_sample']-manifest['clip_first_sample']:raise ValueError('Stem sample timeline mismatch')
    reference=cv2.imread(str(ROOT/'dataset/fretboard_review/runs/clip_003_012_20261103_v1/frames/clip003012_f000120.png'))
    records=[]
    for hand in hands:
        if hand['source_id']!=audio['source_id']:raise ValueError('Audio video source mismatch')
        raw=cv2.imread(hand['source_image'])
        identity=make_frame_identity(hand['source_id'],hand['frame_index'],hand['frame_pts_s'],raw,hand['source_image'],f"fusion_f{hand['frame_index']}")
        same_frame(identity,hand)
        evidence,matrix=track(reference,raw)
        board=make_board(identity,matrix,evidence,hand['source_image'])
        (out/f"board_{hand['frame_index']}.json").write_text(json.dumps(board,indent=2),encoding='utf-8')
        nearest=min(audio['pitch_class_salience'],key=lambda f:abs(f['time_s']-hand['frame_pts_s']))
        if abs(nearest['time_s']-hand['frame_pts_s'])>.01:raise ValueError('Audio feature not aligned to frame')
        local=dict(start_s=nearest['time_s']-.000001,end_s=nearest['time_s']+.000001,pitch_class_salience=[nearest])
        harmony=provisional_audio_harmony(local,top_k=192)['salience_frames'][0]
        candidates=harmony['chord_candidates']
        selected=hand['result']['selection']['selected']
        scenarios=[]
        for name,radius,spacing,side in SCENARIOS:
            config=dict(six_side=side,anchor_y=[15.,15.] if side=='top' else [135.,135.],
                        opposite_margin=[15.,15.],spacing_scale=spacing,anchor_status='assumed_not_observed')
            grid=build_grid(board,config)
            mass,fingers=visual_mass(grid,selected if evidence['status']=='valid' else None,radius)
            scenario=dict(name=name,config=config,radius_px=radius,pc_mass=mass.tolist(),retained_mass=float(mass.sum()),fingers=fingers,
                          missing_visual=bool(selected is None or evidence['status']!='valid' or mass.sum()<.05),
                          visual_withheld_reason='hand_missing' if selected is None else
                              'alignment_unusable' if evidence['status']!='valid' else
                              'insufficient_mass_in_supported_cells' if mass.sum()<.05 else None)
            scenario['rankings']={}
            for label,w in [('80audio_20visual',.2),('60audio_40visual',.4),('40audio_60visual',.6)]:
                ranked=candidates if scenario['missing_visual'] else rerank(candidates,mass,w)
                scenario['rankings'][label]=ranked[:3]
            scenarios.append(scenario)
        records.append(dict(**identity,hand_input=hand_sources[hand['frame_index']],
            hand_selection_status=hand['result']['selection']['status'],audio_feature=nearest,
            audio_feature_delta_s=nearest['time_s']-hand['frame_pts_s'],audio_support_s=[nearest['time_s']-4096/rate,nearest['time_s']+4096/rate],
            audio_only=candidates[:3],conservative_fusion=candidates[:3],
            conservative_visual_withheld_reasons=['anatomical_validity_unknown','precise_board_geometry_unverified','contact_unknown'],
            exploratory_scenarios=scenarios,ground_truth_status='no_independent_chord_reference',
            strict_fusion_unchanged=True))
        print(hand['frame_pts_s'],[c['concert_symbol'] for c in candidates[:3]],'->',
              [c['concert_symbol'] for c in scenarios[0]['rankings']['80audio_20visual']],flush=True)
    result=dict(frames=records,provenance=dict(audio_evidence=str(audio_dir/'evidence.json'),audio_evidence_sha256=sha256_file(audio_dir/'evidence.json'),
        accompaniment_sha256=sha256_file(manifest['analysis_parent_audio']),separation_manifest=sep,hand_inputs=[dict(path=str(p),sha256=sha256_file(p)) for p in hand_paths]),
        interpretation='EXPLORATORY reranking is not production-permitted anatomical fingering evidence',
        production_gates_modified=False,middle_tip_excluded=True,tuning='unconfirmed_standard_EADGBE',
        visual_model='virtual strings and provisional physical fret candidates1to6; no open/mute/barre-contact inference',
        av_sync='container source PTS; no perceptual AV calibration',accuracy=None)
    (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    render(records,out)


def render(records,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    selected=[next(r for r in records if r['frame_index']==i) for i in [4812,4823,4943,5135]]
    fig,axes=plt.subplots(4,2,figsize=(14,13))
    for row,r in enumerate(selected):
        raw=cv2.imread(r['image_file']);ax=axes[row,0];ax.imshow(cv2.cvtColor(raw,cv2.COLOR_BGR2RGB));ax.axis('off')
        ax.set_title(f"f{r['frame_index']} PTS {r['frame_pts_s']:.6f}s | {r['hand_selection_status']}")
        board=read(out/f"board_{r['frame_index']}.json")
        for wire in board['frets']:
            p=np.asarray(wire['original_endpoints']);ax.plot(p[:,0],p[:,1],color='yellow',lw=.7)
        for finger in r['exploratory_scenarios'][0]['fingers']:
            p=finger['pixel'];ax.add_patch(plt.Circle(p,finger['assumed_radius_px'],fill=False,color='cyan',lw=1))
        s=r['exploratory_scenarios'][0];ax=axes[row,1]
        a=r['audio_only'];f=s['rankings']['80audio_20visual'];labels=list(dict.fromkeys([c['concert_symbol'] for c in a+f]))
        x=np.arange(len(labels));ax.bar(x-.18,[next((c['score'] for c in a if c['concert_symbol']==v),0) for v in labels],.36,label='Audio top3')
        ax.bar(x+.18,[next((c['score'] for c in f if c['concert_symbol']==v),0) for v in labels],.36,label='Exploratory 80/20 top3')
        ax.set_xticks(x,labels);ax.set_ylim(0,1);ax.legend(fontsize=8);ax.set_ylabel('Heuristic scores (different scales)')
    fig.suptitle('Candidate comparison, not accuracy | middle excluded | no confirmed contact or guitar isolation')
    fig.tight_layout(rect=[0,0,1,.97]);fig.savefig(out/'comparison.png',dpi=125);plt.close(fig)


if __name__=='__main__':main()
