import unittest
import cv2
import numpy as np
from string_detector import detect_strings,query_string_fret


def synthetic(dark=False, missing=None):
    image=np.full((150,800,3),190 if dark else 45,np.uint8)
    for i,y in enumerate([16,39,62,85,108,131]):
        if i==missing:continue
        color=(20,20,20) if dark else (220,220,220)
        cv2.line(image,(0,y-3),(799,y+3),color,2,cv2.LINE_AA)
    # vertical frets and hand-sized occlusion must not become strings
    for x in range(60,800,55):cv2.line(image,(x,0),(x,149),(150,150,150),2)
    image[0:150,190:310]=[100,120,170]
    return image


class StringTests(unittest.TestCase):
    def test_bright_and_dark_lines(self):
        for dark in (False,True):
            with self.subTest(dark=dark):
                result=detect_strings(synthetic(dark))
                self.assertEqual(len(result['strings']),6)
                self.assertGreaterEqual(result['observed_count'],5)
                for s,y in zip(result['strings'],[16,39,62,85,108,131]):
                    self.assertAlmostEqual((s['y_left']+s['y_right'])/2,y,delta=3)
                self.assertTrue(all(s['string_num'] is None for s in result['strings']))
                self.assertEqual([s['screen_rank'] for s in result['strings']],[1,2,3,4,5,6])

    def test_missing_line_is_not_synthesized(self):
        result=detect_strings(synthetic(missing=2),physical_order='low_e_top')
        self.assertEqual(len(result['strings']),5)
        self.assertEqual(result['estimated_count'],0)
        self.assertTrue(all(s['string_num'] is None for s in result['strings']))
        self.assertEqual(len(result['unresolved']),6)

    def test_blank_is_not_six_observations(self):
        result=detect_strings(np.full((150,800,3),100,np.uint8))
        self.assertEqual(result['status'],'insufficient_evidence')
        self.assertEqual(result['observed_count'],0)
        self.assertIsNone(query_string_fret(50,30,result,[]))

    def test_query_and_estimate_guard(self):
        result=detect_strings(synthetic(),physical_order="low_e_top")
        frets=[dict(fret_num=n,m=0,b=x,xt=x,xb=x) for n,x in enumerate([0,100,200])]
        s=result['strings'][2]
        point=s['m']*150+s['b']
        answer=query_string_fret(150,point,result,frets)
        self.assertEqual(answer['string'],4)
        self.assertEqual(answer['fret'],2)
        s['source']='estimated'
        self.assertIsNone(query_string_fret(150,point,result,frets))
        self.assertIsNone(query_string_fret(150,-30,result,frets))
        self.assertIsNone(query_string_fret(150,151,result,frets))

    def test_high_resolution_coordinate_conversion(self):
        from unittest.mock import patch
        from string_geometry import analyze_saved_board
        line=dict(m=.1,b=50.,observed_intervals=[[100.,900.]],string_num=None,source='observed')
        board=dict(corners=[[0,0],[600,0],[600,200],[0,200]],frets=[],canvas_size=[800,150])
        with patch('string_geometry.detect_strings',return_value={'strings':[line]}):
            r,_,_,_,_=analyze_saved_board(np.zeros((200,600,3),np.uint8),board,'fixture')
        self.assertEqual(r['detection_canvas_size'],[1200,400])
        self.assertAlmostEqual(r['strings'][0]['m'],.05625)
        self.assertAlmostEqual(r['strings'][0]['b'],18.75)
        point=np.array([[[300.,100.]]],np.float64)
        roundtrip=cv2.perspectiveTransform(cv2.perspectiveTransform(point,np.array(r['M'])),np.array(r['M_inv']))
        np.testing.assert_allclose(roundtrip,point,atol=1e-6)
        for key in ['source_id','image_size','canvas_size','M','M_inv','frets']:
            self.assertIn(key,r)

    def test_overlay_separates_evidence_and_prediction(self):
        from string_detector import render_strings
        image=np.zeros((150,800,3),np.uint8)
        line=dict(m=0.,b=30.,source='observed',string_num=None,screen_rank=1,observed_intervals=[[100,200]])
        flat,_=render_strings(image,image,np.eye(3),{'strings':[line]})
        self.assertGreater(flat[30,150,1],150)
        self.assertLess(flat[30,150,0],60)
        self.assertGreater(flat[30,44,0],150)
        self.assertLess(flat[30,44,1],60)

    def test_reference_requires_validation(self):
        with self.assertRaises(ValueError):
            detect_strings(synthetic(),reference={'strings':[]})


if __name__=='__main__':unittest.main()
