"""Additional scoring of retained predictions, not predictor modifications."""
from collections import Counter,defaultdict
import csv
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2];RUN=Path(os.environ.get('GCS_EVAL_RUN',str(ROOT/'evaluation/runs/current_20261111_v1'))).resolve()
sys.path.insert(0,str(ROOT/'engine'))
from metrics import reference
from labels import degree


def main():
    manifest=json.loads((RUN/'manifest.json').read_text());groups=defaultdict(Counter);qconf=defaultdict(Counter);losses=[];tempos=[]
    for mode in ['github','patched']:
        for r in manifest['records']:
            if r['known_timing_issue']:continue
            file=RUN/mode/'details'/(r['id']+'.csv');record=RUN/mode/'records'/(r['id']+'.json')
            if not file.exists() or not record.exists():continue
            d=json.loads(record.read_text(encoding='utf-8'))
            if d['status']!='complete':continue
            if r['dataset']=='guitarset':
                true=float(r['id'].split('-')[1]);estimated=d['tempo']['bpm']
                tempos.append(dict(mode=mode,id=r['id'],reference_bpm=true,estimated_bpm=estimated,relative_error=abs(estimated-true)/true))
            points=defaultdict(dict)
            with file.open(encoding='utf-8-sig',newline='') as f:
                for row in csv.DictReader(f):
                    if row['width']!='0.2' or row['view'] not in ['A','B']:continue
                    key=mode+'_'+r['dataset']+'_'+row['layer']+'_'+row['view'];ref=reference(row['reference']);c=json.loads(row['predictions']);g=groups[key];g['n']+=1
                    ref_bass=(ref['root_pc']+degree(row['reference'].rsplit('/',1)[1]))%12 if '/' in row['reference'] else ref['root_pc']
                    if len(c)==1:
                        pred=c[0];pred_bass=pred.get('bass_pc') if isinstance(pred.get('bass_pc'),int) else pred['root_pc'];qconf[key][row['reference_quality']+' -> '+pred['quality']]+=1
                        g['exact_including_labelled_bass']+=int(row['exact']) * int(ref_bass==pred_bass)
                    else:qconf[key][row['reference_quality']+' -> '+('<ambiguous>' if c else '<abstain>')]+=1
                    if ref_bass!=ref['root_pc']:
                        g['nonroot_inversion_n']+=1
                        g['nonroot_inversion_exact']+=int(len(c)==1 and int(row['exact']) and ref_bass==pred_bass)
                    points[(row['layer'],row['time_s'])][row['view']]=row
            for (layer,t),p in points.items():
                if p.get('A',{}).get('exact')=='1' and p.get('B',{}).get('exact')=='0':
                    losses.append(dict(mode=mode,dataset=r['dataset'],id=r['id'],layer=layer,time_s=float(t),reference=p['A']['reference'],A=json.loads(p['A']['predictions']),B=json.loads(p['B']['predictions'])))
    output=dict(bass_spelling={k:dict(c,exact_with_bass_accuracy=c.get('exact_including_labelled_bass',0)/c['n']) for k,c in groups.items()},
                quality_confusions={k:c.most_common() for k,c in qconf.items()},A_correct_B_wrong=losses,tempo_diagnostics=tempos)
    (RUN/'posthoc.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Posthoc groups:',len(groups),'A-correct/B-wrong points:',len(losses))


if __name__=='__main__':main()
