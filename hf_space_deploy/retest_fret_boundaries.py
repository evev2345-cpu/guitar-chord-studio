"""Paid retest limited to the five previously flagged images."""
import concurrent.futures
import json
from pathlib import Path
import batch_gpt_full_test as batch


def main():
    old=batch.ROOT/'dataset/gpt_full_evaluation'
    names=[]
    for path in sorted(old.glob('*/evaluation.json')):
        r=json.loads(path.read_text(encoding='utf-8'))
        if r.get('unresolved') or r.get('out_of_bounds'):
            names.append(Path(r['image']).stem)
    if len(names)!=5:
        raise SystemExit('Expected exactly five previously flagged images')
    batch.OUT=batch.ROOT/'dataset/gpt_boundary_retest'
    batch.OUT.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(batch.run_one,batch.ROOT/'dataset/labels'/(name+'.json')) for name in names]
        for future in concurrent.futures.as_completed(futures):
            future.result()
            batch.summarize()


if __name__=='__main__':main()
