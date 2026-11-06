"""Conservative boundary adapters. Never infer sounding notes from hand positions."""
import copy
import hashlib
import json
from pathlib import Path


def apply_fusion_semantic_policy(data, policy):
    """Attach a sidecar only to its exact raw-hand lineage, never the whole frame."""
    from cell_audio_fusion import SEMANTIC_LINEAGE
    if policy.get('schema_version')!='fusion_semantic_policy.v1':
        raise ValueError('unsupported fusion semantic policy')
    target=policy['lineage']
    if any(k not in target for k in SEMANTIC_LINEAGE):
        raise ValueError('semantic policy requires complete raw observation lineage')
    out=copy.deepcopy(data);matched=[]
    for finger in out['video']['fingers']:
        lineage=finger.get('observation_lineage',{})
        if any(lineage.get(k)!=target[k] for k in SEMANTIC_LINEAGE):continue
        assessment=policy['fingers'].get(finger['finger_id'])
        if assessment is None:continue
        if assessment['status'] not in ('valid','invalid','unknown'):
            raise ValueError('invalid policy semantic status')
        finger['semantic_validity']=dict(status=assessment['status'],
            finger_id=finger['finger_id'],lineage=copy.deepcopy(target),
            reasons=assessment.get('reasons',[]),policy_id=policy['policy_id'])
        matched.append(finger['finger_id'])
    out['semantic_policy_application']=dict(policy=copy.deepcopy(policy),matched_fingers=matched,
        status='matched_exact_lineage' if matched else 'not_applied_lineage_not_matched')
    return out


def fusion_owner_semantic(observation, hand):
    """Verify B's raw21 medoid lineage and review binding before translating state."""
    from hand_anatomical_validity import skeleton_hash, resolve_medoid, anatomical_validity, same_frame
    validity=observation['anatomical_validity'];o=observation['observation']
    if validity.get('schema_version')!='hand_anatomical_validity.v1':
        raise ValueError('unsupported owner anatomical validity')
    binding=json.loads(Path(hand['review_binding_path']).read_bytes())
    review_path=Path(binding['review_path']);review_raw=review_path.read_bytes();review=json.loads(review_raw)
    if hashlib.sha256(review_raw).hexdigest()!=binding['review_sha256']:
        raise ValueError('semantic review file hash mismatch')
    if hashlib.sha256(Path(review['reviewed_image']).read_bytes()).hexdigest()!=binding['reviewed_image_sha256']:
        raise ValueError('reviewed skeleton image hash mismatch')
    raw_frame=next(r for r in map(json.loads,Path(hand['hand_source']).read_text(encoding='utf-8').splitlines())
                   if r['frame_index']==binding['frame_index'])
    raw_roi=[p['pixel'] for p in raw_frame['roi_observations'][0]['landmarks']]
    if not same_frame(raw_frame,binding) or raw_roi!=binding['raw_points']:
        raise ValueError('review baseline raw21 binding mismatch')
    if skeleton_hash(raw_roi)!=binding['lineage']['skeleton_sha256']:
        raise ValueError('review baseline skeleton digest mismatch')
    robust=json.loads(Path(hand['crop_source']).read_bytes())
    frame=next(f for f in robust['frames'] if f['frame_index']==o['frame_index'])
    if not same_frame(frame,o):raise ValueError('raw crop source identity mismatch')
    tip=o['landmark_index'];lineage=resolve_medoid(frame,tip)
    if lineage!=validity['lineage'] or lineage['raw_points'][tip]!=o['pixel']:
        raise ValueError('semantic raw medoid lineage mismatch')
    expected=anatomical_validity(o,lineage,[tip],binding)
    if any(validity.get(k)!=expected[k] for k in ('status','reason','human_review_applied','landmark_indices','anatomical_fingering_evidence_allowed')):
        raise ValueError('owner anatomical policy mismatch')
    canonical={k:o[k] for k in ('source_id','frame_index','frame_pts_s','frame_pixel_sha256')}
    canonical.update(observation_id=o['observation_id'],branch=o['branch'],raw_hand_sha256=lineage['skeleton_sha256'])
    return dict(observation_lineage=canonical,
        anatomical_fingering_evidence_allowed=observation.get('anatomical_fingering_evidence_allowed'),
        cell_semantic_permissions={c['cell_id']:c.get('anatomical_fingering_evidence_allowed') for c in observation['cells']},
        semantic_validity=dict(status=validity['status'],
        finger_id=o['finger'],lineage=copy.deepcopy(canonical),reasons=[validity['reason']],
        human_review_applied=validity['human_review_applied'],
        owner_sidecar=copy.deepcopy(validity),review_binding=copy.deepcopy(binding)))


