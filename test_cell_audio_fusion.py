import copy
import unittest
import json
import tempfile
from pathlib import Path
from cell_audio_fusion import fusion


def fixture():
    identity=dict(source_id='synthetic_source_not_video_hash',grid_id='synthetic_grid',grid_version='v1',
        frame_index=0,frame_pts_s=.5,frame_pixel_sha256='synthetic_no_pixels',canvas_size=[300,150],
        M=[[1,0,0],[0,1,0],[0,0,1]],M_inv=[[1,0,0],[0,1,0],[0,0,1]],start_s=0,end_s=1,timebase='source_video_seconds')
    cells=[dict(cell_id=f's{s}f{f}',virtual_string_num=s,physical_fret_candidate=f,
                is_virtual=True,estimated=True,polygon=[[f*100,(6-s)*25],[f*100+100,(6-s)*25],
                [f*100+100,(7-s)*25],[f*100,(7-s)*25]],possible_midi=40+(6-s)*5+f,pitch_basis='explicit_assumption')
           for s in range(6,0,-1) for f in range(1,4)]
    result=dict(schema_version='fusion_cell.v1',data_kind='synthetic_contract_not_real_performance',
        grid=dict(identity,cells=cells,geometry_status='usable_for_hypotheses',
            geometry_source='synthetic',anchor_status='assumed',spacing_source='synthetic',numbering_status='assumed'),
        video=dict(identity,score_type='unconditional_location_mass',fingers=[
            dict(finger_id='index',quality_status='usable',cell_masses={'s6f1':.6,'s5f2':.2},outside_mass=.1,unresolved_mass=0,unassigned_mass=.1),
            dict(finger_id='middle',quality_status='usable',cell_masses={'s6f2':.55,'s4f3':.25},outside_mass=.1,unresolved_mass=0,unassigned_mass=.1)]),
        audio=dict(identity,score_type='normalized_compatibility_0_1',quality_status='usable',
            source_identity='accompaniment',derived_from_separation=True,guitar_isolation_verified=False,
            cells={c['cell_id']:dict(score=.1 if c['cell_id'] in ('s6f1','s6f2') else .9,evidence_ids=['shared_peak'] if c['cell_id'] in ('s5f2','s4f3') else [c['cell_id']+':peak']) for c in cells}))
    for finger in result['video']['fingers']:
        lineage={k:identity[k] for k in ('source_id','frame_index','frame_pts_s','frame_pixel_sha256')}
        lineage.update(observation_id='synthetic_hand',branch='synthetic',raw_hand_sha256='synthetic_21_point_hand')
        finger['observation_lineage']=lineage
        finger['semantic_validity']=dict(status='valid',finger_id=finger['finger_id'],lineage=copy.deepcopy(lineage),reasons=['synthetic_identity_permission_not_human_review'])
    return result


