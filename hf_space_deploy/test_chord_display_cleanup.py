import unittest
from chord_display_cleanup import stabilize
from test_chord_display_stabilizer import c,row

class CleanupTests(unittest.TestCase):
    def test_real_change_not_delayed(self):
        a,b=c(),c(2);out=stabilize([0,.04,.08,.12],[row(a),row(a),row(b),row(b)])
        self.assertEqual(out[2]['display_candidate']['root_pc'],2)
    def test_isolated_close_alternative_removed(self):
        a,b=c(score=.96),c(2);out=stabilize([0,.04,.08],[row(a),row(b,a),row(a)])
        self.assertEqual(out[1]['display_candidate']['root_pc'],0)
    def test_strong_unsupported_note_kept(self):
        a,b=c(),c(2);out=stabilize([0,.04,.08],[row(a),row(b),row(a)])
        self.assertEqual(out[1]['display_candidate']['root_pc'],2)
    def test_dropout_only_bridged_between_same_candidates(self):
        a,b=c(),c(2);out=stabilize([0,.04,.08],[row(a),row(),row(a)]);self.assertEqual(out[1]['status'],'bridged_short_dropout')
        out=stabilize([0,.04,.08],[row(a),row(),row(b)]);self.assertIsNone(out[1]['display_candidate'])

if __name__=='__main__':unittest.main()
