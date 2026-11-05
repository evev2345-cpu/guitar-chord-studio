import copy
import json
from pathlib import Path
import unittest
import numpy as np
from hand_cell_distribution import cell_distribution,adapt_grid,segment_distribution
from run_hand_cell_distribution import observations_for_frame
from virtual_string_grid import assert_grid_compatible


def synthetic_grid():
    cells=[]
    # Explicit adapter fixture, not a second virtual-string generator.
    for cell_id,s,f,p in [('a',6,1,[[0,0],[50,0],[50,50],[0,50]]),('b',5,1,[[0,50],[50,50],[50,100],[0,100]]),
                           ('c',6,2,[[50,0],[100,0],[100,50],[50,50]]),('d',5,2,[[50,50],[100,50],[100,100],[50,100]])]:
        cells.append(dict(cell_id=cell_id,virtual_string_num=s,physical_fret_candidate=f,polygon=p,estimated=True,is_virtual=True))
    return dict(source_id='synthetic',frame_index=0,frame_pts_s=0.,frame_pixel_sha256='synthetic_pixels',
        grid_id='synthetic_partial_two_string_fixture',grid_version='synthetic_contract.v1',canvas_size=[100,100],
        M=np.eye(3).tolist(),M_inv=np.eye(3).tolist(),cells=cells,is_virtual=True,synthetic=True,
        geometry_source='synthetic_test',anchor_status='assumed',spacing_source='explicit_test_polygons',
        numbering_status='synthetic_unverified',assumptions={},geometry_status='unknown')


class CellDistributionTests(unittest.TestCase):
    def setUp(self):
        self.grid=synthetic_grid()
        self.obs=dict(source_id='synthetic',frame_index=0,frame_pts_s=0.,frame_pixel_sha256='synthetic_pixels',pixel=[50,50],
                      evidence=dict(evidence_grade='abstain_full_crop_disagreement'))

    def test_four_cells_mass_and_no_overconfidence_override(self):
        result=cell_distribution(self.grid,self.obs,samples=65536)
        self.assertAlmostEqual(result['mass_total'],1.,places=12)
        for cell in result['cells']:self.assertAlmostEqual(cell['position_mass'],.25,delta=.01)
        self.assertEqual(len(result['top3']),3)
        self.assertAlmostEqual(result['top3_total_mass']+result['other_cells_mass']+result['unassigned_mass'],1.)
        self.assertEqual(result['decision'],'abstain')
        center=dict(self.obs,pixel=[25,25]);r=cell_distribution(self.grid,center)
        self.assertEqual(r['top1'][0]['position_mass'],1.)
        self.assertIn('abstain_full_crop_disagreement',r['reasons'])
        valid_grid=dict(self.grid,geometry_status='valid',precise_geometry_verified=True,contact_fret_decision_allowed=True)
        self.assertEqual(cell_distribution(valid_grid,center)['decision'],'abstain')

    def test_outside_and_unresolved_mass_not_renormalized(self):
        grid=copy.deepcopy(self.grid);grid['cells']=[]
        result=cell_distribution(grid,dict(self.obs,pixel=[0,50]),samples=65536)
        self.assertAlmostEqual(result['outside_board_mass'],.5,delta=.01)
        self.assertAlmostEqual(result['unresolved_geometry_mass'],.5,delta=.01)
        self.assertEqual(result['unassigned_mass'],1.)

    def test_mismatched_frame_grid_and_overlap_rejected(self):
        for key,value in [('source_id','wrong'),('frame_index',1),('frame_pts_s',1.),('frame_pixel_sha256','wrong')]:
            with self.assertRaises(ValueError):adapt_grid(self.grid,dict(self.obs,**{key:value}))
        grid=copy.deepcopy(self.grid);grid['cells'].append(dict(grid['cells'][0],cell_id='overlap'))
        with self.assertRaises(ValueError):adapt_grid(grid,self.obs)
        with self.assertRaises(ValueError):adapt_grid(self.grid,dict(self.obs,coordinate_system='flat_pixels'))

    def test_segment_is_separate_normalized_model(self):
        result=segment_distribution(self.grid,self.obs,[[25,20],[25,80]])
        self.assertAlmostEqual(result['mass_total'],1.)
        self.assertEqual(result['model'],'uniform_segment_with_isotropic_gaussian_tube')
        self.assertEqual(result['contact'],'unknown')
        self.assertGreater(result['top2'][0]['position_mass'],.4)

    def test_roi_only_stays_unconfirmed_and_inputs_preserved(self):
        obs=copy.deepcopy(self.obs);grid=copy.deepcopy(self.grid)
        obs['evidence']['evidence_grade']='multi_crop_supported_unconfirmed_candidate'
        result=cell_distribution(grid,obs)
        self.assertIn('roi_only_unconfirmed',result['reasons'])
        self.assertEqual(grid,self.grid)
        self.assertEqual(obs['pixel'],[50,50])

    def test_medoid_index_maps_valid_views_not_missing_view(self):
        joints=[[float(i),float(i)]for i in range(21)]
        robust=dict(source_id='s',frame_index=0,frame_pts_s=0.,frame_pixel_sha256='p',
            views=[dict(view_id=0,hands=[]),dict(view_id=1,hands=[joints])],
            tip_decisions={str(i):dict(selected_pixel=joints[i],medoid_view_index=0,evidence_grade='abstain_crop_disagreement')for i in [4,8,12,16,20]})
        _,segments=observations_for_frame(dict(selected_hand_index=None),robust)
        self.assertEqual(len(segments),3)
        self.assertEqual(segments[0]['view_id'],1)
        self.assertEqual(segments[2]['endpoints'][1],joints[8])

    def test_real_grid_replay_and_strict_model_identity(self):
        root=Path('dataset/hand_cell_distribution/runs/virtual_cells_20261103_v4')
        manifest=json.loads((root/'manifest.json').read_text())
        self.assertEqual(len(manifest['records']),66)
        high=0
        for record in manifest['records']:
            data=json.loads(Path(record['result_path']).read_text())
            grid=json.loads(Path(data['grid_path']).read_text())
            self.assertFalse(data['synthetic'])
            for obs in data['observations']:
                assert_grid_compatible(grid,obs)
                self.assertAlmostEqual(obs['mass_total'],1.,places=12)
                self.assertAlmostEqual(obs['top3_total_mass']+obs['other_cells_mass']+obs['unassigned_mass'],1.,places=12)
                self.assertEqual(obs['decision'],'abstain')
                high+=bool(obs['top1']and obs['top1'][0]['position_mass']>.9)
            wrong=dict(data['observations'][0],grid_id='different_scenario')
            with self.assertRaises(ValueError):assert_grid_compatible(grid,wrong)
        self.assertGreater(high,0)


if __name__=='__main__':unittest.main()