def fusion_pending_from_grid(grid_path, *, start_s, end_s):
    """Actual grid, explicit absent B/C scores; no synthetic measurements attached."""
    grid_path=Path(grid_path)
    raw=grid_path.read_bytes()
    grid=json.loads(raw)
    keys=('source_id','grid_id','grid_version','frame_index','frame_pts_s',
          'frame_pixel_sha256','canvas_size','M','M_inv')
    identity={k:copy.deepcopy(grid[k]) for k in keys}
    identity.update(start_s=start_s,end_s=end_s,timebase='source_video_seconds')
    g=copy.deepcopy(grid); g.update(identity)
    return dict(schema_version='fusion_cell.v1',data_kind='actual_grid_missing_upstream_scores',grid=g,
        video=dict(identity,score_type='unconditional_location_mass',fingers=[],status='not_provided'),
        audio=dict(identity,score_type='normalized_compatibility_0_1',cells={},quality_status='not_provided'),
        provenance={'grid_path':str(grid_path.resolve()),'grid_file_sha256':hashlib.sha256(raw).hexdigest(),
                    'adapter':'actual_grid_pending_v1','no_scores_invented':True})


def fusion_from_owner_records(grid_path, hand_path, audio_record, *, observation_branch='full_observation'):
    """Strict A/B/C bridge. Branches of the same hand are never pooled."""
    gp,hp=Path(grid_path),Path(hand_path)
    hand=json.loads(hp.read_bytes())
    if hand.get('anatomical_validity_contract')=='hand_anatomical_validity.v1':
        parent_raw=Path(hand['upstream_result_path']).read_bytes()
        if hashlib.sha256(parent_raw).hexdigest()!=hand['upstream_result_sha256']:
            raise ValueError('pre-sidecar hand record hash mismatch')
        previous=json.loads(parent_raw)
        for observation in hand['observations']:
            obs_id=observation['observation']['observation_id']
            old=next(o for o in previous['observations'] if o['observation']['observation_id']==obs_id)
            for key in ('observation','assigned_mass','outside_board_mass','unresolved_geometry_mass','unassigned_mass'):
                if observation[key]!=old[key]:raise ValueError('semantic sidecar altered raw observation or mass')
            if {c['cell_id']:c['position_mass'] for c in observation['cells']}!={c['cell_id']:c['position_mass'] for c in old['cells']}:
                raise ValueError('semantic sidecar altered cell masses')
    revision=None
    if hashlib.sha256(gp.read_bytes()).hexdigest()!=hand['grid_file_sha256']:
        # Explicit metadata-only revision: verify the owner's original artifact,
        # identical cells and A's compatibility API; never reproject stale masses.
        old_path=Path(hand['grid_path']);old_raw=old_path.read_bytes()
        if hashlib.sha256(old_raw).hexdigest()!=hand['grid_file_sha256']:
            raise ValueError('hand grid file hash mismatch')
        old,new=json.loads(old_raw),json.loads(gp.read_bytes())
        from virtual_string_grid import assert_grid_compatible
        assert_grid_compatible(new,old)
        changed={k for k in set(old)|set(new) if old.get(k)!=new.get(k)}
        if not changed<= {'geometry_status','upstream_geometry_validity'}:
            raise ValueError('hand mass grid changed beyond geometry metadata')
        if new.get('geometry_status')=='usable_for_hypotheses':
            raise ValueError('metadata revision must not promote geometry')
        revision={'original_grid_path':str(old_path),'original_grid_sha256':hand['grid_file_sha256'],
            'changed_fields':sorted(changed),'cells_and_transform_unchanged':True}
    out=fusion_pending_from_grid(gp,start_s=audio_record['start_s'],end_s=audio_record['end_s'])
    identity_keys=('source_id','grid_id','grid_version','frame_index','frame_pts_s','frame_pixel_sha256')
    for key in identity_keys:
        if hand.get(key)!=out['grid'][key]: raise ValueError(f'hand identity mismatch {key}')
    if audio_record.get('schema_version')!='audio_cell_compatibility.v1':
        raise ValueError('expected audio owner compatibility result')
    for key in ('source_id','grid_id','grid_version','timebase'):
        if audio_record.get(key)!=out['grid'][key]: raise ValueError(f'audio identity mismatch {key}')
    context=audio_record['grid_context']
    for key in ('frame_index','frame_pts_s','frame_pixel_sha256','M','M_inv'):
        if context.get(key)!=out['grid'][key]: raise ValueError(f'audio grid context mismatch {key}')
    canvas=context.get('canvas_size',context.get('canvas'))
    if canvas!=out['grid']['canvas_size']: raise ValueError('audio canvas missing or mismatch')
    video=out['video']; video['raw_owner_record']=hand
    for observation in hand['observations']:
        if observation['observation']['branch']!=observation_branch:continue
        for key in (*identity_keys,'canvas_size','M','M_inv'):
            if observation.get(key)!=out['grid'][key]: raise ValueError(f'observation mismatch {key}')
        masses={c['cell_id']:c['position_mass'] for c in observation['cells']}
        outside=observation['outside_board_mass'];unresolved=observation['unresolved_geometry_mass']
        # Owner unassigned is inclusive: do not double-count outside/unresolved.
        residual=max(0.,observation['unassigned_mass']-outside-unresolved)
        video['fingers'].append(dict(finger_id=observation['observation']['finger'],
            quality_status='usable' if observation['decision']=='spatial_candidate_only' else 'withheld_owner_abstain',
            cell_masses=masses,outside_mass=outside,unresolved_mass=unresolved,unassigned_mass=residual,
            raw_observation_id=observation['observation']['observation_id'],
            upstream_evidence_grade=observation['upstream_evidence_grade'],reasons=observation['reasons']))
        if 'anatomical_validity' in observation:
            video['fingers'][-1].update(fusion_owner_semantic(observation,hand))
    audio=out['audio'];audio.update(quality_status='usable',raw_owner_record=copy.deepcopy(audio_record),
        source_identity=copy.deepcopy(audio_record['source_identity']))
    for c in audio_record['cells']:
        score=c['audio_compatibility_score']
        ids=[p['event_id'] for p in c['frequency_matches']]
        audio['cells'][c['cell_id']]=dict(score=score,evidence_ids=ids,
            evaluation_status=c['status'],expected_pitch=c['expected_pitch'])
    out['data_kind']='actual_owner_records_conditional_geometry_and_tuning'
    out['provenance'].update(hand_path=str(hp.resolve()),hand_file_sha256=hashlib.sha256(hp.read_bytes()).hexdigest(),
        selected_observation_branch=observation_branch,adapter='owner_abc_v1',
        video_unassigned_mapping='inclusive unassigned minus outside/unresolved; invalid retained in residual')
    out['provenance']['grid_metadata_revision']=revision
    return out


