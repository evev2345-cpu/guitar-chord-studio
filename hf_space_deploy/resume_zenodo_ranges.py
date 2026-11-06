"""Resume an existing archive prefix using bounded parallel official HTTP ranges."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path
import time
import urllib.request
import urllib.parse


def main():
    root=Path('IDMT_SMT_Chords');meta=json.loads((root/'zenodo_metadata.json').read_text());f=meta['files'][0]
    archive=root/f['key'];partial=archive.with_suffix('.zip.partial')
    offset=partial.stat().st_size if partial.exists() else 0;total=f['size']
    if archive.exists():print('Archive already complete');return
    chunks=root/'range_chunks';chunks.mkdir(exist_ok=True)
    url=f"https://zenodo.org/records/{meta['id']}/files/{urllib.parse.quote(f['key'])}?download=1"
    ranges=[(start,min(total,start+8*1024*1024)) for start in range(offset,total,8*1024*1024)]
    print('Resume bytes',offset,'of',total,'chunks',len(ranges),flush=True)
    def fetch(bounds):
        start,end=bounds;path=chunks/f'{start}_{end}.bin'
        if path.exists() and path.stat().st_size==end-start:return path
        for retry in range(4):
            try:
                request=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end-1}'})
                with urllib.request.urlopen(request,timeout=90) as response:
                    if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end-1}/{total}':raise ValueError('Range response mismatch')
                    temporary=path.with_suffix('.partial')
                    with temporary.open('wb') as out:
                        while True:
                            chunk=response.read(1024*1024)
                            if not chunk:break
                            out.write(chunk)
                if temporary.stat().st_size!=end-start:raise ValueError('Range length mismatch')
                temporary.replace(path);return path
            except Exception:
                if retry==3:raise
                time.sleep(2**retry)
    completed=offset
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures={pool.submit(fetch,r):r for r in ranges}
        for n,future in enumerate(as_completed(futures),1):
            path=future.result();completed+=path.stat().st_size
            print(n,'/',len(ranges),f'{completed/total*100:.1f}%',flush=True)
    with partial.open('ab') as target:
        for start,end in ranges:
            with (chunks/f'{start}_{end}.bin').open('rb') as source:
                for chunk in iter(lambda:source.read(1024*1024),b''):target.write(chunk)
    if partial.stat().st_size!=total:raise ValueError('Final archive size mismatch')
    partial.replace(archive)
    print('Assembled archive; run official checksum/extraction next',flush=True)


if __name__=='__main__':main()
