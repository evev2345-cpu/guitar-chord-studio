"""Heuristic audio compatibility for virtual-cell hypotheses, never contact inference."""
import argparse
import copy
import json
import math
import re
from pathlib import Path

STANDARD=[40,45,50,55,59,64]
TIMEBASE='source_video_seconds'


def integer(x,name,low,high):
    if type(x) is not int or not low<=x<=high:raise ValueError(f'Invalid {name}')
    return x


def possible_pitch(cell,tuning,capo):
    s=integer(cell['virtual_string_num'],'virtual string',1,6)
    if not cell.get('is_virtual') or not cell.get('estimated'):
        raise ValueError('Cell must be explicitly virtual and estimated')
    notes=tuning.get('midi_6_to_1') if isinstance(tuning,dict) else None
    if notes is None:return dict(status='unknown_tuning',midi=None,frequency_hz=None)
    if len(notes)!=6:raise ValueError('Tuning requires six entries, order6→1')
    for note in notes:integer(note,'tuning MIDI',0,127)
    if tuning.get('status') not in ['assumed','confirmed']:raise ValueError('Tuning assumption/confirmation must be explicit')
    if capo is not None and not isinstance(capo,dict):raise ValueError('Capo must be null or an object')
    c=None if capo is None or capo.get('fret') is None else integer(capo.get('fret'),'capo fret',0,24)
    if c is not None and capo.get('status') not in ['assumed','confirmed']:raise ValueError('Capo assumption must be explicit')
    p=cell.get('physical_fret_candidate');r=cell.get('relative_fret_candidate')
    if p is None:
        if r is None:return dict(status='unknown_fret',midi=None,frequency_hz=None)
        integer(r,'relative fret',0,36)
        if c is None:return dict(status='unknown_capo_for_relative_fret',midi=None,frequency_hz=None)
        p=c+r
    else:
        integer(p,'physical fret',0,36)
        if c is not None and p<c:raise ValueError('Physical fret lies behind assumed/confirmed capo')
        if r is not None:
            integer(r,'relative fret',0,36)
            if c is not None and p!=c+r:raise ValueError('Physical/relative fret disagreement')
    midi=notes[6-s]+p
    integer(midi,'result MIDI',0,127)
    return dict(status='possible_under_tuning_and_cell_hypothesis',midi=midi,frequency_hz=440*2**((midi-69)/12),
        physical_fret_candidate=p,relative_fret_candidate=p-c if c is not None else None,
        capo_feasibility='unknown' if c is None else 'conditional_on_capo_setting',
        relative_fret_consistency='unverified' if r is not None and c is None else 'not_conflicting')


def adapt_grid(grid,start_s,end_s,*,tuning,capo=None):
    """Read actual upstream A contract without re-estimating its geometry or numbering."""
    if grid.get('grid_version')!='virtual_string_grid.v1' or grid.get('synthetic') is not False:
        raise ValueError('Expected actual upstream virtual-grid candidate, not a synthetic grid')
    fields=['source_id','grid_id','grid_version','frame_index','frame_pts_s','frame_pixel_sha256',
        'canvas_size','image_size','M','M_inv','frame_identity','geometry_source','geometry_status',
        'upstream_geometry_validity','precise_geometry_verified','contact_fret_decision_allowed',
        'anchor_status','spacing_source','numbering_status','assumptions']
    record={k:copy.deepcopy(grid[k]) for k in fields if k in grid}
    record.update(start_s=start_s,end_s=end_s,timebase=TIMEBASE,data_origin='actual_upstream_virtual_grid_hypotheses',
                  tuning=copy.deepcopy(tuning),capo=copy.deepcopy(capo))
    record['cells']=[{k:copy.deepcopy(c[k]) for k in ['cell_id','virtual_string_num','physical_fret_candidate',
        'confirmed_physical_fret_num','physical_string_num','polygon','numbering_status','is_virtual','estimated',
        'contact','sounding','confidence_calibrated'] if k in c} for c in grid['cells']]
    return record


def finite(x):return type(x) in (int,float) and math.isfinite(x)


