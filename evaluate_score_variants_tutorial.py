"""Replay frozen nine video references through the same sampled-score variants."""
import json
import numpy as np
from joint_evidence_review import ROOT,read
from guitarset_benchmark import TEMPLATES
from chord_score_variants import score_variants
from compare_guitar_stem_accuracy import safe_evaluate


def main():
    folder=ROOT/'dataset/integration_review/runs/score_variants_tutorial_20261105_v1'
    if (folder/'result.json').exists():raise FileExistsError(folder)
    folder.mkdir(parents=True,exist_ok=True)
    evidence=read(ROOT/'dataset/integration_review/runs/bandcut_weight_sweep_20261105_v1/cut_evidence.json')
    references=read(ROOT/'dataset/integration_review/runs/tutorial_accuracy_20261105_v1/references.json')['references']
    sampled=evidence['pitch_class_salience'][::10];times=np.array([f['time_s'] for f in sampled]);sal=np.array([f['salience'] for f in sampled])
    variants=score_variants(sal);rows=[]
    for ref in references:
        i=int(np.argmin(abs(times-ref['pts'])));record=dict(reference=ref,feature_time_s=float(times[i]),delta_s=float(times[i]-ref['pts']),variants={})
        for name,(scores,order,usable) in variants.items():
            ranked=[dict(root_pc=TEMPLATES[j]['root_pc'],quality=TEMPLATES[j]['quality'],concert_symbol=TEMPLATES[j]['symbol'],score=float(scores[i,j])) for j in order[i]] if usable[i] else []
            record['variants'][name]=dict(top3=ranked[:3],evaluation=safe_evaluate(ranked,ref))
        rows.append(record)
    summary={name:{k:sum(r['variants'][name]['evaluation'][k] for r in rows) for k in ['exact_top1','exact_top3','root_top1']} for name in variants}
    (folder/'result.json').write_text(json.dumps(dict(frames=rows,summary=summary,
        vision_used=False,sampling='100ms grid nearest video PTS; all variants same features; context uses neighboring audio scores'),indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
