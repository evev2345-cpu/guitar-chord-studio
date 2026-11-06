import copy
import tempfile
from pathlib import Path
import unittest
import numpy as np
from harmonic_context import bass_track, key_hypotheses, rerank_candidate_pool, spell, CONFIG
from chord_web_analysis import make_timeline


def candidate(root, quality, pcs, score=1.):
    return dict(root_pc=root,quality=quality,pcs=pcs,score=score,symbol='C')


class ContextTests(unittest.TestCase):
    def test_bass_requires_sustained_evidence(self):
        grid=np.arange(0,1,.01);frames=np.zeros((100,88));frames[:,45-21]=.8
        frames[50,38-21]=.99
        bass=bass_track(grid,frames,[.5])[0]
        self.assertEqual(bass['midi'],45)
        self.assertEqual(bass['instrument_attribution'],'unknown')

    def test_edge_and_silence_do_not_supply_bass(self):
        grid=np.arange(0,1,.01);frames=np.zeros((100,88))
        self.assertEqual([b['midi'] for b in bass_track(grid,frames,[0,.5,1])],[None]*3)

    def test_slash_and_root_position_spelling(self):
        c=candidate(0,'major',[0,4,7]);raw=copy.deepcopy(c)
        self.assertEqual(spell(c,dict(pc=4,midi=40,status='provisional'))['symbol'],'C/E')
        self.assertEqual(spell(c,dict(pc=0,midi=48,status='provisional'))['symbol'],'C')
        self.assertEqual(c,raw)

    def test_m7_vs_6_uses_bass_bonus_without_modifying_audio_score(self):
        pool=[candidate(0,'6',[0,4,7,9]),candidate(9,'m7',[0,4,7,9])];original=copy.deepcopy(pool)
        ranked=rerank_candidate_pool(pool,dict(pc=9,midi=45,status='provisional'),{})
        self.assertEqual(ranked[0]['quality'],'m7')
        self.assertEqual(ranked[1]['symbol'],'C6/A')
        self.assertEqual([r['score'] for r in ranked],[1.,1.])
        self.assertGreaterEqual(ranked[0]['adjusted_score']-ranked[1]['adjusted_score'],CONFIG['minimum_decision_margin'])
        self.assertEqual(pool,original)

    def test_unknown_bass_keeps_same_pc_tie(self):
        ranked=rerank_candidate_pool([candidate(0,'6',[0,4,7,9]),candidate(9,'m7',[0,4,7,9])],dict(pc=None,midi=None,status='unknown'),{})
        self.assertEqual(ranked[0]['adjusted_score'],ranked[1]['adjusted_score'])

    def test_strong_audio_winner_cannot_be_overridden(self):
        pool=[candidate(0,'major',[0,4,7],1.),candidate(9,'m7',[0,4,7,9],.8)]
        ranked=rerank_candidate_pool(pool,dict(pc=9,midi=45,status='provisional'),{})
        self.assertEqual(ranked[0]['root_pc'],0)
        self.assertFalse(ranked[1]['prior_eligible'])
        self.assertEqual(sum(ranked[1]['bonus_components'].values()),0.)

    def test_chromatic_chord_is_not_filtered_by_key(self):
        pool=[candidate(0,'major',[0,4,7],.97),candidate(1,'major',[1,5,8],1.)]
        key=dict(bonus_enabled=True,hypotheses=[dict(pcs=[0,2,4,5,7,9,11])])
        ranked=rerank_candidate_pool(pool,dict(pc=None,midi=None,status='unknown'),key)
        self.assertEqual(len(ranked),2)
        self.assertEqual(ranked[0]['root_pc'],1)
        self.assertTrue(all(v>=0 for r in ranked for v in r['bonus_components'].values()))

    def test_uniform_chroma_does_not_certify_a_key(self):
        key=key_hypotheses(np.ones((1000,88))*.8,20)
        self.assertFalse(key['bonus_enabled'])
        self.assertFalse(key['mode_identified'])

    def test_end_to_end_same_pc_tie_with_observed_a_bass(self):
        grid=np.arange(0,3,.01);frames=np.zeros((len(grid),88))
        frames[:,np.array([45,52,55,60])-21]=.8
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'prediction.npz';np.savez(path,times=grid,note=frames)
            result=make_timeline(path,3)
        for rows in result['branches'].values():
            row=rows[24]
            self.assertGreaterEqual(row['tied_top1_count'],2)
            self.assertEqual(row['context']['display_candidates'][0]['symbol'],'Am7')
            self.assertTrue(row['context']['resolved'])


if __name__=='__main__':unittest.main()
