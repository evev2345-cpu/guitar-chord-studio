"""Read-only upstream validation and nine-window harmony replay. No audio inference."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from harmony_engine import analyze
from harmony_input_adapter import adapt_audio


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def replay(root, output):
    root, output = Path(root), Path(output)
    require(not output.exists(), 'choose a new output directory')
    comparison = read(root/'comparison.json')
    index = read(root/'fingering_comparison_index.json')
    upstream_replay = read(root/'harmony_replay.json')
    require(index['source_id'] == comparison['source_id'], 'index source mismatch')
    require(len(upstream_replay) == 9, 'upstream replay count mismatch')
    validation = []
    for key, value in comparison['provenance'].items():
        if key.endswith('_sha256'):
            path = comparison['provenance'][key[:-7]]
            require(sha(path) == value, f'provenance hash mismatch: {key}')
            validation.append({'path':path,'sha256':value})
    results, summaries = [], []
    for branch in ('mixture','accompaniment','vocals'):
        parent = read(root/branch/'evidence.json')
        manifest = read(root/branch/'manifest.json')
        require(manifest['source_id']==comparison['source_id']==parent['source_id'], 'branch source mismatch')
        require(manifest['timebase']==comparison['timebase']=='source_video_seconds', 'timebase mismatch')
        require(abs(manifest['start_s']-comparison['start_s'])<1e-9, 'PTS origin mismatch')
        require(sha(root/branch/'original.wav')==comparison['components'][branch]['pcm_sha256'], 'PCM hash mismatch')
        track_ids={n['event_id'] for n in parent['pitch_tracks']}
        peak_ids={n['event_id'] for n in parent['pitch_candidates']}
        for path in sorted((root/branch/'fixtures').glob('audio_*.json')):
            data=read(path)
            require(data['source_id']==comparison['source_id'], 'fixture source mismatch')
            require(data['timebase']==comparison['timebase'], 'fixture timebase mismatch')
            require(comparison['start_s']<=data['start_s']<data['end_s']<=comparison['end_s'], 'fixture outside source')
            identity=data['source_identity']
            require(identity['component']==branch, 'component mismatch')
            require(identity['derived_from_separation']==(branch!='mixture'), 'separation flag mismatch')
            require(not identity['guitar_isolation_verified'], 'unexpected guitar isolation assertion')
            if branch=='accompaniment':
                require(identity['piano_audible_in_reviewed_accompaniment'], 'piano review missing')
            require(data['tuning'] is None and data['capo'] is None, 'unverified tuning/capo changed')
            require(not data['evidence']['observed_audio_notes'], 'unexpected observed notes')
            for candidate in data['fingering_comparison_candidates']:
                require(candidate['pitch_status']=='spectral_peak_candidate' and candidate['contact']=='unknown', 'candidate promoted')
                require(set(candidate['evidence_ids'])<=peak_ids, 'missing peak parent')
                require(all(t['event_id'] in track_ids for t in candidate['persistence_context']), 'missing track parent')
            result=analyze(adapt_audio(data))
            require(not result['chord_candidates'] and not result['mixed_audio_harmony']['chord_candidates'], 'confirmed chord promotion')
            frames=result['provisional_audio_harmony']['salience_frames']
            ranked=[f for f in frames if f['chord_candidates']]
            symbols=[f['chord_candidates'][0]['concert_symbol'] for f in ranked]
            representative=ranked[len(ranked)//2] if ranked else None
            summary=dict(branch=branch,start_s=data['start_s'],end_s=data['end_s'],
                ranked_frames=len(ranked),total_frames=len(frames),
                top1_counts=dict(Counter(symbols)),
                top1_changes=sum(a!=b for a,b in zip(symbols,symbols[1:])),
                ambiguous_frames=sum(f['status']=='ambiguous' for f in ranked),
                exact_top_ties=sum(abs(f['chord_candidates'][0]['score']-f['chord_candidates'][1]['score'])<1e-12 for f in ranked),
                representative=representative)
            summaries.append(summary)
            results.append(dict(input=str(path.resolve()),input_sha256=sha(path),result=result))
    require(len(results)==9, 'expected nine fixtures')
    output.mkdir(parents=True)
    (output/'results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
    (output/'summary.json').write_text(json.dumps(dict(validation=validation,windows=summaries),indent=2,ensure_ascii=False),encoding='utf-8')
    lines=['# Demucs 3창 화성 비교 — 2026-11-03', '',
        '검토창이며 안정음 정답이 아니다. 아래는 중앙 ranked frame의 잠정 상위3개다. 점수는 확률이 아니다.', '',
        '| 시간 | 원음 | 반주 | 보컬 | 반주 변동·모호성 |','|---|---|---|---|---|']
    def label(s):
        r=s['representative']
        return ', '.join(f"{c['concert_symbol']} {c['score']:.3f}" for c in r['chord_candidates']) if r else '보류'
    for a in [s for s in summaries if s['branch']=='accompaniment']:
        peers={s['branch']:s for s in summaries if s['start_s']==a['start_s']}
        lines.append(f"| {a['start_s']:.2f}–{a['end_s']:.2f} | {label(peers['mixture'])} | {label(a)} | {label(peers['vocals'])} | top1 변경 {a['top1_changes']}, 모호 {a['ambiguous_frames']}/{a['ranked_frames']}, 정확 동률 {a['exact_top_ties']} |")
    lines.extend(['', '확정 기타·확정 혼합음 코드와 실제 운지가설은 9개 모두 0이다. 반주에는 피아노가 포함되며 개별 음의 악기 귀속은 unknown이다.',
        '프레임 PC를 합치지 않았다. 전체 시간별 순위·matched/missing/extra PC·salience·event ID·출처·parent persistence는 results.json에 보존한다.',
        '원음과 반주 후보가 비슷해도 기타 보존 증거가 아니다. 보컬 stem 후보도 누출·배음일 수 있다. 실제 A/V 동기는 미검수이며 보정0을 유지한다.'])
    (output/'comparison.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return summaries


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-root',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    replay(args.input_root,args.output)