def bounded_score(p):
    score=p.get('score')
    if not finite(score) or not 0<=score<=1:raise ValueError('Audio score must be finite relative amplitude in[0,1]')
    return score


def compare(cells_record,audio,tuning=None,capo=None,tolerance_cents=50.):
    if not finite(tolerance_cents) or not 0<tolerance_cents<=100:raise ValueError('Invalid cents tolerance')
    sid=cells_record['source_id']
    if not isinstance(sid,str) or not re.fullmatch('[0-9a-f]{64}',sid) or sid!=audio.get('source_id'):
        raise ValueError('Original source SHA-256 mismatch')
    if cells_record.get('timebase')!=TIMEBASE or audio.get('timebase')!=TIMEBASE:raise ValueError('Timebase mismatch')
    lo,hi=cells_record['start_s'],cells_record['end_s']
    if not all(finite(v) for v in [lo,hi]) or not audio['start_s']<=lo<hi<=audio['end_s']:raise ValueError('Time window not covered by audio')
    if not cells_record.get('grid_id') or not cells_record.get('grid_version'):raise ValueError('Grid version required')
    synthetic=cells_record.get('data_origin')=='synthetic_cell_hypotheses'
    if not synthetic:
        integer(cells_record.get('frame_index'),'frame index',0,10**9)
        frame_t=cells_record.get('frame_pts_s')
        if not finite(frame_t) or not lo<=frame_t<hi:raise ValueError('Frame PTS outside cell/audio comparison window')
        if not re.fullmatch('[0-9a-f]{64}',cells_record.get('frame_pixel_sha256','')):raise ValueError('Frame pixel hash required')
    tuning=copy.deepcopy(tuning if tuning is not None else cells_record.get('tuning'))
    capo=copy.deepcopy(capo if capo is not None else cells_record.get('capo'))
    peaks=None if 'pitch_candidates' not in audio else [p for p in audio['pitch_candidates'] if lo<=p['start_s'] and p['end_s']<=hi]
    tracks=None if 'pitch_tracks' not in audio else [p for p in audio['pitch_tracks'] if p['start_s']<hi and p['end_s']>lo]
    support=audio.get('provenance',{}).get('window_support_s')
    if audio.get('pitch_class_salience') and (not finite(support) or support<=0):raise ValueError('Chroma frame support metadata required')
    half=(support or 0)/2
    chroma=None if 'pitch_class_salience' not in audio else [p for p in audio['pitch_class_salience'] if lo<=p['time_s']-half and p['time_s']+half<=hi]
    frame_keys=set(round(p['start_s'],7) for p in peaks or [])
    frame_keys.update(round(p['time_s']-half,7) for p in chroma or [])
    results=[];ids=set()
    for cell in cells_record['cells']:
        if cell['cell_id'] in ids:raise ValueError('Duplicate cell_id')
        ids.add(cell['cell_id']);expected=possible_pitch(cell,tuning,capo)
        base=dict(cell_id=cell['cell_id'],virtual_string_num=cell['virtual_string_num'],physical_fret_candidate=cell.get('physical_fret_candidate'),
            expected_pitch=expected,is_virtual=True,estimated=True,contact='unknown',sounding='unknown',instrument_attribution='unknown',
            confidence_calibrated=False,score_type='heuristic_audio_compatibility_not_probability',
            audio_compatibility_score=None,exact_frequency_score=None,persistent_frequency_score=None,pitch_class_score=None,
            frequency_matches=[],persistent_matches=[],octave_alternatives=[],pitch_class_evidence_ids=[],
            evidence_availability={'pitch_candidates':'missing' if peaks is None else 'present_empty' if not peaks else 'present',
                'pitch_tracks':'missing' if tracks is None else 'present_empty' if not tracks else 'present',
                'pitch_class_salience':'missing' if chroma is None else 'present_empty' if not chroma else 'present'})
        base['upstream_cell_context']={k:copy.deepcopy(cell[k]) for k in ['polygon','numbering_status','confirmed_physical_fret_num','physical_string_num'] if k in cell}
        if expected['midi'] is None:
            base.update(status='unknown_expected_pitch');results.append(base);continue
        hz=expected['frequency_hz'];pc=expected['midi']%12
        scores={key:0. for key in frame_keys}
        for p in peaks or []:
            if p.get('pitch_status') not in ['spectral_peak_candidate','persistent_spectral_peak_candidate']:raise ValueError('Unsupported peak status')
            if p.get('score_type')!='relative_spectral_peak_amplitude':raise ValueError('Unsupported spectral score semantics')
            if not finite(p.get('frequency_hz')) or p['frequency_hz']<=0:raise ValueError('Invalid candidate frequency')
            cents=1200*math.log2(p['frequency_hz']/hz)
            support=dict(event_id=p['event_id'],start_s=p['start_s'],end_s=p['end_s'],frequency_hz=p['frequency_hz'],
                cents_error=cents,midi_delta=12*math.log2(p['frequency_hz']/hz),pitch_status=p['pitch_status'],
                score=bounded_score(p),score_type=p['score_type'],
                frequency_resolution_hz=p.get('frequency_resolution_hz'),
                coincident_vocal_stem_evidence_ids=p.get('coincident_vocal_stem_evidence_ids',[]),instrument_attribution='unknown')
            if abs(cents)<=tolerance_cents:
                base['frequency_matches'].append(support)
                k=round(p['start_s'],7);scores[k]=max(scores.get(k,0),bounded_score(p)*max(0,1-abs(cents)/tolerance_cents))
            else:
                octaves=round(cents/1200)
                if octaves and abs(cents-1200*octaves)<=tolerance_cents:
                    support['octave_difference']=octaves;base['octave_alternatives'].append(support)
        for p in tracks or []:
            if p.get('pitch_status')!='persistent_spectral_peak_candidate':raise ValueError('Unsupported track status')
            if p.get('score_type')!='median_relative_spectral_peak_amplitude':raise ValueError('Unsupported track score semantics')
            if not finite(p.get('frequency_hz')) or p['frequency_hz']<=0:raise ValueError('Invalid track frequency')
            cents=1200*math.log2(p['frequency_hz']/hz)
            if abs(cents)<=tolerance_cents:
                overlap=max(0,min(hi,p['end_s'])-max(lo,p['start_s']))
                score=bounded_score(p)*max(0,1-abs(cents)/tolerance_cents)*overlap/(hi-lo)
                base['persistent_matches'].append(dict(event_id=p['event_id'],start_s=p['start_s'],end_s=p['end_s'],
                    overlap_start_s=max(lo,p['start_s']),overlap_end_s=min(hi,p['end_s']),cents_error=cents,
                    compatibility=score,evidence_ids=p['evidence_ids'],harmonic_ambiguities=p['harmonic_ambiguities'],
                    instrument_attribution='unknown'))
        pc_values=[]
        for p in chroma or []:
            sal=p['salience']
            if len(sal)!=12 or any(not finite(v) or not 0<=v<=1 for v in sal) or sum(sal)>1.00001:raise ValueError('Invalid relative chroma salience')
            pc_values.append(sal[pc]);base['pitch_class_evidence_ids'].append(p['event_id'])
        exact=None if peaks is None else sum(scores.values())/len(scores) if scores else 0.
        persistent=None if tracks is None else max([p['compatibility'] for p in base['persistent_matches']],default=0.)
        pc_score=None if chroma is None else sum(pc_values)/len(pc_values) if pc_values else 0.
        base.update(exact_frequency_score=exact,persistent_frequency_score=persistent,pitch_class_score=pc_score,
            audio_compatibility_score=exact,evaluated_frame_count=len(scores))
        if exact is None:status='missing_frequency_evidence'
        elif exact>0:status='frequency_candidate_support'
        elif pc_score is not None and pc_score>0:status='pitch_class_only_support'
        else:status='no_matching_candidate_evidence'
        base.update(status=status);results.append(base)
    return dict(schema_version='audio_cell_compatibility.v1',source_id=sid,timebase=TIMEBASE,start_s=lo,end_s=hi,
        grid_id=cells_record['grid_id'],grid_version=cells_record['grid_version'],
        frame_index=cells_record.get('frame_index'),frame_pts_s=cells_record.get('frame_pts_s'),frame_pixel_sha256=cells_record.get('frame_pixel_sha256'),
        canvas_size=copy.deepcopy(cells_record.get('canvas_size')),M=copy.deepcopy(cells_record.get('M')),M_inv=copy.deepcopy(cells_record.get('M_inv')),
        geometry_status=cells_record.get('geometry_status'),contact_fret_decision_allowed=False,
        data_origin=cells_record.get('data_origin','upstream_cells'),
        grid_context={k:copy.deepcopy(cells_record[k]) for k in ['frame_index','frame_pts_s','frame_pixel_sha256','frame_identity','input_geometry','canvas','canvas_size','image_size','M','M_inv','geometry_status','upstream_geometry_validity','precise_geometry_verified','contact_fret_decision_allowed','geometry_source','anchor_status','spacing_source','numbering_status','assumptions'] if k in cells_record},
        tuning=tuning,capo=capo,cells=results,source_identity=copy.deepcopy(audio.get('source_identity',{'instrument_attribution':'unknown'})),
        provenance={'audio_run_id':audio['run_id'],'audio_provenance':copy.deepcopy(audio.get('provenance',{})),
            'cents_tolerance':tolerance_cents,'pitch_frame_denominator':'union of complete-window chroma frame supports and observed peak supports',
            'exact_score':'mean over frames of max(relative peak amplitude * max(0,1-|cents|/tolerance))',
            'persistent_score':'max relative track amplitude * cents kernel * window overlap fraction; diagnostic only',
            'pc_score':'mean original 12-class relative salience; retains octave ambiguity',
            'fusion_audio_score':'exact_frequency_score only; no silent PC promotion or missing-value filling'},
        limitations=['Heuristic normalized indices[0,1], not calibrated note/contact probabilities',
            'No matching candidate is not evidence of mute or nonplaying; missing arrays give null',
            'Accompaniment contains piano; shared pitch and harmonics may match a virtual-cell hypothesis',
            'Virtual string identity, geometry, tuning, capo and contact are hypotheses/unknown as supplied',
            'Tracks/peaks/chroma are correlated diagnostics, not independent probabilities',
            'Frame identity/geometry passed through; this module does not verify decoded image geometry'],
        status='provisional_compatibility_only',confidence_calibrated=False)


