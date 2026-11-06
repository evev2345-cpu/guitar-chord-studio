"""Offline, evidence-only pitch conversion and chord candidate ranking."""
import argparse
import copy
import json
import math
from pathlib import Path
import numpy as np

NAMES = ('C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B')
STANDARD = [40, 45, 50, 55, 59, 64]
QUALITIES = {
    'major': (0, 4, 7), 'minor': (0, 3, 7), '5': (0, 7),
    'diminished': (0, 3, 6), 'augmented': (0, 4, 8),
    'sus2': (0, 2, 7), 'sus4': (0, 5, 7), '6': (0, 4, 7, 9),
    'm6': (0, 3, 7, 9), '7': (0, 4, 7, 10), 'maj7': (0, 4, 7, 11),
    'm7': (0, 3, 7, 10), 'm7b5': (0, 3, 6, 10),
    'dim7': (0, 3, 6, 9), 'add9': (0, 2, 4, 7),
}
SUFFIX = {'major': '', 'minor': 'm', 'diminished': 'dim', 'augmented': 'aug'}

TEMPLATES = sorted([dict(root_pc=root, quality=quality, pcs=sorted({(root + i) % 12 for i in intervals}),
                         symbol=NAMES[root] + SUFFIX.get(quality, quality))
                     for root in range(12) for quality, intervals in QUALITIES.items()],
                    key=lambda c: (c['root_pc'], c['quality']))


def rank_saliences(saliences):
    sal = np.asarray(saliences, float)
    total = sum(sal[:, i] for i in range(12))
    active = (sal > 0) & (sal >= 0.1 * sal.max(axis=1)[:, None])
    usable = (total > 0) & (active.sum(axis=1) >= 3)
    scores = np.full((len(sal), len(TEMPLATES)), -np.inf)
    for j, template in enumerate(TEMPLATES):
        target = {(template['root_pc'] + i) % 12 for i in QUALITIES[template['quality']]}
        coverage = sum(sal[:, i] for i in target) / np.maximum(total, 1e-300)
        missing = sum(~active[:, i] for i in target)
        scores[usable, j] = (coverage - 0.15 * missing / len(target))[usable]
    order = np.argsort(-scores, axis=1, kind='stable')
    return scores, order, usable


def probabilities_to_chroma(probabilities, threshold=0.3):
    p = np.asarray(probabilities, float)
    weights = np.where(p >= threshold, p, 0.0)
    sal = np.zeros((len(p), 12))
    for i, midi in enumerate(range(38, 89)):
        sal[:, midi % 12] += weights[:, i]
    return sal / np.maximum(sal.sum(axis=1, keepdims=True), 1e-12)


def pooled_chroma(frame_times, note_frames, query_times, width=0.0, method='max'):
    grid = np.asarray(frame_times, float)
    values = np.asarray(note_frames, float)
    query = np.asarray(query_times, float)
    rows = []
    for t in query:
        if width == 0:
            i = int(np.argmin(abs(grid - t)))
            row = values[i, 17:68]
        else:
            if t - width / 2 < grid[0] or t + width / 2 > grid[-1]:
                continue
            a = np.searchsorted(grid, t - width / 2, side='left')
            b = np.searchsorted(grid, t + width / 2, side='left')
            if a >= b:
                row = np.zeros(51)
            else:
                row = getattr(np, method)(values[a:b, 17:68], axis=0)
        rows.append(row)
    if not rows:
        return np.zeros((0, 12))
    return probabilities_to_chroma(np.array(rows).reshape(-1, 51), 0.3)


def integer(value, name, low=0, high=127):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer in [{low}, {high}]')
    return value


def pitch(midi):
    integer(midi, 'midi')
    return {'midi': midi, 'pitch_class': midi % 12,
            'note_name': f'{NAMES[midi % 12]}{midi // 12 - 1}'}


