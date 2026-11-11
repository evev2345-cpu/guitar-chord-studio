import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'engine'))
sys.path.insert(0,str(ROOT))
import run_local_separation as bridge
import separation_worker as worker
from chord_studio_v2 import server_v2


class SeparationRuntimeTests(unittest.TestCase):
    def test_development_uses_root_environment_and_worker(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(bridge,'ROOT',Path(tmp)),patch.object(sys,'frozen',False,create=True):
            python=Path(tmp)/'.venv-audio-separation/Scripts/python.exe'
            python.parent.mkdir(parents=True);python.touch()
            command=bridge.separation_command('audio.wav','out')
            self.assertEqual(command[:2],[str(python),str(Path(tmp)/'engine/separation_worker.py')])

    def test_frozen_uses_own_executable_and_never_development_python(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(Path(tmp)/'GuitarChordStudio.exe')):
            executable=Path(tmp)/'workers/GuitarSeparator/GuitarSeparator.exe'
            executable.parent.mkdir(parents=True);executable.touch()
            command=bridge.separation_command('audio.wav','out')
            self.assertEqual(command[0],str(executable))
            self.assertFalse(any('.venv' in arg for arg in command))
            executable.unlink()
            with self.assertRaisesRegex(ValueError,'workers'):bridge.separation_command('audio.wav','out')

    def test_child_cannot_inherit_parent_frozen_runtime(self):
        with patch.dict(os.environ,{'_PYI_APPLICATION_HOME_DIR':'parent','PYTHONHOME':'parent','PYTHONPATH':'parent'}):
            env=bridge.worker_environment()
        self.assertNotIn('_PYI_APPLICATION_HOME_DIR',env)
        self.assertNotIn('PYTHONHOME',env)
        self.assertEqual(env['PYINSTALLER_RESET_ENVIRONMENT'],'1')
        self.assertEqual(env['HF_HUB_OFFLINE'],'1')

    def test_existing_output_and_changed_model_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audio=root/'in.wav';audio.touch();output=root/'out';output.mkdir()
            with self.assertRaisesRegex(ValueError,'preserved'):worker.separate(audio,output)
            weights=root/'model';weights.write_bytes(b'invalid')
            with patch.object(worker,'model_path',return_value=weights),self.assertRaisesRegex(ValueError,'checksum'):
                worker.separate(audio,root/'fresh')

    def test_requested_separation_failure_is_not_silently_original_mode(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(server_v2,'RUNS',Path(tmp)),patch.object(server_v2,'JOBS',{}):
            job='a'*32;directory=Path(tmp)/job;directory.mkdir();(directory/'input.bin').touch()
            def execute(command,log,env=None):
                if command[0]=='ffmpeg':
                    with wave.open(str(directory/'audio.wav'),'wb') as f:
                        f.setnchannels(1);f.setsampwidth(2);f.setframerate(22050);f.writeframes(b'\0\0'*22050)
                else:raise subprocess.CalledProcessError(1,command)
            probe=subprocess.CompletedProcess([],0,stdout=json.dumps({'format':{'duration':'1'},'streams':[{'codec_type':'audio'}]}).encode())
            with patch.object(server_v2.subprocess,'run',return_value=probe),patch.object(server_v2,'run_cmd',side_effect=execute),patch.object(server_v2,'separation_command',return_value=['separator']),patch.object(server_v2,'write_result') as write:
                server_v2.analyze(job,separate_guitar=True)
            state=json.loads((directory/'job.json').read_text(encoding='utf-8'))
            self.assertEqual(state['status'],'error');self.assertEqual(state['separation_status'],'failed');write.assert_not_called()
