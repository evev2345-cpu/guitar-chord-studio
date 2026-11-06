import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))
sys.path.insert(0, str(ROOT))

from harmonic_context import rerank_candidate_pool, CONFIG

def candidate(root, quality, pcs, score=1.):
    return dict(root_pc=root, quality=quality, pcs=pcs, score=score, symbol='C')

class FullMixAnchorTest(unittest.TestCase):
    def test_guitar_ambiguous_tie_resolved_by_full_mix_concordance(self):
        pool = [
            candidate(4, 'minor', [4, 7, 11], score=0.80), # Em
            candidate(7, 'major', [7, 11, 2], score=0.80), # G
        ]
        bass = dict(pc=None, status='unknown')
        key = dict(bonus_enabled=False)
        # Without full mix, it's a tie
        unresolved = rerank_candidate_pool(pool, bass, key)
        self.assertEqual(unresolved[0]['adjusted_score'], unresolved[1]['adjusted_score'])
        
        # With full mix indicating Em
        fm_top = [candidate(4, 'minor', [4, 7, 11], score=0.85)]
        resolved = rerank_candidate_pool(pool, bass, key, full_mix_top=fm_top)
        self.assertEqual(resolved[0]['root_pc'], 4)
        self.assertGreater(resolved[0]['adjusted_score'], resolved[1]['adjusted_score'])
        self.assertAlmostEqual(resolved[0]['bonus_components']['full_mix'], 0.05)

    def test_guitar_rootless_bass_resolved_by_full_mix_bass(self):
        # Guitar plays high triad E-G-B (Em) score=0.85 vs Cmaj7 (C-E-G-B) score=0.82
        # Without bass, Em wins on raw score
        # With full mix bass having pc=0 (C), Cmaj7 gets bass root match bonus and wins
        pool = [
            candidate(4, 'minor', [4, 7, 11], score=0.85),  # Em
            candidate(0, 'maj7', [0, 4, 7, 11], score=0.82) # Cmaj7
        ]
        guitar_bass = dict(pc=None, status='unknown')
        fm_bass = dict(pc=0, midi=36, status='sustained')
        key = dict(bonus_enabled=False)
        
        ranked = rerank_candidate_pool(pool, fm_bass, key)
        self.assertEqual(ranked[0]['root_pc'], 0) # Cmaj7 wins!
        self.assertEqual(ranked[0]['symbol'], 'Cmaj7')

if __name__ == '__main__':
    unittest.main()