def fret_note(record, tuning, capo):
    """Unknown, muted and unplayed states never become open strings."""
    out = copy.deepcopy(record)
    state = record.get('state', 'unknown')
    if state not in ('sounding', 'possible', 'unknown', 'muted', 'unplayed'):
        raise ValueError('invalid string state')
    out.update(midi=None, pitch_class=None, note_name=None)
    if state not in ('sounding', 'possible'):
        return out
    string = integer(record.get('string'), 'string', 1, 6)
    p, r = record.get('physical_fret'), record.get('relative_fret')
    if p is None and r is None:
        out['unknown_reason'] = 'fret_unknown'
        return out
    if p is not None:
        integer(p, 'physical_fret')
    if r is not None:
        integer(r, 'relative_fret')
    if capo is None:
        out['unknown_reason'] = 'capo_unknown'
        return out
    if p is not None and r is not None and p != capo + r:
        raise ValueError('physical and relative frets disagree')
    if p is not None and p < capo:
        out['unknown_reason'] = 'physical_fret_behind_capo'
        return out
    p = p if p is not None else capo + r
    out.update(physical_fret=p, relative_fret=p - capo)
    out.update(pitch(tuning[6 - string] + p))
    return out


def rank_chords(notes, bass=None):
    pcs = {n['midi'] % 12 for n in notes}
    if len(pcs) < 3:
        return [], 'fewer_than_three_distinct_pitch_classes'
    candidates = []
    for root in range(12):
        for quality, intervals in QUALITIES.items():
            target = {(root + i) % 12 for i in intervals}
            matched, missing, extra = pcs & target, target - pcs, pcs - target
            score = max(0., (len(matched) - .5 * len(missing) - len(extra))
                        / len(pcs | target))
            if len(matched) < 2 or score < .35:
                continue
            symbol = NAMES[root] + SUFFIX.get(quality, quality)
            if bass is not None and bass % 12 != root:
                symbol += '/' + NAMES[bass % 12]
            candidates.append(dict(concert_symbol=symbol, shape_symbol=None,
                root_pc=root, quality=quality, bass_midi=bass, score=score,
                score_type='heuristic_overlap_v1', matched_pcs=sorted(matched),
                missing_pcs=sorted(missing), extra_pcs=sorted(extra),
                evidence_ids=[n['id'] for n in notes],
                score_components={'matched': len(matched), 'missing': len(missing),
                                  'extra': len(extra), 'union': len(pcs | target)},
                prior_assumptions=['finite_chord_dictionary', 'equal_root_prior']))
    candidates.sort(key=lambda c: (-c['score'], c['root_pc'], c['quality']))
    return candidates[:3], None if candidates else 'no_dictionary_candidate_above_threshold'


def provisional_audio_harmony(data, *, top_k=3):
    """Development hypotheses only; rank each salience frame independently."""
    start, end = data['start_s'], data['end_s']
    frames = []
    for index, frame in enumerate(data.get('pitch_class_salience', [])):
        if not start <= frame['time_s'] < end:
            continue
        weights = frame['salience']
        if (len(weights) != 12 or any(type(w) not in (int, float) or
                not math.isfinite(w) or w < 0 for w in weights)):
            raise ValueError('salience requires twelve finite nonnegative weights')
        total = sum(weights)
        active = {i for i,w in enumerate(weights) if w > 0 and w >= .1 * max(weights)}
        candidates = []
        if total > 0 and len(active) >= 3:
            for root in range(12):
                for quality, intervals in QUALITIES.items():
                    target = {(root+i)%12 for i in intervals}
                    coverage = sum(weights[i] for i in target)/total
                    missing = target-active
                    score = coverage - .15 * len(missing)/len(target)
                    candidates.append(dict(concert_symbol=NAMES[root]+SUFFIX.get(quality,quality),
                        root_pc=root, quality=quality, score=score,
                        score_type='salience_coverage_minus_missing_v1',
                        matched_pcs=sorted(target&active), missing_pcs=sorted(missing),
                        extra_pcs=sorted(active-target), weighted_coverage=coverage,
                        evidence_ids=[frame.get('event_id',f'salience_{index}')],
                        pitch_status='provisional', bass_midi=None, shape_symbol=None))
            candidates.sort(key=lambda n:(-n['score'],n['root_pc'],n['quality']))
        frames.append(dict(time_s=frame['time_s'], chord_candidates=candidates[:top_k],
            status='ambiguous' if len(candidates)>1 and candidates[0]['score']-candidates[1]['score']<.1
                   else 'provisional' if candidates else 'insufficient_evidence',
            active_pcs=sorted(active), salience=weights))
    tentative = []
    for index, n in enumerate(data.get('tentative_notes', [])):
        if (n.get('pitch_status') in ('tentative','provisional') and
                type(n.get('midi')) is int and n.get('start_s',float('inf')) <= start
                and n.get('end_s',-1) >= end):
            tentative.append(dict(n,id=n.get('event_id',f'tentative_{index}')))
    ranked, reason = rank_chords(tentative)
    return dict(scope='audio_component_provisional_not_guitar_confirmed',
        source_identity=copy.deepcopy(data.get('source_identity',data.get('source_context',{'source_identity':'unknown'}))),
        status='hypotheses_only' if ranked or any(f['chord_candidates'] for f in frames) else 'insufficient_evidence',
        salience_frames=frames, tentative_note_candidates=ranked,
        tentative_unknown_reason=reason,
        limitations=['No spectral peaks promoted to notes.',
            'Salience frames are ranked separately, never pooled across time.',
            'Scores are heuristic, not probabilities; piano and other instruments may explain them.',
            'Fingering evidence is separate; no instrument attribution or sounding claim.'])


