"""Join actual upstream grid identities to existing audio, without hand inference."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from audio_cell_compatibility import adapt_grid,compare,to_fusion_audio,STANDARD
from audio_mixture_diagnostics import digest


def build(grids,audio_parent,output):
    grids=Path(grids).resolve();audio_parent=Path(audio_parent).resolve();root=Path(output);root.mkdir(parents=True,exist_ok=False);(root/'fixtures').mkdir()
    tuning=dict(midi_6_to_1=STANDARD,status='assumed',source='explicit_standard_tuning_assumption_not_verified_by_audio_or_visual')
    summaries=[]
    for frame,lo,hi in [(124,5.05,5.35),(190,7.8,8.1),(210,8.75,9.05)]:
        path=grids/f'clip003012_f{frame:06d}_candidate_anchor.json';grid=json.loads(path.read_text())
        image=cv2.imread(grid['frame_identity']['image_file'])
        if image is None or hashlib.sha256(image.tobytes()).hexdigest()!=grid['frame_pixel_sha256']:raise ValueError('Actual grid frame BGR hash mismatch')
        cells=adapt_grid(grid,lo,hi,tuning=tuning,capo=None)
        (root/f'frame_{frame}_cells.json').write_text(json.dumps(cells,indent=2))
        summary=dict(frame_index=frame,frame_pts_s=grid['frame_pts_s'],grid_id=grid['grid_id'],grid_version=grid['grid_version'],geometry_status=grid['geometry_status'],cells=len(cells['cells']),components={})
        for component in ['mixture','accompaniment','vocals']:
            audio_path=audio_parent/component/'evidence.json';audio=json.loads(audio_path.read_text());result=compare(cells,audio)
            result['provenance'].update(grid_file=str(path),grid_file_sha256=digest(path),audio_evidence_file=str(audio_path),audio_evidence_sha256=digest(audio_path),frame_bgr_hash_verified=True)
            (root/f'frame_{frame}_{component}.json').write_text(json.dumps(result,indent=2))
            small=copy.deepcopy(result);small['cells']=[c for c in small['cells'] if c['physical_fret_candidate']==1]
            small['provenance']['fixture_selection']='all virtual strings in physical-fret1 candidate, fixed independent of scores; full cell set in parent result'
            (root/'fixtures'/f'frame_{frame}_{component}.json').write_text(json.dumps(small,indent=2))
            summary['components'][component]=dict(frequency_candidate_supported_cells=sum(c['exact_frequency_score'] is not None and c['exact_frequency_score']>0 for c in result['cells']),
                pc_only_cells=sum(c['status']=='pitch_class_only_support' for c in result['cells']),max_exact_score=max(c['exact_frequency_score'] for c in result['cells']))
            if component=='accompaniment':
                flat=cv2.warpPerspective(image,np.array(grid['M']),tuple(grid['canvas_size']))
                fig,axes=plt.subplots(2,1,figsize=(14,8),gridspec_kw={'height_ratios':[3,1.6]})
                axes[0].imshow(cv2.cvtColor(image,cv2.COLOR_BGR2RGB));axes[0].set_title(f'Original decoded frame {frame}, PTS {grid["frame_pts_s"]:.6f}s; no hand/contact labels');axes[0].axis('off')
                axes[1].imshow(cv2.cvtColor(flat,cv2.COLOR_BGR2RGB));cmap=plt.get_cmap('viridis')
                for c in result['cells']:
                    points=np.array(c['upstream_cell_context']['polygon']);score=c['exact_frequency_score'];axes[1].add_patch(Polygon(points,facecolor=cmap(score) if score is not None else 'gray',alpha=.48,edgecolor='white',lw=.5))
                    axes[1].text(*points.mean(axis=0),c['cell_id'],fontsize=6,color='white',ha='center')
                axes[1].set_title('Estimated virtual grid + audio frequency compatibility[0,1]; geometry suspect; NOT contact probability');axes[1].axis('off')
                fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0,1),cmap=cmap),ax=axes[1],fraction=.025,label='relative compatibility')
                fig.tight_layout();fig.savefig(root/f'frame_{frame}_audio_grid_overlay.png');plt.close(fig)
        summaries.append(summary)
    result=dict(schema_version='actual_grid_audio_join.v1',data_origin='actual_upstream_grid_plus_actual_audio',tuning_status='assumed_standard_not_verified',capo=None,contact='unknown',sounding='unknown',confidence_calibrated=False,frames=summaries)
    (root/'summary.json').write_text(json.dumps(result,indent=2));return result


def build_models(grids,audio_parent,output):
    from virtual_string_grid import assert_grid_compatible
    from fretboard_frame_identity import assert_same_frame
    grids=Path(grids).resolve();audio_parent=Path(audio_parent).resolve();root=Path(output);root.mkdir(parents=True,exist_ok=False)
    build(grids,audio_parent,root/'baseline')
    fixture=json.loads((grids/'same_frame_fixture.json').read_text())
    frame_lookup={f['frame_identity']['frame_index']:f for f in fixture['frames']}
    tuning=dict(midi_6_to_1=STANDARD,status='assumed',source='explicit_standard_tuning_assumption_not_verified_by_audio_or_visual')
    audios={n:json.loads((audio_parent/n/'evidence.json').read_text()) for n in ['mixture','accompaniment','vocals']}
    bundle=dict(schema_version='audio_cell_model_bundle.v1',data_origin='actual_upstream_grid_plus_actual_audio',frames=[])
    for frame,lo,hi in [(124,5.05,5.35),(190,7.8,8.1),(210,8.75,9.05)]:
        upstream=frame_lookup[frame];row=dict(frame_identity=upstream['frame_identity'],start_s=lo,end_s=hi,models=[]);baseline_scores=None
        for model in upstream['models']:
            path=Path(model['grid_json']);grid=json.loads(path.read_text());assert_same_frame(grid,upstream['frame_identity'])
            if grid['grid_id']!=model['grid_id']:raise ValueError('Fixture/model grid ID mismatch')
            cells=adapt_grid(grid,lo,hi,tuning=tuning,capo=None);assert_grid_compatible(grid,cells)
            folder=root/'models'/f'frame_{frame}'/model['model_name'];folder.mkdir(parents=True)
            (folder/'cells_input.json').write_text(json.dumps(cells,indent=2))
            item=dict(model_name=model['model_name'],grid_id=grid['grid_id'],grid_version=grid['grid_version'],grid_json=str(path),cell_input=str((folder/'cells_input.json').resolve()),components={})
            for name,audio in audios.items():
                result=compare(cells,audio);assert_grid_compatible(grid,result)
                result['provenance'].update(grid_file=str(path),grid_file_sha256=digest(path),audio_evidence_file=str(audio_parent/name/'evidence.json'),audio_evidence_sha256=digest(audio_parent/name/'evidence.json'),grid_compatibility_assertion='passed',upstream_fixture=str(grids/'same_frame_fixture.json'),upstream_fixture_sha256=digest(grids/'same_frame_fixture.json'))
                output_path=folder/f'{name}.json';output_path.write_text(json.dumps(result,indent=2))
                small=copy.deepcopy(result);small['cells']=[c for c in small['cells'] if c['physical_fret_candidate']==1]
                small['provenance']['fixture_selection']='physical fret1 across all six virtual strings; independent of score'
                small_path=folder/f'{name}_six_cell_fixture.json';small_path.write_text(json.dumps(small,indent=2))
                adapter_path=folder/f'{name}_fusion_audio.json';adapter_path.write_text(json.dumps(to_fusion_audio(result),indent=2))
                item['components'][name]=dict(result=str(output_path.resolve()),small_fixture=str(small_path.resolve()),fusion_audio=str(adapter_path.resolve()))
                if name=='accompaniment':
                    scores={c['cell_id']:c['exact_frequency_score'] for c in result['cells']}
                    if baseline_scores is None:baseline_scores=scores
                    item['max_audio_score_change_vs_first_model']=max(abs(scores[k]-baseline_scores[k]) for k in scores)
            row['models'].append(item)
        bundle['frames'].append(row)
    bundle.update(frames_analyzed=3,grid_models=18,audio_comparisons=54,join_key=['grid_id','cell_id'],
        explanation='No scores from different grid IDs pooled. Audio is invariant to anchor/spacing changes when virtual-string/fret labels are unchanged; visual mass may change.',
        all_contacts_unknown=True)
    (root/'bundle.json').write_text(json.dumps(bundle,indent=2));return bundle


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--grids',required=True);p.add_argument('--audio-parent',required=True);p.add_argument('--output',required=True);p.add_argument('--all-models',action='store_true');a=p.parse_args();(build_models if a.all_models else build)(a.grids,a.audio_parent,a.output)
