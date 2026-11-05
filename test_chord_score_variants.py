import unittest
import numpy as np
from chord_score_variants import score_variants
from guitarset_benchmark import TEMPLATES


class ScoreVariantTests(unittest.TestCase):
    def top(self,result,name,row=0):return TEMPLATES[result[name][1][row,0]]
    def test_weak_extra_note_not_automatically_major_seventh(self):
        sal=np.zeros((1,12));sal[0,[7,11,2]]=1;sal[0,6]=.12
        r=score_variants(sal)
        self.assertEqual(self.top(r,'legacy')['quality'],'maj7')
        self.assertEqual((self.top(r,'cosine')['root_pc'],self.top(r,'cosine')['quality']),(7,'major'))
    def test_true_seventh_remains_seventh(self):
        sal=np.zeros((1,12));sal[0,[7,11,2,6]]=1
        r=score_variants(sal)
        self.assertEqual((self.top(r,'cosine')['root_pc'],self.top(r,'cosine')['quality']),(7,'maj7'))
    def test_silence_does_not_get_a_fabricated_chord(self):
        r=score_variants(np.zeros((3,12)))
        for scores,rank,usable in r.values():self.assertFalse(usable.any());self.assertTrue(np.isneginf(scores).all())
    def test_context_uses_nearby_audio_only(self):
        sal=np.zeros((3,12));sal[[0,2],0]=1;sal[[0,2],4]=1;sal[[0,2],7]=1;sal[1,[1,5,8]]=1
        r=score_variants(sal)
        self.assertEqual(self.top(r,'cosine',1)['root_pc'],1)
        self.assertEqual(self.top(r,'cosine_context',1)['root_pc'],0)


if __name__=='__main__':unittest.main()