def analyze(data):
    if data.get('schema_version') != 'guitar_evidence.v1':
        raise ValueError('expected guitar_evidence.v1')
    out = copy.deepcopy(data)
    assumptions = out.setdefault('assumptions', [])
    tuning = out.get('tuning')
    if tuning is None:
        tuning = {'midi_6_to_1': STANDARD[:], 'source': 'standard_tuning_assumption',
                  'confirmed': False}
        assumptions.append('unconfirmed_standard_tuning')
    values = tuning['midi_6_to_1']
    if len(values) != 6:
        raise ValueError('tuning requires six MIDI values ordered 6 to 1')
    for v in values:
        integer(v, 'tuning MIDI')
    capo = out.get('capo')
    if capo is None:
        capo = {'fret': None, 'source': 'not_provided', 'confirmed': False}
    if not isinstance(capo, dict):
        raise ValueError('capo must be null or an object')
    c = capo.get('fret')
    if c is not None:
        integer(c, 'capo', 0, 24)
    if out.get('timebase') != 'source_video_seconds':
        raise ValueError('unsupported timebase')
    start, end = out.get('start_s'), out.get('end_s')
    if (type(start) not in (int, float) or type(end) not in (int, float)
            or not 0 <= start < end < float('inf')):
        raise ValueError('expected finite interval 0 <= start_s < end_s')
    out.update(tuning=tuning, capo=capo)
    evidence = out.setdefault('evidence', {})
    notes = []
    audio = evidence.get('observed_audio_notes', [])
    manual = evidence.get('manual_notes', [])
    accepted_audio = []
    mixture_notes = []
    parent_source = out.get('source_context') or out.get('source_identity') or {}
    parent_separated = isinstance(parent_source, dict) and parent_source.get('derived_from_separation', False)
    excluded = []
    for index, item in enumerate(audio + manual):
        n = copy.deepcopy(item)
        n.setdefault('id', n.get('event_id', f'note_{index}'))
        if n.get('pitch_status') not in (None, 'confirmed'):
            excluded.append(dict(record=n, reason='pitch_not_confirmed'))
            continue
        if 'start_s' in n or 'end_s' in n:
            a, b = n.get('start_s'), n.get('end_s')
            if (type(a) not in (int, float) or type(b) not in (int, float)
                    or not 0 <= a < b < float('inf')):
                raise ValueError('invalid note interval')
            if not a <= start < end <= b:
                excluded.append(dict(record=n, reason='note_does_not_cover_analysis_window'))
                continue
        if n.get('midi') is not None:
            n.update(pitch(n['midi']))
            if index < len(audio):
                mixture_notes.append(n)
                identity = n.get('source_identity', 'unknown')
                if identity not in ('guitar', 'mixed', 'vocal', 'accompaniment', 'unknown'):
                    raise ValueError('invalid audio source_identity')
                if (identity != 'guitar' or n.get('source_attribution_status') != 'verified'
                        or n.get('derived_from_separation', False) or parent_separated):
                    excluded.append(dict(record=n, reason='guitar_source_identity_unverified'))
                    continue
            notes.append(n)
            if index < len(audio):
                accepted_audio.append(n)
    evidence['excluded_note_evidence'] = excluded
    computed = []
    for record in evidence.get('string_states', []):
        if 'start_s' in record or 'end_s' in record:
            a, b = record.get('start_s'), record.get('end_s')
            if (type(a) not in (int, float) or type(b) not in (int, float)
                    or not 0 <= a < b < float('inf')):
                raise ValueError('invalid string state interval')
            if not a <= start < end <= b:
                excluded.append(dict(record=copy.deepcopy(record), reason='string_state_does_not_cover_analysis_window'))
                continue
        computed.append(fret_note(record, values, c))
    for index, n in enumerate(computed):
        n.update(tuning_source=tuning.get('source'), capo_source=capo.get('source'))
        n.setdefault('id', f'string_{index}')
        if n.get('midi') is not None and n.get('state') == 'sounding':
            notes.append(n)
    evidence['computed_string_notes'] = computed
    evidence['possible_notes_from_fingering'] = [n for n in computed if n.get('state') == 'possible']
    bass = evidence.get('confirmed_bass_midi')
    if bass is not None:
        integer(bass, 'confirmed bass')
        if bass not in [n['midi'] for n in notes]:
            raise ValueError('confirmed bass must occur in sounding evidence')
        if bass != min(n['midi'] for n in notes):
            raise ValueError('confirmed bass contradicts lower sounding evidence')
    candidates, reason = rank_chords(notes, bass)
    mixture_candidates, mixture_reason = rank_chords(mixture_notes)
    possible = evidence['possible_notes_from_fingering']
    fingering_candidates, fingering_reason = rank_chords([n for n in possible if n.get('midi') is not None])
    audio_pcs = {n['midi'] % 12 for n in accepted_audio}
    sounding_pcs = {n['midi'] % 12 for n in computed
                    if n.get('state') == 'sounding' and n.get('midi') is not None}
    conflict = bool(audio_pcs and sounding_pcs and audio_pcs != sounding_pcs)
    out.update(chord_candidates=candidates, unknown_reason=reason,
        status='evidence_conflict' if conflict else 'insufficient_evidence' if reason else
               'ambiguous' if len(candidates) > 1 and candidates[0]['score'] - candidates[1]['score'] < .1 else 'ok',
        lowest_detected_midi=min((n['midi'] for n in accepted_audio), default=None),
        lowest_possible_fingering_midi=min((n['midi'] for n in computed if n.get('midi') is not None), default=None),
        confirmed_bass_midi=bass)
    out['analysis_scope'] = 'guitar_confirmed_evidence_or_explicit_manual_assertions'
    out['provisional_audio_harmony'] = provisional_audio_harmony(out)
    out['mixed_audio_harmony'] = {
        'scope': 'confirmed_audio_pitches_without_instrument_attribution',
        'chord_candidates': mixture_candidates, 'unknown_reason': mixture_reason,
        'status': 'insufficient_evidence' if mixture_reason else 'hypotheses_only',
        'limitations': ['These candidates are not confirmed guitar chords.']}
    out['fingering_hypotheses'] = {
        'scope': 'explicit_upstream_possible_joint_string_states',
        'chord_candidates': fingering_candidates, 'unknown_reason': fingering_reason,
        'status': 'insufficient_evidence' if fingering_reason else 'hypotheses_only',
        'limitations': ['Possible pitches do not assert contact or sounding notes.']}
    out.setdefault('limitations', []).extend([
        'Scores are heuristic similarities, not calibrated probabilities.',
        'No key, progression, contact inference or shape-label interpretation.',
        'At most three candidates; ties use root pitch class then quality.',
        'Audio/string set disagreement requires review; neither is corrected.'])
    out.setdefault('provenance', {})['harmony'] = {'algorithm': 'overlap_v1',
        'weights': {'matched': 1, 'missing': -.5, 'extra': -1},
        'hypothesis_search': 'none; upstream joint string states required'}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--video', type=Path, help='Explicit source path; recorded only, no extraction')
    parser.add_argument('--start', type=float, help='Explicit time-local analysis window start')
    parser.add_argument('--end', type=float, help='Explicit time-local analysis window end')
    parser.add_argument('--selection-source', help='Window selection provenance, not a stability assertion')
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding='utf-8-sig'))
    if args.start is not None or args.end is not None:
        from harmony_input_adapter import adapt_audio
        data = adapt_audio(data, start_s=args.start, end_s=args.end,
                           selection_source=args.selection_source)
    if args.video:
        if not args.video.is_file():
            parser.error('video does not exist')
        data.setdefault('provenance', {})['video_path'] = str(args.video)
    result = analyze(data)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
