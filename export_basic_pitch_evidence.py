"""Export cached pretrained inference to the existing provisional harmony API."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from basic_pitch_adapter import build_evidence
from harmony_engine import provisional_audio_harmony

def main():
    p=argparse.ArgumentParser();p.add_argument('--prediction',type=Path,required=True);p.add_argument('--source-id',required=True)
    p.add_argument('--offset',type=float,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    if (a.prediction.parent.parent/'superseded.json').exists():raise ValueError('Superseded inference clock; use the v2 prediction')
    meta=json.loads(a.prediction.with_suffix('.json').read_text());source=Path(meta['audio'])
    if hashlib.sha256(source.read_bytes()).hexdigest()!=meta['source_sha256']:raise ValueError('Source hash mismatch')
    with np.load(a.prediction) as data:
        evidence=build_evidence(data['times'],data['note'],meta['note_events'],source_id=a.source_id,start_s=a.offset,duration_s=meta['duration_s'])
    evidence['provenance']=dict(prediction=str(a.prediction.resolve()),prediction_sha256=hashlib.sha256(a.prediction.read_bytes()).hexdigest(),
                               source_audio_sha256=meta['source_sha256'],waveform_cut=meta['mode']=='cut',model_manifest=str(a.prediction.parent/'model.json'))
    a.output.mkdir(parents=True)
    (a.output/'evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    (a.output/'harmony.json').write_text(json.dumps(provisional_audio_harmony(evidence),indent=2),encoding='utf-8')
    print('Exported',len(evidence['pitch_class_salience']),'frames',len(evidence['pitch_candidates']),'note candidates',flush=True)

if __name__=='__main__':main()
