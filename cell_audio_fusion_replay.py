"""Replay actual A/B cached evidence through C's API and the D fusion boundary."""
import argparse
import json
import hashlib
from pathlib import Path
from audio_cell_compatibility import compare
from cell_audio_fusion import fusion, render, require
from harmony_input_adapter import fusion_from_owner_records
from harmony_engine import provisional_audio_harmony


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def raw_plot(data, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    cells=data['grid']['cells'];frets=sorted({c['physical_fret_candidate'] for c in cells})
    fig,axes=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
    for ax,modality in zip(axes,('video','audio')):
        arr=np.full((6,len(frets)),np.nan)
        for cell in cells:
            cid=cell['cell_id']
            if modality=='video':
                values=[f['cell_masses'].get(cid) for f in data['video']['fingers'] if f['cell_masses'].get(cid) is not None]
                value=max(values) if values else None
            else:value=data['audio']['cells'].get(cid,{}).get('score')
            if value is not None:arr[6-cell['virtual_string_num'],frets.index(cell['physical_fret_candidate'])]=value
        im=ax.imshow(arr,vmin=0,vmax=1,cmap='magma',aspect='auto')
        ax.set(title=f'{modality}: RAW DIAGNOSTIC, decision WITHHELD',xlabel='physical fret candidate',
            xticks=range(len(frets)),xticklabels=frets,yticks=range(6),yticklabels=range(6,0,-1))
    fig.colorbar(im,ax=axes,label='raw mass / compatibility (different meanings)')
    fig.suptitle(f"frame {data['grid']['frame_index']} PTS {data['grid']['frame_pts_s']:.6f}; virtual grid, not contact")
    fig.savefig(path,dpi=130);plt.close(fig)


def replay(output, grid_root='dataset/virtual_string_grid/runs/clip_003_012_20261103_v2'):
    output=Path(output);require(not output.exists(),'choose new output directory');output.mkdir(parents=True)
    grids=Path(grid_root)
    hands=Path('dataset/hand_cell_distribution/runs/virtual_cells_20261103_v1')
    audios=Path('dataset/audio_analysis/runs/clip_003_012_demucs_evidence_v5/accompaniment/fixtures')
    summaries=[]
    for frame,window in ((124,'5.05_5.35'),(190,'7.80_8.10'),(215,'8.75_9.05')):
        for model in ('candidate_anchor','anchor_minus3','anchor_plus3','spacing_minus10pct','spacing_plus10pct','margin_only_alternative'):
            name=f'clip003012_f{frame:06d}_{model}'
            gp=grids/f'{name}.json';hp=hands/f'{name}_hand_cells.json'
            require(gp.is_file() and hp.is_file(),f'missing owner input {name}')
            grid=read(gp);audio=read(audios/f'audio_{window}.json')
            record=dict(grid,start_s=audio['start_s'],end_s=audio['end_s'],timebase=audio['timebase'],
                canvas=grid['canvas_size'],data_origin='actual_grid_conditional_tuning_experiment')
            # Explicit hypothetical standard tuning only; no capo is inferred from the screen.
            compatibility=compare(record,audio,tuning={'midi_6_to_1':[40,45,50,55,59,64],
                'status':'assumed','source':'D_replay_explicit_standard_tuning_hypothesis_not_verified'},capo=None)
            data=fusion_from_owner_records(gp,hp,compatibility)
            audio_path=audios/f'audio_{window}.json'
            data['provenance'].update(audio_fixture_path=str(audio_path.resolve()),
                audio_fixture_sha256=hashlib.sha256(audio_path.read_bytes()).hexdigest(),
                audio_compatibility_implementation_sha256=hashlib.sha256(Path('audio_cell_compatibility.py').read_bytes()).hexdigest())
            data['accompaniment_harmony']=provisional_audio_harmony(audio)
            result=fusion(data)
            folder=output/name;folder.mkdir()
            (folder/'input.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
            (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            if model=='candidate_anchor':
                render(result,folder);raw_plot(data,folder/'raw_modalities.png')
            fingers=data['video']['fingers']
            raw_top={f['finger_id']:(max(f['cell_masses'],key=f['cell_masses'].get)
                if f['cell_masses'] and max(f['cell_masses'].values())>0 else None) for f in fingers}
            summaries.append(dict(frame_index=frame,model=model,grid_id=grid['grid_id'],
                geometry_status=grid['geometry_status'],finger_grades={f['finger_id']:f['quality_status'] for f in fingers},
                raw_visual_top_cells=raw_top,
                raw_audio_top_cell=max(data['audio']['cells'],key=lambda cid:data['audio']['cells'][cid]['score'] or 0),
                experiments={k:dict(status=e['status'],combinations=len(e['combinations'])) for k,e in result['experiments'].items()}))
    (output/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
    return summaries


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    replay(p.parse_args().output)
