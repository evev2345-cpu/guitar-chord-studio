"""Re-score archived predictions at identical points; NOT new historical inference."""
import hashlib
import json
import os
from collections import Counter,defaultdict
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
RUN=Path(os.environ.get('GCS_EVAL_RUN',str(ROOT/'evaluation/runs/current_20261111_v1'))).resolve()
sys.path.insert(0,str(ROOT/'engine'))
from harmony_engine import TEMPLATES
from metrics import reference,score


def main():
    m=json.loads((RUN/'manifest.json').read_text());old=Path(m['legacy_root'])/'dataset/integration_review/runs'
    scopes=[('harmonic_ablation_20261105_v1',['peak_legacy','peak_cosine','harmonic_legacy','harmonic_cosine']),
            ('cut_audio_features_20261105_v1',['peak','harmonic','supported']),
            ('basic_pitch_20261105_v2',['raw_frames','raw_events','cut_frames','cut_events'])]
    groups={};proof=[]
    for folder,branches in scopes:
        for rec in m['records']:
            if rec['known_timing_issue']:continue
            path=old/folder/'records'/(rec['id']+'.json')
            if not path.exists():raise FileNotFoundError(path)
            data=json.loads(path.read_text())
            assert data.get('sha256',data.get('audio_sha256',rec['audio_sha256']))==rec['audio_sha256']
            assert data['times']==rec['times']
            proof.append(dict(folder=folder,id=rec['id'],sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            for branch in branches:
                for layer,result in data['branches'][branch].items():
                    key=folder+'/'+branch+'/'+rec['dataset']+'/'+layer
                    g=groups.setdefault(key,dict(counts=Counter(),qualities=defaultdict(Counter),files=0,source='archived2026-11-05_predictions_rescored_no_new_inference'))
                    g['files']+=1
                    for frame in result['frames']:
                        r=reference(frame['reference']);top=frame['top3'][:1]
                        pred=[]
                        for c in top:
                            template=next(t for t in TEMPLATES if t['root_pc']==c['root_pc'] and t['quality']==c['quality'])
                            pred.append(dict(template,score=c['score']))
                        s=score(r,pred);assert bool(s['exact'])==frame['correct_top1']
                        g['counts'].update(s);g['qualities'][r['quality']].update(s)
    for g in groups.values():
        c=g['counts'];g['rates']={k:c[k]/c['n'] for k in ['exact','root','quality']}
    (RUN/'historical_comparison.json').write_text(json.dumps(dict(groups=groups,source_records=proof),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Archived comparisons checked:',len(proof),'groups',len(groups))


if __name__=='__main__':main()
