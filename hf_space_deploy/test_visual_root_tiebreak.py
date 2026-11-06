import unittest
from visual_root_tiebreak import resolve

def pair():return [dict(root_pc=0,quality='6',pcs=[0,4,7,9],score=1,symbol='C6'),dict(root_pc=9,quality='m7',pcs=[0,4,7,9],score=1,symbol='Am7')]

class RootTieTests(unittest.TestCase):
    def test_only_verified_distinct_root_cue_changes_order(self):
        before=pair();r=resolve(before,{0:.1,9:.8},visual_status='validated_root_or_voicing')
        self.assertEqual(r['candidates'][0]['symbol'],'Am7');self.assertEqual(before[0]['symbol'],'C6')
        self.assertEqual(r['candidates'][0]['score'],1)
    def test_unverified_visual_does_not_force_user_reference(self):
        r=resolve(pair(),{0:.1,9:.8});self.assertEqual(r['status'],'ambiguous_visual_unverified');self.assertEqual(r['candidates'][0]['symbol'],'C6')
    def test_different_pc_chord_is_not_reordered(self):
        c=pair();c[1]['pcs']=[0,3,7,9];r=resolve(c,{9:1},visual_status='validated_root_or_voicing')
        self.assertEqual(r['status'],'no_equal_pc_audio_tie')
    def test_weak_margin_preserves_tie(self):
        r=resolve(pair(),{0:.5,9:.52},visual_status='validated_root_or_voicing');self.assertEqual(r['status'],'ambiguous_visual_margin')

if __name__=='__main__':unittest.main()
