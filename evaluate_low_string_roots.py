"""Apply the low-string prior to the frozen real213.8/214/214.2s observations."""
import json
import hashlib
from pathlib import Path
from hand_cell_distribution import sample_projected,integrate_points
from low_string_root_prior import assess,STRING_WEIGHTS,FINGER_WEIGHTS

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'dataset/integration_review/runs/visual_root_tie_20261105_v1/observations.json'
OUT=ROOT/'dataset/integration_review/runs/low_string_root_20261105_v1'

def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True);records=[]
    for row in json.loads(SOURCE.read_text()):
        fingers=list(row['fingers']);selected=row['hand']['selection']['selected']
        if selected:
            pixel=selected['hands'][0]['pixel_landmarks'][12];points,valid=sample_projected(row['grid'],pixel,12,samples=4096)
            fingers.append(dict(finger='middle',pixel=pixel,tip_index=12,**integrate_points(row['grid'],points,valid)))
        scenarios={}
        for name,include in [('middle_excluded',False),('middle_downweighted_0_25',True)]:
            result=assess(row['audio']['0.2']['top3'],fingers,include_uncertain_middle=include,visual_status='unknown')
            scenarios[name]=result
        records.append(dict(pts=row['pts'],image=row['image'],alignment=row['alignment']['status'],hand_selection=row['hand']['selection']['status'],scenarios=scenarios))
        print(row['pts'],{n:dict(order=[c['capo1_shape'] for c in r['exploratory_tie_order']],scores={c['capo1_shape']:r['support']['root_support'][c['root_pc']] for c in r['exploratory_tie_order']},low65={c['capo1_shape']:r['support']['low65_support'][c['root_pc']] for c in r['exploratory_tie_order']},status=r['decision']['status']) for n,r in scenarios.items()})
    result=dict(records=records,config=dict(string_weights=STRING_WEIGHTS,finger_weights=FINGER_WEIGHTS,
        tuning='Unconfirmed standard EADGBE, physical fret includes capo; compare concert roots, then display Capo1 shapes',
        note='IdenticalPC and identicalaudio score ties only; original audio scores/PCs kept. No human reference used.',
        source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),code_sha256=hashlib.sha256((ROOT/'low_string_root_prior.py').read_bytes()).hexdigest()),
        production_reranking_applied=False,uncertainty='Anatomy, precise grid/string positions and contact remain unknown; root preference must not be treated as verified contact')
    (OUT/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')

if __name__=='__main__':main()
