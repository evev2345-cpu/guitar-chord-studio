import copy
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

import cv2
import numpy as np

from fretting_hand_skeleton import select_whole_hand, hand_bounding_crop, FrettingHandSkeletonDetector
from improve_hand_skeleton import prepare_image, restore_hand


class SkeletonImprovementTests(unittest.TestCase):
    def test_adaptive_crop_stays_inside_image_at_edges(self):
        for center in [(20,20),(1260,700),(640,360)]:
            p=np.tile(center,(21,1)).astype(float)
            crop=hand_bounding_crop(p,(720,1280,3))
            x0,y0,x1,y1=crop
            self.assertTrue(0<=x0<x1<=1280 and 0<=y0<y1<=720)
            self.assertEqual(x1-x0,220)
            self.assertTrue(x0<=center[0]<=x1 and y0<=center[1]<=y1)
        with self.assertRaises(ValueError):hand_bounding_crop([[0,0]],(720,1280,3))
        with self.assertRaises(ValueError):hand_bounding_crop(np.full((21,2),np.nan),(720,1280,3))

    def test_adaptive_missing_proposal_does_not_invent_hand(self):
        detector=object.__new__(FrettingHandSkeletonDetector)
        detector.detect=lambda image,crop:dict(candidates=[],selection=select_whole_hand([]))
        result=detector.detect_adaptive(np.zeros((720,1280,3),np.uint8),(650,100,1180,460))
        self.assertIsNone(result['selection']['selected'])
        self.assertIsNone(result['adaptive_crop'])
        self.assertEqual(result['status'],'no_hand_proposal')

    def test_rotation_and_mirror_inverse_restore_source_pixels(self):
        raw=np.zeros((100,150,3),np.uint8);crop=(20,10,110,90)
        source=np.array([[25.,15.],[80.,60.],[100.,80.]])
        for turns in range(4):
            for mirror in [False,True]:
                image,M=prepare_image(raw,crop,turns,mirror)
                transformed=cv2.perspectiveTransform(source[:,None],M)[:,0]
                h,w=image.shape[:2]
                hand=[NS(x=x/w,y=y/h) for x,y in transformed]
                np.testing.assert_allclose(restore_hand(hand,image.shape,M),source,atol=1e-10)

    def test_whole_medoid_never_combines_points_or_claims_validity(self):
        base=np.c_[np.arange(21),np.arange(21)*2.]
        candidates=[dict(candidate_id=str(i),hands=[dict(pixel_landmarks=(base+delta).tolist())])
                    for i,delta in enumerate([0.,1.,2.,100.])]
        original=copy.deepcopy(candidates)
        r=select_whole_hand(candidates)
        self.assertIn(r['selected'],original)
        self.assertEqual(candidates,original)
        self.assertFalse(r['per_finger_mixing'])
        self.assertFalse(r['coordinates_manually_adjusted'])
        self.assertEqual(r['anatomical_validity'],'unknown')
        self.assertEqual(r['contact'],'unknown')

    def test_missing_or_ambiguous_observations_not_forced(self):
        self.assertIsNone(select_whole_hand([{'hands':[]}])['selected'])
        self.assertIsNone(select_whole_hand([{'hands':[{},{}]}])['selected'])
        with self.assertRaises(ValueError):
            select_whole_hand([{'hands':[{'pixel_landmarks':[[0,0]]}]}])

    def test_frame210_pose_specific_separation_snapshot(self):
        # This is a fixed pose regression, NOT a general finger identity rule.
        p=Path(__file__).parent/'dataset/hand_analysis/runs/skeleton_improvement_20261104_focused_v1/result.json'
        d=json.loads(p.read_text())
        f=next(f for f in d['frames'] if f['frame_index']==210)
        s=f['inference']['selection']
        points=np.array(s['selected']['hands'][0]['pixel_landmarks'])
        self.assertGreater(points[16,1]-points[12,1],30)
        self.assertGreater(points[20,1]-points[16,1],40)
        self.assertFalse(f['confirmed_anatomical_validity'])
        self.assertEqual(s['selected']['hands'][0]['points_from_one_inference'],True)


if __name__=='__main__':unittest.main()
