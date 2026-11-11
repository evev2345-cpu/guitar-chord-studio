"""Verbatim legacy Harte adapter functions. No prediction logic.
Source: original guitarset_benchmark.py; source SHA recorded in protocol.
"""
import re,json
from functools import lru_cache
from harmony_engine import TEMPLATES
from pathlib import Path
SHORTHANDS={'maj':(0,4,7),'min':(0,3,7),'dim':(0,3,6),'aug':(0,4,8),
 'sus2':(0,2,7),'sus4':(0,5,7),'7':(0,4,7,10),'maj7':(0,4,7,11),
 'min7':(0,3,7,10),'hdim7':(0,3,6,10),'dim7':(0,3,6,9),'maj6':(0,4,7,9),
 'min6':(0,3,7,9),'minmaj7':(0,3,7,11),'9':(0,4,7,10,2),'maj9':(0,4,7,11,2),
 'min9':(0,3,7,10,2),'11':(0,4,7,10,2,5),'min11':(0,3,7,10,2,5)}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def degree(text):
    match=re.fullmatch(r'([b#]*)([1-9][0-9]*)',text)
    if match is None:raise ValueError('Unsupported degree: '+text)
    accidental,number=match.groups();n=int(number)-1
    return ([0,2,4,5,7,9,11][n%7]+12*(n//7)+accidental.count('#')-accidental.count('b'))%12

@lru_cache(None)
def parse_chord(label):
    if label in ('N','X'):return None
    match=re.fullmatch(r'([A-G])([#b]*)(?::([^/]*))?(?:/([^/]+))?',label)
    if match is None:raise ValueError('Unsupported chord label: '+label)
    letter,accidental,body,bass=match.groups()
    root=({'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}[letter]+accidental.count('#')-accidental.count('b'))%12
    body='maj' if body is None or body=='' else body
    parts=re.fullmatch(r'([^()]*)\(([^()]*)\)',body)
    mods=[]
    if parts:
        quality,extensions=parts.groups();mods=[x.strip() for x in extensions.split(',') if x.strip()]
    else:quality=body
    if quality=='':intervals={0}
    elif quality in SHORTHANDS:intervals=set(SHORTHANDS[quality])
    else:raise ValueError('Unsupported chord quality: '+label)
    # Root is explicit in Harte encodings; apply omissions/additions before adding bass.
    intervals.add(0)
    for extension in mods:
        if extension.startswith('*'):intervals.discard(degree(extension[1:]))
        else:intervals.add(degree(extension))
    intervals.add(degree(bass or '1'))
    pcs=tuple(sorted((root+i)%12 for i in intervals))
    representable=any(t['root_pc']==root and tuple(t['pcs'])==pcs for t in TEMPLATES)
    return dict(root_pc=root,pcs=pcs,representable=representable,bass_ignored_as_separate_metric=True)

def load_reference(path):
    data=read(path);layers={};notes=[]
    for annotation in data['annotations']:
        namespace=annotation['namespace'];source=annotation['annotation_metadata'].get('data_source')
        if namespace=='chord':
            layer='performed' if source=='Semi-automatic chord transcription with manual verification' else 'nominal' if not source else 'unknown'
            if layer in layers:raise ValueError('Duplicate chord layer')
            layers[layer]=annotation['data']
        elif namespace=='note_midi':
            if source not in list('012345'):raise ValueError('Unexpected string label')
            notes.extend(dict(start=e['time'],end=e['time']+e['duration'],midi=e['value'],string_source=source) for e in annotation['data'])
    if set(layers)!={'nominal','performed'}:raise ValueError('Expected distinct nominal/performed layers')
    return layers,notes
