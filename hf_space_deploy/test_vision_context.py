import copy
import unittest
from vision_context import with_vision


def chord(root,pcs,quality='major',score=1.):
    return dict(root_pc=root,pcs=pcs,quality=quality,score=score,symbol=str(root),adjusted_score=score)


def context(candidates):
    return dict(top3=copy.deepcopy(candidates),display_candidates=[copy.deepcopy(candidates[0])],status='audio_supported',bass=dict(pc=None,midi=None,status='unknown'))


def observation():
    return dict(source_id='a'*64,time_s=1.,frame_index=24,frame_pixel_sha256='b'*64,status='provisional_location_only',
                alignment=dict(inlier_fraction=1.),spatial=dict(pc_support=[.5 if i in [2,7,11] else 0. for i in range(12)],supported_fingers=2))


class VisionContextTests(unittest.TestCase):
    def call(self,cs,obs=None,source='a'*64,time=1.):
        return with_vision(context(cs),dict(top3=cs),obs,source_id=source,time_s=time,max_delta=1/48)

    def test_location_bonus_can_prefer_an_audio_supported_chord(self):
        cs=[chord(0,[0,4,7]),chord(7,[2,7,11])];original=copy.deepcopy(cs)
        r=self.call(cs,observation())
        self.assertEqual(r['display_candidates'][0]['root_pc'],7)
        self.assertEqual(r['status'],'vision_position_preference')
        self.assertTrue(all(c['visual_bonus']>=0 for c in r['top3']))
        self.assertEqual(cs,original)

    def test_missing_hand_does_not_change_audio(self):
        cs=[chord(0,[0,4,7]),chord(7,[2,7,11])]
        for o in [None,dict(observation(),status='no_current_visual_support')]:
            r=self.call(cs,o);self.assertEqual(r['display_candidates'][0]['root_pc'],0);self.assertFalse(r['vision_evidence']['applied'])

    def test_wrong_video_or_stale_frame_is_not_used(self):
        cs=[chord(0,[0,4,7]),chord(7,[2,7,11])]
        for r in [self.call(cs,observation(),source='c'*64),self.call(cs,observation(),time=1.2)]:
            self.assertFalse(r['vision_evidence']['applied'])

    def test_equal_pc_root_tie_stays_unresolved(self):
        cs=[chord(0,[0,4,7,9],'6'),chord(9,[0,4,7,9],'m7')];ctx=context(cs);ctx['display_candidates']=copy.deepcopy(cs)
        r=with_vision(ctx,dict(top3=cs),observation(),source_id='a'*64,time_s=1.,max_delta=1/48)
        self.assertEqual(len(r['display_candidates']),2)
        self.assertFalse(r['vision_evidence']['root_voicing_validated'])

    def test_strong_audio_gap_is_protected(self):
        cs=[chord(0,[0,4,7],score=1.),chord(7,[2,7,11],score=.7)]
        r=self.call(cs,observation());self.assertEqual(r['display_candidates'][0]['root_pc'],0)
        self.assertEqual(next(c for c in r['top3'] if c['root_pc']==7)['visual_bonus'],0.)

    def test_unknown_contact_and_geometry_are_not_promoted(self):
        r=self.call([chord(0,[0,4,7]),chord(7,[2,7,11])],observation());e=r['vision_evidence']
        self.assertEqual(e['contact'],'unknown');self.assertFalse(e['geometry_verified']);self.assertFalse(e['anatomy_verified'])

    def test_insufficient_fingers_or_invalid_mass_is_not_trusted(self):
        cs=[chord(0,[0,4,7]),chord(7,[2,7,11])];o=observation();o['spatial']['supported_fingers']=1
        self.assertFalse(self.call(cs,o)['vision_evidence']['applied'])
        o=observation();o['spatial']['pc_support'][0]=float('nan')
        with self.assertRaises(ValueError):self.call(cs,o)


if __name__=='__main__':unittest.main()
