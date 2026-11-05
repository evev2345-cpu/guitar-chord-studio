import json
import unittest
from pathlib import Path
from fret_geometry import resolve_frets, build_cells


def wire(n, x):
    return dict(fret_num=n, p1=[200,x], p2=[700,x])


class GeometryTests(unittest.TestCase):
    def test_multiple_gaps_and_missing_numbers(self):
        result = resolve_frets({'frets': [wire(2,100),
            dict(fret_num=3, occluded=True), wire(5,400), wire(8,700)]})
        self.assertEqual([r['fret_num'] for r in result], list(range(2,9)))
        self.assertEqual(result[1]['anchors'], [2,5])
        self.assertEqual(result[4]['anchors'], [5,8])
        self.assertEqual([b['fret_num'] for a,b in build_cells(result)], list(range(3,9)))
        widths = [result[i+1]['xt']-result[i]['xt'] for i in range(3)]
        self.assertAlmostEqual(widths[1]/widths[0], 2**(-1/12))
        self.assertTrue(result[1]['occluded'])
        self.assertFalse(result[2]['occluded'])

    def test_unbounded_not_extrapolated(self):
        result = resolve_frets({'frets': [dict(fret_num=0, occluded=True),
            wire(1,100), wire(2,200), dict(fret_num=3, occluded=True)]})
        self.assertNotIn('xt', result[0])
        self.assertNotIn('xt', result[-1])
        self.assertEqual(len(build_cells(result)), 1)

    def test_bad_responses(self):
        for frets in ([wire(1,100),wire(1,200)], [wire(1,300),wire(2,200)],
                      [dict(fret_num=1,p1=[200,100],p2=[200,100])],
                      [dict(fret_num=1,p1=[-1,100],p2=[700,100])]):
            with self.subTest(frets=frets), self.assertRaises(ValueError):
                resolve_frets({'frets':frets})

    def test_saved_fender_response(self):
        path = Path(__file__).parent/'sample_images/perfect_certain_frets.json'
        result = resolve_frets(json.loads(path.read_text(encoding='utf-8')))
        self.assertEqual(len(result),18)
        self.assertEqual([r['fret_num'] for r in result if r['interpolated']], [6,7,8])
        self.assertAlmostEqual(result[6]['xt'],435.1,delta=0.1)

class BoundaryTests(unittest.TestCase):
    def test_recover_occluded_ends_without_renumbering(self):
        positions=lambda n:1000*(1-2**(-n/12))/(1-2**(-20/12))
        frets=[wire(n,positions(n)) for n in range(1,17)]
        frets += [dict(fret_num=n,occluded=True) for n in range(17,21)]
        result=resolve_frets({'frets':frets,'last_fret_num':20},board_boundaries=True)
        self.assertEqual(result[0]['source'],'boundary_estimated')
        self.assertEqual(result[-1]['fret_num'],20)
        self.assertEqual(result[-1]['source'],'boundary_estimated')
        self.assertEqual(result[-1]['xt'],800)
        self.assertTrue(result[-2]['interpolated'])

    def test_conflicting_terminal_number_stays_unknown(self):
        positions=lambda n:1000*(1-2**(-n/12))/(1-2**(-20/12))
        frets=[wire(n,positions(n)) for n in range(1,17)]
        frets.append(dict(fret_num=20,occluded=True))
        result=resolve_frets({'frets':frets,'last_fret_num':21},board_boundaries=True)
        self.assertNotIn('xt',result[-1])

    def test_clip_small_but_reject_large_extrapolation(self):
        slight=dict(fret_num=22,p1=[80,996.3],p2=[480,998.8])
        result=resolve_frets({'frets':[slight]})[0]
        self.assertEqual(result['xb'],800)
        self.assertEqual(result['geometry_adjustment'],'boundary_clip')
        self.assertAlmostEqual(result['original_endpoints'][1],801.64)
        large=dict(fret_num=22,p1=[80,980],p2=[480,999])
        result=resolve_frets({'frets':[large]})[0]
        self.assertEqual(result['source'],'rejected')
        self.assertNotIn('xt',result)


class CropMappingTests(unittest.TestCase):
    def test_crop_coordinate_roundtrip(self):
        import numpy as np
        from two_stage_fret_pipeline import prepare_candidate_crop, map_crop_corners
        image = np.zeros((100,200,3),dtype=np.uint8)
        crop,bounds = prepare_candidate_crop(image,[200,200,800,800],margin=0)
        self.assertEqual(bounds,(40,20,160,80))
        self.assertEqual(max(crop.shape[:2]),1400)
        response = dict(nut_top=[0,0],body_top=[0,1000],
                        body_bottom=[1000,1000],nut_bottom=[1000,0])
        self.assertEqual(map_crop_corners(response,bounds),
                         [(40,20),(160,20),(160,80),(40,80)])

    def test_invalid_bbox(self):
        import numpy as np
        from two_stage_fret_pipeline import prepare_candidate_crop
        with self.assertRaises(ValueError):
            prepare_candidate_crop(np.zeros((100,100,3),dtype=np.uint8),[800,0,200,1000])


if __name__ == '__main__':
    unittest.main()