class FusionTests(unittest.TestCase):
    def test_weights_and_preservation(self):
        f=fixture(); original=copy.deepcopy(f);out=fusion(f)
        self.assertEqual(f,original)
        self.assertEqual(set(out['experiments']),{'60_40','80_20','40_60','video_only','audio_only'})
        a=out['experiments']['60_40']['finger_rankings'][0]['candidates']
        row=next(r for r in a if r['cell_id']=='s6f1')
        self.assertAlmostEqual(row['score'],.6*.6+.4*.1)
        self.assertEqual(out['confirmed_guitar_chords'],[])

    def test_identity_rejection(self):
        for key,value in [('source_id','other'),('grid_version','other'),('frame_pts_s',.6),('M',[]),('canvas_size',[5,5]),('frame_pixel_sha256','other')]:
            f=fixture(); f['audio'][key]=value
            with self.assertRaises(ValueError): fusion(f)

    def test_missing_not_zero_or_renormalized(self):
        f=fixture(); del f['audio']['cells']['s6f1'];out=fusion(f)
        row=next(r for r in out['experiments']['60_40']['finger_rankings'][0]['candidates'] if r['cell_id']=='s6f1')
        self.assertIsNone(row['score']);self.assertIsNone(row['audio_score'])
        row=next(r for r in out['experiments']['video_only']['finger_rankings'][0]['candidates'] if r['cell_id']=='s6f1')
        self.assertEqual(row['score'],.6)

    def test_geometry_and_both_bad_abstain(self):
        f=fixture();f['grid']['geometry_status']='withheld'
        out=fusion(f)
        self.assertTrue(all(not e['combinations'] for e in out['experiments'].values()))
        f=fixture();f['audio']['quality_status']='poor'
        for finger in f['video']['fingers']:finger['quality_status']='withheld'
        self.assertTrue(all(not e['combinations'] for e in fusion(f)['experiments'].values()))

    def test_string_conflicts_and_no_finger_reuse(self):
        out=fusion(fixture())
        for e in out['experiments'].values():
            for c in e['combinations']:
                self.assertEqual(len({a['finger_id'] for a in c['assignments']}),len(c['assignments']))
                self.assertEqual(len({a['cell_id'].split('f')[0] for a in c['assignments']}),len(c['assignments']))
        self.assertEqual(out['experiments']['audio_only']['combinations'],[])

    def test_shared_audio_not_double_counted(self):
        f=fixture()
        for finger,cid in zip(f['video']['fingers'],('s5f2','s4f3')):
            finger['cell_masses']={cid:.8}
        combo=fusion(f)['experiments']['60_40']['combinations'][0]
        self.assertEqual(len(combo['assignments']),2)
        self.assertAlmostEqual(combo['audio_component'],.4*.9/2)

    def test_mass_scale_and_unknown_cells(self):
        for mass in (float('nan'),1.2,-.1):
            f=fixture();f['video']['fingers'][0]['cell_masses']['s6f1']=mass
            with self.assertRaises(ValueError):fusion(f)
        f=fixture();f['video']['score_type']='calibrated_pressure_probability'
        with self.assertRaises(ValueError):fusion(f)

    def test_no_audio_chord_rescoring(self):
        f=fixture();a=fusion(f)['experiments']
        f['accompaniment_harmony']={'concert_symbol':'C','score':1.0}
        self.assertEqual(fusion(f)['experiments'],a)

    def test_real_grid_pending_is_not_synthetic_score(self):
        from harmony_input_adapter import fusion_pending_from_grid
        f=fusion_pending_from_grid('dataset/virtual_string_grid/runs/clip_003_012_20261103_v1/clip003012_f000124_candidate_anchor.json',start_s=5.05,end_s=5.35)
        out=fusion(f)
        self.assertEqual(out['data_kind'],'actual_grid_missing_upstream_scores')
        self.assertTrue(all(e['status']=='geometry_withheld' and not e['combinations'] for e in out['experiments'].values()))

    def test_withheld_hand_not_rescued_by_audio(self):
        f=fixture()
        for finger in f['video']['fingers']:finger['quality_status']='withheld_crop_conflict'
        out=fusion(f)
        self.assertFalse(out['experiments']['60_40']['combinations'])
        self.assertFalse(out['experiments']['audio_only']['combinations'])
        self.assertIsNotNone(out['experiments']['audio_only']['finger_rankings'][0]['candidates'][0]['score'])

    def test_actual_owner_adapter_v2_and_grid_revision(self):
        from harmony_input_adapter import fusion_from_owner_records
        record=json.loads(Path('dataset/cell_audio_fusion/runs/actual_abc_20261103_v2/clip003012_f000124_candidate_anchor/input.json').read_text())
        gp=record['provenance']['grid_path'];hp=record['provenance']['hand_path']
        result=fusion_from_owner_records(gp,hp,record['audio']['raw_owner_record'])
        self.assertTrue(result['provenance']['grid_metadata_revision']['cells_and_transform_unchanged'])
        self.assertEqual(len(result['video']['fingers']),5)
        self.assertTrue(all(e['status']=='geometry_withheld' for e in fusion(result)['experiments'].values()))
        with tempfile.TemporaryDirectory() as tmp:
            wrong=json.loads(Path(gp).read_text());wrong['cells'][0]['polygon'][0][0]+=.5
            path=Path(tmp)/'bad_grid.json';path.write_text(json.dumps(wrong))
            with self.assertRaises(ValueError):fusion_from_owner_records(path,hp,record['audio']['raw_owner_record'])

    def test_synthetic_audio_grid_cannot_attach_to_actual_hand(self):
        from harmony_input_adapter import fusion_from_owner_records
        c=json.loads(Path('dataset/audio_analysis/runs/audio_cell_compatibility_20261103_v1/accompaniment_5.05_5.35.json').read_text())
        with self.assertRaises(ValueError):
            fusion_from_owner_records('dataset/virtual_string_grid/runs/clip_003_012_20261103_v2/clip003012_f000124_candidate_anchor.json',
                'dataset/hand_cell_distribution/runs/virtual_cells_20261103_v1/clip003012_f000124_candidate_anchor_hand_cells.json',c)

    def test_semantic_invalid_unknown_cannot_be_rescued(self):
        for status in ('invalid','unknown'):
            f=fixture()
            for finger in f['video']['fingers']:
                finger['semantic_validity']['status']=status
                finger['cell_masses']={cid:0 for cid in finger['cell_masses']}
                finger['cell_masses'][next(iter(finger['cell_masses']))]=.99
                finger.update(outside_mass=.01,unassigned_mass=0)
            for record in f['audio']['cells'].values():record['score']=1.
            out=fusion(f)
            for experiment in out['experiments'].values():
                self.assertEqual(experiment['combinations'],[])
                for finger in experiment['finger_rankings']:
                    self.assertEqual(finger['semantic_status'],status)
                    self.assertTrue(all(r['score'] is None and r['status']=='semantic_'+status for r in finger['candidates']))

    def test_semantic_missing_and_zero_are_distinct(self):
        f=fixture()
        del f['video']['fingers'][0]['semantic_validity']
        f['video']['fingers'][1]['cell_masses']={'s4f3':0.}
        f['audio']['cells']['s4f3']['score']=0.
        f['audio']['cells']['s4f3']['evaluation_status']='no_matching_candidate_evidence'
        out=fusion(f)['experiments']['60_40']
        self.assertEqual(out['finger_rankings'][0]['candidates'][0]['status'],'semantic_unknown')
        row=next(r for r in out['finger_rankings'][1]['candidates'] if r['cell_id']=='s4f3')
        self.assertEqual(row['score'],0.)
        f['audio']['cells']['s4f3']['score']=None
        row=next(r for r in fusion(f)['experiments']['60_40']['finger_rankings'][1]['candidates'] if r['cell_id']=='s4f3')
        self.assertIsNone(row['score']);self.assertEqual(row['status'],'missing_or_withheld_modality')

    def test_semantic_exact_scope_and_mixed_hand_lineage(self):
        from harmony_input_adapter import apply_fusion_semantic_policy
        f=fixture();target=copy.deepcopy(f['video']['fingers'][0]['observation_lineage'])
        policy=dict(schema_version='fusion_semantic_policy.v1',policy_id='synthetic_review',lineage=target,
            fingers={'index':dict(status='invalid',reasons=['synthetic_chain_error'])})
        out=apply_fusion_semantic_policy(f,policy)
        self.assertEqual(fusion(out)['experiments']['60_40']['finger_rankings'][0]['semantic_status'],'invalid')
        for key in ('observation_id','branch','raw_hand_sha256','frame_index','frame_pixel_sha256','frame_pts_s'):
            altered=copy.deepcopy(policy);altered['lineage'][key]='other'
            self.assertEqual(apply_fusion_semantic_policy(f,altered)['semantic_policy_application']['matched_fingers'],[])
        f['video']['fingers'][0]['observation_lineage']['raw_hand_sha256']='mixed_per_finger_hand'
        self.assertEqual(fusion(f)['experiments']['60_40']['finger_rankings'][0]['semantic_status'],'unknown')

    def test_semantic_error_removes_chord_notes_not_just_score(self):
        f=fixture();base=f['video']['fingers'][0];f['video']['fingers']=[]
        for name,cid,midi in zip(('middle','ring','pinky'),('s6f1','s5f2','s4f3'),(60,64,67)):
            finger=copy.deepcopy(base);finger.update(finger_id=name,cell_masses={cid:.8})
            finger['semantic_validity']['finger_id']=name
            f['video']['fingers'].append(finger)
            next(c for c in f['grid']['cells'] if c['cell_id']==cid)['possible_midi']=midi
        self.assertTrue(fusion(f)['experiments']['video_only']['combinations'][0]['fingering_chord_hypotheses'])
        for finger in f['video']['fingers']:finger['semantic_validity']['status']='invalid'
        self.assertTrue(all(not e['combinations'] for e in fusion(f)['experiments'].values()))

    def test_owner_false_permission_is_hard_gate(self):
        f=fixture()
        for finger in f['video']['fingers']:finger['anatomical_fingering_evidence_allowed']=False
        self.assertTrue(all(not e['combinations'] for e in fusion(f)['experiments'].values()))
        f=fixture()
        for finger in f['video']['fingers']:
            finger['cell_semantic_permissions']={c['cell_id']:False for c in f['grid']['cells']}
        self.assertTrue(all(not e['combinations'] for e in fusion(f)['experiments'].values()))

    def test_actual_frame210_owner_semantics_and_tamper_rejection(self):
        from harmony_input_adapter import fusion_owner_semantic
        p=Path('dataset/hand_cell_distribution/runs/anatomical_validity_20261104_v2/clip003012_f000210_candidate_anchor_hand_cells.json')
        hand=json.loads(p.read_bytes());states={}
        for o in hand['observations']:
            converted=fusion_owner_semantic(o,hand)
            states[o['observation']['finger']]=converted['semantic_validity']['status']
            self.assertFalse(converted['anatomical_fingering_evidence_allowed'])
        self.assertEqual(states,dict(thumb='unknown',index='unknown',middle='invalid',ring='invalid',pinky='invalid'))
        for key in ('pixel','frame_pixel_sha256'):
            bad=copy.deepcopy(hand['observations'][2]);bad['observation'][key]='tampered'
            with self.assertRaises(ValueError):fusion_owner_semantic(bad,hand)
        bad=copy.deepcopy(hand['observations'][2]);bad['anatomical_validity']['lineage']['view_id']=1
        with self.assertRaises(ValueError):fusion_owner_semantic(bad,hand)

    def test_actual_thirty_fixture_fusion_regression(self):
        from cell_fusion_semantic_review import replay_actual
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'actual'
            replay_actual('dataset/hand_cell_distribution/runs/anatomical_validity_20261104_v2',output)
            records=json.loads((output/'single_fixture_replay.json').read_bytes())
            self.assertEqual(len(records),30)
            self.assertEqual(sum(r['semantic_status']=='invalid' for r in records),18)
            self.assertEqual(sum(r['semantic_status']=='unknown' for r in records),12)
            self.assertTrue(all(r['rankable_cells']==r['combinations']==0 for r in records))


if __name__=='__main__':unittest.main()
