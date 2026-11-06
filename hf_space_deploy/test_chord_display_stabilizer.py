import unittest
from chord_display_stabilizer import stabilize

def c(root=0,quality='major',pcs=None,score=1):return dict(root_pc=root,quality=quality,pcs=pcs or [root,(root+4)%12,(root+7)%12],score=score,symbol=str(root))
def row(*candidates):return dict(top3=list(candidates),status='provisional' if candidates else 'insufficient_note_evidence')

class StabilizerTests(unittest.TestCase):
    def test_short_spike_rejected_and_real_change_committed(self):
        a,b=c(),c(2);times=[0,.05,.1,.15,.2,.25,.3,.35,.4,.45]
        out=stabilize(times,[row(a)]*3+[row(b)]+[row(a)]*2+[row(b)]*4)
        self.assertEqual(out[3]['display_candidate']['root_pc'],0)
        self.assertEqual(out[-1]['display_candidate']['root_pc'],2)
    def test_dropout_retention_bounded(self):
        out=stabilize([0,.05,.1,.15,.3],[row(c())]*3+[row(),row()])
        self.assertIsNotNone(out[3]['display_candidate']);self.assertIsNone(out[4]['display_candidate'])
    def test_extensions_need_longer_confirmation(self):
        a=c();b=c(0,'maj7',[0,4,7,11]);times=[i*.05 for i in range(9)];out=stabilize(times,[row(a)]*3+[row(b)]*6)
        self.assertEqual(out[5]['display_candidate']['quality'],'major');self.assertEqual(out[-1]['display_candidate']['quality'],'maj7')
    def test_equal_score_retains_existing_candidate(self):
        a,b=c(),c(9,'m7',[0,4,7,9]);out=stabilize([0,.05,.1,.15],[row(a)]*3+[row(b,a)])
        self.assertEqual(out[-1]['status'],'retained_top_score_tie');self.assertEqual(out[-1]['display_candidate']['root_pc'],0)
    def test_audio_edge_resets_display(self):
        out=stabilize([0,.05,.1,.15],[row(c())]*3+[dict(top3=[],status='audio_edge_no_full_window')])
        self.assertIsNone(out[-1]['display_candidate'])

if __name__=='__main__':unittest.main()
