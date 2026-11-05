"""Reuse frozen scorer/evaluation with the validation-selected change detector."""
import json
import shutil
from pathlib import Path
import evaluate_change_aware_audio as runner
from calibrated_audio_changes import detect_changes

def main():
    old=runner.OUT;new=old.with_name('change_aware_audio_20261105_v2');config=json.loads((new/'detector_calibration.json').read_text())
    for name in ['frozen_review_plan.json','new_references.json','reference_freeze_sha256.json','new_tasks.json']:
        if not (new/name).exists():shutil.copy2(old/name,new/name)
    # Predictions are immutable input artifacts; reusing them performs no extra inference.
    if not (new/'new_predictions').exists():shutil.copytree(old/'new_predictions',new/'new_predictions')
    runner.OUT=new;runner.HEIGHT=config['selected_height'];runner.detect_changes=lambda t,f:detect_changes(t,f,config['selected_height'])
    runner.main()
    path=new/'config.json';record=json.loads(path.read_text());record.update(activation_floor=.3,detector_calibration_file=str(new/'detector_calibration.json'),
        detector_module='calibrated_audio_changes.py',review_status='New4references selected before v1 inference; exposed in v1, not fresh for v2')
    path.write_text(json.dumps(record,indent=2),encoding='utf-8')

if __name__=='__main__':main()
