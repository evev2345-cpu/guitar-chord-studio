"""Frozen 80/20 model evaluation against analyst-read tutorial + visible hand reference.

References never enter detector, spatial mass or chord ranking inputs.
"""
import json
import csv
import cv2
import numpy as np
from joint_evidence_review import ROOT,read
from global_fretting_hand import detect_global_fretting
from fretting_hand_skeleton import FrettingHandSkeletonDetector
from fretboard_frame_identity import make_frame_identity,sha256_file
from review_fretboard_clip import track,make_board
from virtual_string_grid import build_grid
from harmony_engine import provisional_audio_harmony,QUALITIES,NAMES
from compare_new_hand_harmony import visual_mass,rerank

REFERENCES={195:('F#',6,'major',[2,4,4,3,2,2]),197:('Fm',5,'minor',[1,3,3,1,1,1]),
            199:('F#',6,'major',[2,4,4,3,2,2]),207:('F#',6,'major',[2,4,4,3,2,2]),
            209:('F7',5,'7',[1,3,1,2,1,1]),211:('G#',8,'major',[4,6,6,5,4,4]),
            221:('G#7',8,'7',[4,6,4,5,4,4]),223:('A',9,'major',[None,0,2,2,2,0]),
            225:('G#7',8,'7',[4,6,4,5,4,4])}
EXCLUDED={201:'hand moves toward next C# at +0.208s',203:'diagram advances F# to G#; proximity to transition',
          205:'Fm to Bbm change within neighborhood',213:'B to G#m7 change within neighborhood',
          215:'C#m7 to A change within neighborhood',217:'G#7 to C#m7 change within neighborhood',
          219:'hand arrives at A from prior shape within neighborhood'}


def evaluate(candidates,reference):
    key=lambda c:(c['root_pc'],c['quality'])
    target=(reference['concert_root_pc'],reference['quality'])
    tied=[c for c in candidates if abs(c['score']-candidates[0]['score'])<1e-10]
    return dict(exact_top1=key(candidates[0])==target,exact_top3=any(key(c)==target for c in candidates[:3]),
                tied_top1_contains_reference=any(key(c)==target for c in tied),top1_tie_count=len(tied),
                root_top1=candidates[0]['root_pc']==target[0],
                reference_rank=next((i+1 for i,c in enumerate(candidates) if key(c)==target),None))


