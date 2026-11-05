import json
import hashlib
import evaluate_chord_display as runner
from chord_display_cleanup import stabilize,CONFIG

def main():
    runner.OUT=runner.OUT.with_name('stable_video_review_20261105_v2');runner.stabilize=stabilize;runner.CONFIG=CONFIG;runner.main()
    p=runner.OUT/'config.json';d=json.loads(p.read_text());d['source_sha256']['chord_display_cleanup.py']=hashlib.sha256((runner.ROOT/'chord_display_cleanup.py').read_bytes()).hexdigest();d['scope']='Display cleanup only; no claim of new acoustic accuracy or independent validation';p.write_text(json.dumps(d,indent=2))

if __name__=='__main__':main()
