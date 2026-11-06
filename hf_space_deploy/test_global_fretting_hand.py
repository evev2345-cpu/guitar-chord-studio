import unittest
import numpy as np
from global_fretting_hand import score_hand,rank_view,board_segment,select_hand_groups,detect_native_first


class GlobalHandTests(unittest.TestCase):
    def replay(self,candidates):
        class Replay:
            def __init__(self):self.calls=[]
            def detect(self,image,crop,quarter_turns=None):
                self.calls.append(list(quarter_turns))
                return dict(candidates=[c for c in candidates if c['quarter_turns'] in quarter_turns])
        return Replay()

    def test_strong_native_skips_rotations(self):
        detector=self.replay([dict(candidate_id='r0',quarter_turns=0,hands=[self.hand(1000,250)])])
        result=detect_native_first(detector,np.zeros((720,1280,3),np.uint8),(0,0,1280,720),
                                   [[1100,200],[400,200],[400,280],[1100,280]])
        self.assertEqual(detector.calls,[[0]])
        self.assertEqual(result['rotation_policy']['inference_count'],1)
        self.assertIsNotNone(result['group_ranking']['selection']['selected'])

    def test_actual_4812_rotates_only_after_native_abstains(self):
        import json
        from pathlib import Path
        from review_fretboard_clip import REFERENCE_CORNERS
        d=json.loads((Path(__file__).parent/'dataset/hand_analysis/runs/middle_temporal_200s_20261104_v3_nut_groups/result.json').read_text())
        frame=next(r for r in d['frames'] if r['frame_index']==4812)
        detector=self.replay(frame['result']['global_candidates'])
        r=detect_native_first(detector,np.zeros((720,1280,3),np.uint8),(0,0,1280,720),REFERENCE_CORNERS)
        self.assertEqual(detector.calls,[[0],[1,2,3]])
        self.assertIn('native_selection_abstained',r['rotation_policy']['reasons'])
        self.assertGreater(np.asarray(r['group_ranking']['selection']['selected']['hands'][0]['pixel_landmarks'])[[5,9,13,17],0].mean(),800)

    def test_low_score_native_triggers_rotations_even_when_selected(self):
        hand=self.hand(350,250,False)
        candidates=[dict(candidate_id=str(t),quarter_turns=t,hands=[hand]) for t in range(4)]
        detector=self.replay(candidates)
        r=detect_native_first(detector,np.zeros((720,1280,3),np.uint8),(0,0,1280,720),
                              [[1100,200],[400,200],[400,280],[1100,280]])
        self.assertEqual(detector.calls,[[0],[1,2,3]])
        self.assertIn('native_role_score_below_0.8',r['rotation_policy']['reasons'])

    def hand(self,x,y,up=True):
        p=np.tile([float(x),float(y)],(21,1));p[0,1]+=70 if up else -70
        return dict(pixel_landmarks=p.tolist())

    def test_direction_and_board_select_fretting_over_strumming(self):
        c=[[1100,200],[400,200],[400,280],[1100,280]]
        fret=self.hand(1000,250);stroke=self.hand(300,400,False)
        result=rank_view([stroke,fret],(720,1280,3),c)
        self.assertEqual(result['selected'],fret)
        self.assertFalse(result['ranked'][0]['calibrated_probability'])

    def test_nut_extension_is_soft_and_moves_with_board(self):
        c=np.array([[1100,200],[400,200],[400,280],[1100,280]],float)
        near=score_hand(self.hand(1190,250),(720,1280),c)['cues']['board_proximity']
        far=score_hand(self.hand(1500,250),(720,1800),c)['cues']['board_proximity']
        self.assertGreater(near,.9);self.assertLess(far,near)
        shifted=score_hand(self.hand(990,350),(820,1280),c+[-200,100])['cues']['board_proximity']
        self.assertAlmostEqual(near,shifted)

    def test_ambiguous_or_absent_hands_abstain(self):
        h=self.hand(900,250)
        self.assertIsNone(rank_view([h,h],(720,1280))['selected'])
        self.assertIsNone(rank_view([],(720,1280))['selected'])
        self.assertIsNone(rank_view([self.hand(900,250,False)],(720,1280))['selected'])

    def test_bad_geometry_rejected(self):
        with self.assertRaises(ValueError):board_segment(np.zeros((4,2)))

    def test_direction_only_adds_bonus_and_cannot_block_near_board(self):
        c=[[1100,200],[400,200],[400,280],[1100,280]]
        down=self.hand(1000,250,False);up=self.hand(1000,250,True)
        a=score_hand(down,(720,1280),c);b=score_hand(up,(720,1280),c)
        self.assertEqual(a['base_score'],b['base_score'])
        self.assertAlmostEqual(a['score'],a['base_score'])
        self.assertAlmostEqual(b['score']-a['score'],.15)
        self.assertEqual(rank_view([down],(720,1280),c)['selected'],down)
        # Direction alone cannot establish which hand is fretting.
        self.assertIsNone(rank_view([up],(720,1280))['selected'])

    def test_actual_214_proposals_survive_low_direction(self):
        import json
        from pathlib import Path
        d=json.loads((Path(__file__).parent/'dataset/hand_analysis/runs/global_fretting_20261104_v1/result.json').read_text())
        f=next(r for r in d['frames'] if r['frame_index']==5135)
        for proposal in f['result']['global_candidates']:
            r=rank_view(proposal['hands'],(720,1280),f['board_corners'])
            self.assertIsNotNone(r['selected'])
            self.assertGreater(r['ranked'][0]['base_score'],.6)

    def test_one_fretting_view_beats_four_strumming_views(self):
        board=[[1100,200],[400,200],[400,280],[1100,280]]
        fret=self.hand(1000,250);stroke=self.hand(280,300,False)
        candidates=[dict(candidate_id=str(i),hands=[stroke]+([fret] if i==1 else [])) for i in range(4)]
        r=select_hand_groups(candidates,(720,1280),board)
        self.assertEqual(r['selection']['selected']['hands'][0],fret)
        self.assertEqual(r['selection']['candidate_count'],1)
        self.assertFalse(r['frequency_used_as_role_score'])

    def test_body_side_fretting_still_supported(self):
        board=[[1100,200],[400,200],[400,280],[1100,280]]
        h=self.hand(480,250,False)
        self.assertIsNotNone(rank_view([h],(720,1280),board)['selected'])
        near=score_hand(self.hand(1000,250),(720,1280),board)
        far=score_hand(h,(720,1280),board)
        self.assertGreater(near['cues']['nut_prior'],far['cues']['nut_prior'])

    def test_different_hands_from_one_view_never_merged(self):
        a=self.hand(900,250);b=self.hand(905,250)
        r=select_hand_groups([dict(candidate_id='one',hands=[a,b])],(720,1280),[[1100,200],[400,200],[400,280],[1100,280]])
        self.assertEqual(len(r['groups']),2)
        self.assertIsNone(r['selection']['selected'])

    def test_actual_4812_one_view_fretting_not_outvoted(self):
        import json
        from pathlib import Path
        from review_fretboard_clip import REFERENCE_CORNERS
        d=json.loads((Path(__file__).parent/'dataset/hand_analysis/runs/middle_temporal_200s_20261104_v1/result.json').read_text())
        f=next(r for r in d['frames'] if r['frame_index']==4812)
        candidates=f['result']['global_candidates']
        for order in [candidates,list(reversed(candidates))]:
            result=select_hand_groups(order,(720,1280),REFERENCE_CORNERS)
            selected=result['selection']['selected']
            self.assertIsNotNone(selected)
            self.assertGreater(np.asarray(selected['hands'][0]['pixel_landmarks'])[[5,9,13,17],0].mean(),800)
            self.assertEqual(result['selection']['candidate_count'],1)


if __name__=='__main__':unittest.main()
