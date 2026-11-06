"""Cache official six-source Demucs safetensors in this workspace; no package install."""
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent
os.environ['HF_HOME']=str(ROOT/'.cache/audio-models/huggingface')
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'


def main():
    import yaml
    from huggingface_hub import hf_hub_download
    repo='adefossez/HTDemucs-6s'
    config=Path(hf_hub_download(repo,'htdemucs_6s.yaml'))
    bag=yaml.safe_load(config.read_text());paths=[config]
    for signature in bag['models']:paths.append(Path(hf_hub_download(repo,f'{signature}.safetensors')))
    result=dict(provider=repo,model='htdemucs_6s',files=[dict(path=str(p),name=p.name,bytes=p.stat().st_size,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths])
    (ROOT/'docs/guitar-separation-model-manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
