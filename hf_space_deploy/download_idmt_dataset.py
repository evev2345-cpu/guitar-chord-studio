"""Download official Zenodo archive, verify published size/MD5 and safely extract."""
import argparse
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import time
import urllib.request
import zipfile


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--record',type=int,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();root=args.output.resolve();root.mkdir(parents=True,exist_ok=True)
    url=f'https://zenodo.org/api/records/{args.record}'
    with urllib.request.urlopen(url,timeout=60) as response:metadata=json.load(response)
    (root/'zenodo_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    manifests=[]
    for f in metadata['files']:
        if Path(f['key']).name!=f['key']:raise ValueError('Unexpected remote filename')
        path=root/f['key'];size=f['size'];checksum=f['checksum']
        if not checksum.startswith('md5:'):raise ValueError('Expected published MD5')
        started=time.perf_counter()
        if not path.exists():
            partial=path.with_suffix(path.suffix+'.partial');offset=partial.stat().st_size if partial.exists() else 0
            request=urllib.request.Request(f['links']['self'],headers={'Range':f'bytes={offset}-'} if offset else {})
            with urllib.request.urlopen(request,timeout=120) as response:
                if offset and response.status!=206:offset=0
                mode='ab' if offset else 'wb';total=offset;mark=total//(64*1024*1024)
                with partial.open(mode) as target:
                    while True:
                        chunk=response.read(4*1024*1024)
                        if not chunk:break
                        target.write(chunk);total+=len(chunk)
                        if total//(64*1024*1024)>mark:
                            mark=total//(64*1024*1024);print(f['key'],f'{100*total/size:.1f}%',flush=True)
            if partial.stat().st_size!=size:raise ValueError('Downloaded file size mismatch')
            partial.replace(path)
        md5=hashlib.md5();sha=hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda:handle.read(8*1024*1024),b''):md5.update(chunk);sha.update(chunk)
        if path.stat().st_size!=size or 'md5:'+md5.hexdigest()!=checksum:raise ValueError('Published size/checksum mismatch')
        result=dict(path=str(path),size=size,md5=md5.hexdigest(),sha256=sha.hexdigest(),published_checksum=checksum,verified=True,elapsed_s=time.perf_counter()-started)
        if path.suffix.lower()=='.zip':
            destination=root/'extracted'
            with zipfile.ZipFile(path) as archive:
                infos=archive.infolist();seen=set()
                for info in infos:
                    name=PurePosixPath(info.filename)
                    if name.is_absolute() or '..' in name.parts or ':' in info.filename or '\\' in info.filename:raise ValueError('Unsafe ZIP path')
                    resolved=(destination/Path(*name.parts)).resolve()
                    if os.path.commonpath([str(destination.resolve()),str(resolved)])!=str(destination.resolve()):raise ValueError('ZIP path escapes target')
                    if (info.external_attr>>16)&0o170000==0o120000:raise ValueError('ZIP symlink rejected')
                    if info.filename.lower() in seen:raise ValueError('Duplicate ZIP name')
                    seen.add(info.filename.lower())
                print('ZIP members',len(infos),'uncompressed bytes',sum(i.file_size for i in infos),flush=True)
                result['zip_members']=len(infos);result['uncompressed_bytes']=sum(i.file_size for i in infos)
                if not destination.exists():
                    bad=archive.testzip()
                    if bad:raise ValueError('ZIP CRC failure '+bad)
                    destination.mkdir();archive.extractall(destination)
                else:raise FileExistsError('Extraction destination exists; do not overwrite')
                result.update(zip_crc_valid=True,extracted=str(destination))
        manifests.append(result)
    (root/'download_manifest.json').write_text(json.dumps(dict(record=args.record,files=manifests),indent=2),encoding='utf-8')
    print('Verified and extracted',root,flush=True)


if __name__=='__main__':main()
