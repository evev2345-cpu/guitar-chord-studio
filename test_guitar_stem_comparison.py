import unittest
from joint_evidence_review import ROOT,read
from compare_guitar_stem_accuracy import score_interval,safe_evaluate


class GuitarStemComparisonTests(unittest.TestCase):
    def test_empty_guitar_evidence_abstains(self):
        result=safe_evaluate([],dict(concert_root_pc=7,quality='major'))
        self.assertTrue(result['abstain']);self.assertFalse(result['exact_top1'])

    def test_identical_reference_visual_weights_and_baseline(self):
        baseline=read(ROOT/'dataset/integration_review/runs/tutorial_accuracy_20261105_v1/result.json')
        result=read(ROOT/'dataset/integration_review/runs/guitar_stem_accuracy_20261105_v1/result.json')
        self.assertTrue(result['baseline_replay_exact'])
        self.assertEqual(result['frozen_parameters'],baseline['frozen_model'])
        self.assertEqual(result['provenance']['reference_sha256'],baseline['reference_sha256'])
        self.assertFalse(result['guitar_isolation_verified'])
        for old,new in zip(baseline['frames'],result['frames']):
            self.assertEqual(old['reference'],new['reference'])
            self.assertEqual(old['visual_pc_mass'],new['visual_pc_mass'])
            self.assertEqual(old['audio_only'],new['accompaniment_audio'])
            self.assertEqual(old['audio_analysis_frame_count'],new['audio_analysis_frame_count'])
        for branch in ['accompaniment_audio','accompaniment_combined','guitar_audio','guitar_combined']:
            for metric in ['exact_top1','exact_top3','root_top1']:
                self.assertEqual(result['metrics'][branch][metric],sum(r['evaluation'][branch][metric] for r in result['frames']))

    def test_stem_sample_grid_preserved(self):
        result=read(ROOT/'dataset/integration_review/runs/guitar_stem_accuracy_20261105_v1/result.json')
        for name in ['mixture','accompaniment','guitar','no_guitar']:
            qa=result['quality_checks'][name]
            self.assertEqual(qa['shape'],[1411200,2]);self.assertEqual(qa['sample_rate'],44100)
            self.assertTrue(qa['finite']);self.assertGreater(qa['rms'],0)


if __name__=='__main__':unittest.main()
