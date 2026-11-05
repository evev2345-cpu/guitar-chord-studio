import copy
import json
from pathlib import Path
import unittest
from hand_anatomical_validity import *

RUN=Path('dataset/hand_cell_distribution/runs/anatomical_validity_20261104_v2')
class AnatomicalValidityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binding=json.loads((RUN/'review_binding.json').read_text())
        cls.lineage=json.loads((RUN/'medoid_lineage.json').read_text())
        cls.frame=next(f for f in json.loads(Path('dataset/integration_review/runs/robust_candidates_20261103_v2/result.json').read_text())['frames'] if f['frame_index']==210)
    def test_reviewed_groups_invalid(self):
        for i in range(9,21):
            v=anatomical_validity(self.binding,self.lineage['12'],[i],self.binding)
            self.assertEqual(v['status'],'invalid')
    def test_thumb_index_qualitative_not_precision_truth(self):
        for i in [4,5,6,7,8]:
            v=anatomical_validity(self.binding,self.lineage['8'],[i],self.binding)
            self.assertEqual(v['status'],'unknown');self.assertFalse(v['anatomical_fingering_evidence_allowed'])
    def test_other_crop_unknown(self):
        ln=copy.deepcopy(self.lineage['12']);ln['view_id']=1
        self.assertEqual(anatomical_validity(self.binding,ln,[12],self.binding)['status'],'unknown')
    def test_other_frame_and_source_do_not_inherit(self):
        for key,value in [('frame_index',211),('frame_pts_s',9),('source_id','other'),('frame_pixel_sha256','other')]:
            identity=dict(self.binding);identity[key]=value
            self.assertFalse(anatomical_validity(identity,self.lineage['12'],[12],self.binding)['human_review_applied'])
    def test_altered_skeleton_unknown(self):
        ln=copy.deepcopy(self.lineage['12']);ln['skeleton_sha256']='changed'
        self.assertEqual(anatomical_validity(self.binding,ln,[12],self.binding)['status'],'unknown')
    def test_medoid_filtered_views_and_coordinate_match(self):
        frame=copy.deepcopy(self.frame);frame['views'].insert(0,dict(view_id=99,hands=[]))
        self.assertEqual(resolve_medoid(frame,12)['view_id'],0)
        frame['tip_decisions']['12']['selected_pixel']=[0,0]
        with self.assertRaises(ValueError):resolve_medoid(frame,12)
    def test_high_mass_does_not_override_invalid(self):
        v=anatomical_validity(self.binding,self.lineage['12'],[12],self.binding)
        d=dict(decision='spatial_candidate_only',cells=[dict(position_mass=1.)],reasons=[])
        out=apply_validity(d,v)
        self.assertEqual(out['decision'],'abstain');self.assertEqual(out['cells'][0]['position_mass'],1.)
        self.assertFalse(out['cells'][0]['anatomical_fingering_evidence_allowed']);self.assertNotIn('anatomical_validity',d)
    def test_actual_six_grids_raw_preserved(self):
        manifest=json.loads((RUN/'manifest.json').read_text());self.assertEqual(len(manifest['records']),6)
        for record in manifest['records']:
            new=json.loads(Path(record['path']).read_text());old=json.loads(Path(new['upstream_result_path']).read_text())
            self.assertEqual(record['invalid'],3)
            for a,b in zip(old['observations'],new['observations']):
                self.assertEqual(a['observation'],b['observation'])
                for k in ('top1','top2','top3','unassigned_mass','mass_total'):self.assertEqual(a[k],b[k])
                self.assertEqual(b['anatomical_validity']['status'],'invalid' if a['observation']['landmark_index'] in (12,16,20) else 'unknown')
    def test_baseline_matches_saved_roi(self):
        raw=next(r for r in map(json.loads,Path('dataset/hand_analysis/runs/clip_003_012_20261103_v1/observations.jsonl').read_text().splitlines()) if r['frame_index']==210)
        self.assertEqual([p['pixel'] for p in raw['roi_observations'][0]['landmarks']],self.binding['raw_points'])
if __name__=='__main__':unittest.main()