def adapt_audio(record, *, start_s=None, end_s=None, selection_source=None, listening_review=None):
    """Preserve candidate tiers; optional explicit time-local window, no pitch promotion."""
    if record.get('schema_version') != 'guitar_evidence.v1':
        raise ValueError('unsupported audio contract')
    out = copy.deepcopy(record)
    if listening_review is not None:
        review = listening_review
        if (not record.get('source_id') or review.get('source_id') != record['source_id']
                or review.get('timebase') != record.get('timebase')
                or not review['start_s'] <= record['start_s'] < record['end_s'] <= review['end_s']):
            raise ValueError('listening review source/time coverage mismatch')
        out['source_context'] = {
            'source_identity': review.get('source_identity', 'mixed' if review.get('instrument_mix') == 'vocal_and_guitar' else 'unknown'),
            'instrument_mix': review.get('instrument_mix', 'unknown'),
            'reviewer': review.get('reviewer'), 'review_date': review.get('review_date'),
            'review_scope': review.get('scope'), 'pitch_attribution': 'unverified',
            'review_source_id': review['source_id']}
        for key in ('derived_from_separation', 'guitar_isolation_verified', 'piano_audible'):
            if key in review:
                out['source_context'][key] = review[key]
    if start_s is None and end_s is None:
        return out
    if (type(start_s) not in (int, float) or type(end_s) not in (int, float)
            or not record['start_s'] <= start_s < end_s <= record['end_s']
            or not selection_source):
        raise ValueError('window must be within source interval with selection_source')
    out.update(start_s=start_s, end_s=end_s)
    out.setdefault('provenance', {})['harmony_window'] = {
        'parent_interval': [record['start_s'], record['end_s']],
        'selection_source': selection_source,
        'policy': 'confirmed notes must cover entire window; candidates only overlap'}
    for key in ('pitch_candidates', 'tentative_notes', 'acoustic_events'):
        if key in out:
            out[key] = [n for n in out[key] if n['start_s'] < end_s and n['end_s'] > start_s]
    for key in ('onsets', 'pitch_class_salience'):
        if key in out:
            out[key] = [n for n in out[key] if start_s <= n['time_s'] < end_s]
    evidence = out.setdefault('evidence', {})
    for key in ('observed_audio_notes', 'manual_notes', 'string_states'):
        for n in evidence.get(key, []):
            if 'start_s' not in n or 'end_s' not in n:
                raise ValueError('windowed sounding evidence requires explicit temporal support')
    return out


def adapt_legacy_hand(path, *, source_id=None, run_id='legacy_hand_import'):
    path = Path(path)
    raw = path.read_bytes()
    data = json.loads(raw)
    start = data.get('timestamp_ms', 0) / 1000
    selected = data.get('selected_hand_index')
    candidates = [copy.deepcopy(h.get('candidates', [])) for h in data.get('hands', [])
                  if h.get('hand_index') == selected and data.get('status') == 'selected']
    return {'schema_version': 'guitar_evidence.v1', 'run_id': run_id,
        'source_id': source_id, 'start_s': start, 'end_s': start + 1 / 24,
        'timebase': 'source_video_seconds',
        'capo': {'fret': data.get('capo_physical_fret'), 'source': 'legacy_hand_metadata', 'confirmed': False},
        'assumptions': ['legacy_duration_assumed_1_over_24_seconds'],
        'evidence': {'observed_audio_notes': [], 'string_states': [],
                     'hand_position_candidates': candidates},
        'provenance': {'hand_record_path': str(path), 'hand_record_sha256': hashlib.sha256(raw).hexdigest(),
                       'adapter': 'legacy_hand_v1'},
        'limitations': ['Source video SHA-256 not supplied.' if source_id is None else 'Source ID supplied by caller.',
                       'String identity and contact unresolved; no notes generated.']}