def to_fusion_audio(result):
    """Explicit adapter for D fusion_cell.v1 audio branch; no video evidence supplied."""
    keys=['source_id','grid_id','grid_version','frame_index','frame_pts_s','frame_pixel_sha256',
          'canvas_size','M','M_inv','start_s','end_s','timebase']
    out={k:copy.deepcopy(result[k]) for k in keys}
    out.update(score_type='normalized_compatibility_0_1',quality_status='usable' if any(c['audio_compatibility_score'] is not None for c in result['cells']) else 'missing',
        quality_scope='feature compatibility evaluable, not verified guitar attribution or geometry',
        source_identity=copy.deepcopy(result['source_identity']),confidence_calibrated=False,
        provenance=copy.deepcopy(result['provenance']),cells={})
    for c in result['cells']:
        out['cells'][c['cell_id']]=dict(score=c['audio_compatibility_score'],
            evidence_ids=[p['event_id'] for p in c['frequency_matches']],evaluation_status=c['status'],
            exact_frequency_score=c['exact_frequency_score'],persistent_frequency_score=c['persistent_frequency_score'],
            pitch_class_score=c['pitch_class_score'],pitch_class_evidence_ids=c['pitch_class_evidence_ids'],
            expected_pitch=copy.deepcopy(c['expected_pitch']),instrument_attribution='unknown',contact='unknown',sounding='unknown',
            source_details='See full audio_cell_compatibility record for cents, harmonic/vocal and temporal supports')
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cells',required=True);p.add_argument('--audio',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();out=Path(a.output)
    if out.exists():raise FileExistsError('Use a new output path')
    result=compare(json.loads(Path(a.cells).read_text()),json.loads(Path(a.audio).read_text()))
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
