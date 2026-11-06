import hashlib
import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np
from fretboard_frame_identity import make_frame_identity,attach_frame_identity,assert_same_frame
from review_fretboard_clip import make_board,REFERENCE_CORNERS


class FrameIdentityTests(unittest.TestCase):
    def test_separate_hashes_and_legacy_case(self):
        frame=np.arange(600,dtype=np.uint8).reshape(10,20,3)
        with tempfile.TemporaryDirectory() as t:
            image=Path(t)/'frame.png';cv2.imwrite(str(image),frame)
            identity=make_frame_identity('a'*64,71,3.,frame,image,'new_case')
            self.assertNotEqual(identity['image_file_sha256'],identity['frame_pixel_sha256'])
            self.assertEqual(identity['frame_pixel_sha256'],hashlib.sha256(frame.tobytes()).hexdigest())
            result=attach_frame_identity(dict(source_id='case_0005.00',image_sha256=identity['frame_pixel_sha256']),identity)
            self.assertEqual(result['source_id'],'a'*64)
            self.assertEqual(result['case_id'],'case_0005.00')
            self.assertTrue(assert_same_frame(result,identity))
            with self.assertRaises(ValueError):attach_frame_identity(dict(source_id='b'*64),identity)
            with self.assertRaises(ValueError):attach_frame_identity(dict(image_sha256='f'*64),identity)

    def test_pts_rounding_tolerance_is_not_frame_shift(self):
        base=dict(source_id='a'*64,frame_index=81,frame_pts_s=3.416667,frame_pixel_sha256='b'*64)
        self.assertTrue(assert_same_frame(base,dict(base,frame_pts_s=82/24)))
        with self.assertRaises(ValueError):assert_same_frame(base,dict(base,frame_pts_s=3.375))
        with self.assertRaises(ValueError):assert_same_frame(base,dict(base,frame_index=82))
        with self.assertRaises(ValueError):assert_same_frame(base,dict(base,frame_pixel_sha256='c'*64))

    def test_capo_is_not_nut_or_first_wire(self):
        identity=dict(source_id='a'*64,frame_index=120,frame_pts_s=121/24,case_id='test')
        board=make_board(identity,np.eye(3),dict(status='valid'),Path('frame.png'))
        self.assertIsNone(board['capo']['value'])
        self.assertEqual(board['capo']['physical_fret_candidate'],1)
        self.assertFalse(board['capo']['is_nut'])
        self.assertFalse(board['geometry_validity']['contact_fret_decision_allowed'])
        self.assertEqual(board['geometry_validity']['status'],'suspect')
        first=next(f for f in board['frets'] if f['fret_num']==1)
        self.assertEqual(first['reference_endpoints'][0][0],1057)
        self.assertEqual(first['legacy_fret_num'],2)
        self.assertEqual(first['relative_fret_candidate'],0)
        self.assertIsNone(first['relative_fret'])
        self.assertIsNone(first['confirmed_physical_fret_num'])
        self.assertEqual(first['source'],'manual_estimate')


if __name__=='__main__':unittest.main()
