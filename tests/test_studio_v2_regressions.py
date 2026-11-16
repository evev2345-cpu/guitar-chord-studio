import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'engine'))
from chord_studio_v2 import server_v2
from vision_context import add_layer


def result_fixture():
    c = dict(root_pc=0, quality='major', pcs=[0, 4, 7], score=1., symbol='C')
    context = dict(top3=[c], display_candidates=[c], status='audio_supported', bass=dict(pc=None, midi=None, status='unavailable', activation=0., presence=0.))
    rows = []
    for i in range(24):
        rows.append(dict(time_s=i/24, top3=[copy.deepcopy(c)],
                         context=copy.deepcopy(context), onset_context=copy.deepcopy(context),
                         presentation=dict(display_candidates=[copy.deepcopy(c)]),
                         onset_presentation=dict(display_candidates=[copy.deepcopy(c)])))
    return dict(branches={'0.2': rows})


class StudioRegressionTests(unittest.TestCase):
    def test_editor_quality_values_save_and_reload(self):
        import re
        html = (ROOT / 'chord_studio_v2/static/index.html').read_text(encoding='utf-8')
        options = re.search(r'id="edit-quality"[^>]*>(.*?)</select>', html, re.S).group(1)
        values = re.findall(r'value="([^"]+)"', options)
        self.assertIn('diminished', values)
        self.assertIn('augmented', values)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'result.json'
            for quality in values:
                with self.subTest(quality=quality):
                    path.write_text(json.dumps(result_fixture()), encoding='utf-8')
                    response = server_v2.apply_chord_edit_to_result(path, '0.2', 0., .5, 0, quality)
                    saved = json.loads(path.read_text(encoding='utf-8'))
                    self.assertEqual(response['candidate']['quality'], quality)
                    self.assertEqual(saved['branches']['0.2'][0]['presentation']['display_candidates'][0]['quality'], quality)

    def test_calibration_and_recalibration_preserve_saved_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'result.json'
            path.write_text(json.dumps(result_fixture()), encoding='utf-8')
            server_v2.apply_chord_edit_to_result(path, '0.2', .25, .5, 6, 'm7', 1)
            data = json.loads(path.read_text(encoding='utf-8'))
            observations = [dict(time_s=i/24, source_id='video', frame_index=i, status='unavailable') for i in range(24)]
            for _ in range(2):
                add_layer(data, observations, source_id='video', fps=24)
                for row in data['branches']['0.2']:
                    for key in ('vision_presentation', 'vision_onset_presentation'):
                        fields = ('display_candidates', 'frame_display_candidates') if .25 <= row['time_s'] < .5 else ('display_candidates',)
                        for field in fields:
                            candidate = row[key][field][0]
                            if .25 <= row['time_s'] < .5:
                                self.assertEqual((candidate['root_pc'], candidate['quality'], candidate['bass_pc']), (6, 'm7', 1))
                                self.assertTrue(candidate['user_edited'])
                            else:
                                self.assertEqual(candidate['root_pc'], 0)
                # Simulate persisted result loaded before the next calibration.
                data = json.loads(json.dumps(data))

    def test_shared_startup_recovers_interrupted_jobs_and_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / 'runs'
            statuses = ['uploading', 'queued', 'running', 'running', 'complete', 'error']
            for i, status in enumerate(statuses):
                directory = runs / str(i)
                directory.mkdir(parents=True)
                (directory / 'job.json').write_text(json.dumps(dict(id=str(i), status=status)), encoding='utf-8')
            (runs / '0/user_calibration.json').write_text('{"capo_candidate": 1}', encoding='utf-8')
            with patch.object(server_v2, 'ROOT', root), patch.object(server_v2, 'RUNS', runs), patch.object(server_v2, 'JOBS', {}):
                server_v2.seed_existing_runs()
                self.assertEqual(sum(j['status'] in ('uploading', 'queued', 'running') for j in server_v2.JOBS.values()), 0)
                self.assertEqual(server_v2.JOBS['4']['status'], 'complete')
                self.assertEqual(server_v2.JOBS['0']['user_calibration']['capo_candidate'], 1)
                for i in range(4):
                    self.assertEqual(json.loads((runs / str(i) / 'job.json').read_text())['status'], 'error')
                server_v2.seed_existing_runs()
                self.assertEqual(server_v2.JOBS['0']['status'], 'error')


if __name__ == '__main__':
    unittest.main()