def main():
    refdir=ROOT/'dataset/integration_review/runs/tutorial_reference_20261105_v1'
    out=ROOT/'dataset/integration_review/runs/tutorial_accuracy_20261105_v1'
    if (out/'result.json').exists():raise FileExistsError(out)
    out.mkdir(parents=True,exist_ok=True)
    frames=read(refdir/'frames.json');references=[]
    for frame in frames:
        t=frame['time']
        if t not in REFERENCES:continue
        shape,root,quality,tab=REFERENCES[t]
        references.append(dict(**frame,shape=shape,shape_root_pc=root,quality=quality,capo=1,
            tab_6_to_1=tab,concert_root_pc=(root+1)%12,concert_symbol=NAMES[(root+1)%12]+('m' if quality=='minor' else '7' if quality=='7' else ''),
            inspected_frame_indices=[frame['frame_index']-5,frame['frame_index'],frame['frame_index']+5],
            stable_interval=[t-.2,t+.2],reference_basis='analyst_read_screen_chord_TAB_diagram_and_visible_fretting_pose',
            review_status='analyst_reviewed_not_second_human_verified',standard_tuning_assumed=True))
    (out/'references.json').write_text(json.dumps(dict(references=references,excluded=EXCLUDED,
        sampling='195..225 every2s before inspecting predictions; discard visible transitions in +/-5 source frames',
        capo_basis='Capo.1 visible; clamp at first physical fret; TAB fingering relative to capo',
        no_reference_used_in_predictions=True),indent=2),encoding='utf-8')
    audio=read(ROOT/'dataset/audio_analysis/runs/barre_194_226_accompaniment_20261104_v1/evidence.json')
    original=cv2.imread(str(ROOT/'dataset/fretboard_review/runs/clip_003_012_20261103_v1/frames/clip003012_f000120.png'))
    results=[]
    with FrettingHandSkeletonDetector(ROOT/'hand_landmarker.task',num_hands=2) as detector:
        for ref in references:
            raw=cv2.imread(ref['image']);identity=make_frame_identity(audio['source_id'],ref['frame_index'],ref['pts'],raw,ref['image'],f"stable_{ref['frame_index']}")
            alignment,matrix=track(original,raw);board=make_board(identity,matrix,alignment,ref['image'])
            hand=detect_global_fretting(detector,raw,np.asarray(board['corners']) if alignment['status']=='valid' else None,previous=None)
            grid=build_grid(board,dict(six_side='top',anchor_y=[15.,15.],opposite_margin=[15.,15.],spacing_scale=1.,anchor_status='assumed_not_observed'))
            pc_mass,fingers=visual_mass(grid,hand['selection']['selected'] if alignment['status']=='valid' else None,12.)
            use_visual=bool(pc_mass.sum()>=.05)
            # Score each complete STFT support separately, then average CHORD scores, not PC sets.
            half=4096/44100
            salience=[f for f in audio['pitch_class_salience'] if ref['stable_interval'][0]<=f['time_s']-half and f['time_s']+half<=ref['stable_interval'][1]]
            if not salience:raise ValueError('No complete audio support inside reference')
            h=provisional_audio_harmony(dict(start_s=ref['stable_interval'][0],end_s=ref['stable_interval'][1],pitch_class_salience=salience),top_k=192)
            all_rows=[f['chord_candidates'] for f in h['salience_frames']]
            by_key={}
            for row in all_rows:
                for c in row:by_key.setdefault((c['root_pc'],c['quality']),[]).append(c)
            averaged=[dict(items[0],score=float(np.mean([c['score'] for c in items]))) for items in by_key.values()]
            averaged.sort(key=lambda c:(-c['score'],c['root_pc'],c['quality']))
            combined=rerank(averaged,pc_mass,.2) if use_visual else averaged
            nearest=min(h['salience_frames'],key=lambda f:abs(f['time_s']-ref['pts']))['chord_candidates']
            single_combined=rerank(nearest,pc_mass,.2) if use_visual else nearest
            record=dict(**identity,reference=ref,audio_only=averaged,combined=combined,
                audio_evaluation=evaluate(averaged,ref),combined_evaluation=evaluate(combined,ref),
                single_frame_audio=nearest[:3],single_frame_combined=single_combined[:3],
                single_frame_audio_evaluation=evaluate(nearest,ref),single_frame_combined_evaluation=evaluate(single_combined,ref),
                audio_analysis_frame_count=len(salience),audio_support_s=ref['stable_interval'],
                visual_used=use_visual,visual_pc_mass=pc_mass.tolist(),fingers=fingers,hand=hand,board=board)
            results.append(record)
            print(ref['time'],ref['shape'],'concert',ref['concert_symbol'],'audio',averaged[0]['concert_symbol'],
                  'combined',combined[0]['concert_symbol'],'correct',record['audio_evaluation']['exact_top1'],record['combined_evaluation']['exact_top1'],flush=True)
    metrics={}
    for branch in ['audio','combined','single_frame_audio','single_frame_combined']:
        field=branch+'_evaluation'
        metrics[branch]={k:sum(r[field][k] for r in results) for k in ['exact_top1','exact_top3','tied_top1_contains_reference','root_top1']}
        metrics[branch]['count']=len(results)
    metrics['improved']=[r['frame_pts_s'] for r in results if not r['audio_evaluation']['exact_top1'] and r['combined_evaluation']['exact_top1']]
    metrics['worsened']=[r['frame_pts_s'] for r in results if r['audio_evaluation']['exact_top1'] and not r['combined_evaluation']['exact_top1']]
    (out/'result.json').write_text(json.dumps(dict(frames=results,metrics=metrics,
        frozen_model=dict(audio_weight=.8,visual_weight=.2,middle_excluded=True,ref_labels_not_used_as_model_input=True),
        reference_sha256=sha256_file(out/'references.json'),audio_sha256=sha256_file(ROOT/'dataset/audio_analysis/runs/barre_194_226_accompaniment_20261104_v1/evidence.json'),
        limitations=['Analyst-derived tutorial reference, not independent human annotation','Standard tuning assumed; capo read from video','Small single-video development sample','Combined is exploratory; strict production visual gates remain withheld']),indent=2),encoding='utf-8')
    (out/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    render(results,out)
    print(json.dumps(metrics,indent=2))


def render(rows,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for part in range(3):
        fig,axes=plt.subplots(3,2,figsize=(14,12))
        for axpair,r in zip(axes,rows[part*3:part*3+3]):
            axpair[0].imshow(cv2.cvtColor(cv2.imread(r['image_file']),cv2.COLOR_BGR2RGB));axpair[0].axis('off')
            ref=r['reference'];axpair[0].set_title(f"PTS {r['frame_pts_s']:.6f}s f{r['frame_index']} | shape {ref['shape']} + capo1 = {ref['concert_symbol']}")
            axpair[1].axis('off')
            text='Reference: '+ref['concert_symbol']+'\n\nAudio:\n'+'\n'.join(f"{c['concert_symbol']} {c['score']:.3f}" for c in r['audio_only'][:3])
            text+='\n\nExploratory 80/20:\n'+'\n'.join(f"{c['concert_symbol']} {c['score']:.3f}" for c in r['combined'][:3])
            text+=f"\n\nExact match: {r['audio_evaluation']['exact_top1']} / {r['combined_evaluation']['exact_top1']}"
            axpair[1].text(.05,.95,text,va='top',fontsize=12)
        fig.suptitle('Tutorial reference verified against visible hand; predictions do not read labels')
        fig.tight_layout(rect=[0,0,1,.97]);fig.savefig(out/f'comparison_{part}.png',dpi=120);plt.close(fig)


if __name__=='__main__':main()
